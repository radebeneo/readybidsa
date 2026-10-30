import logging
import pickle
import sys
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq.connections import get_connection_kwargs
from rq.timeouts import TimerDeathPenalty

from readybid_core.config import Settings
from readybid_core.jobs import QUEUE_NAME
from readybid_worker import main as worker_main
from readybid_worker.main import (
    MAX_RESTART_DELAY_SECONDS,
    RESTART_DELAY_SECONDS,
    STABLE_RUN_SECONDS,
    ReadyBidWorker,
    SchedulerIntervalMixin,
    WindowsWorker,
    build_connection,
    build_queue,
    build_worker,
    run_forever,
    stop_requested,
    worker_class,
)


def test_worker_requires_redis_url() -> None:
    with pytest.raises(RuntimeError, match="Integration not configured"):
        build_worker(Settings(_env_file=None))


def test_queue_uses_readybid_name() -> None:
    # Redis.from_url and Queue() do not connect, so no Redis server is needed.
    queue = build_queue(Redis.from_url("redis://localhost:6379/0"))

    assert queue.name == QUEUE_NAME


def test_worker_class_matches_platform() -> None:
    expected = WindowsWorker if sys.platform == "win32" else ReadyBidWorker

    assert worker_class() is expected


def test_windows_worker_uses_timer_timeouts() -> None:
    assert WindowsWorker.death_penalty_class is TimerDeathPenalty


def test_scheduler_interval_defaults_to_ten_seconds() -> None:
    assert Settings(_env_file=None).rq_scheduler_interval_seconds == 10


@pytest.mark.parametrize("value", [0, 61])
def test_scheduler_interval_is_bounded(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rq_scheduler_interval_seconds=value)


class FakeScheduler:
    def __init__(self, queues: Any, connection: Any, **kwargs: Any) -> None:
        self.queues = queues
        self.connection = connection
        self.kwargs = kwargs
        self.acquired_locks = {QUEUE_NAME}
        self.calls: list[str] = []

    def acquire_locks(self) -> set[str]:
        self.calls.append("acquire_locks")
        return self.acquired_locks

    def start(self) -> None:
        self.calls.append("start")

    def register_birth(self) -> None:
        self.calls.append("register_birth")

    def enqueue_scheduled_jobs(self) -> None:
        self.calls.append("enqueue_scheduled_jobs")

    def release_locks(self) -> None:
        self.calls.append("release_locks")

    def register_death(self) -> None:
        self.calls.append("register_death")


def fake_worker(interval: int) -> SimpleNamespace:
    return SimpleNamespace(
        queues=["queue"],
        connection="connection",
        log=logging.getLogger("test"),
        serializer="serializer",
        scheduler=None,
        scheduler_interval_seconds=interval,
    )


def test_start_scheduler_passes_configured_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_main, "RQScheduler", FakeScheduler)
    worker = fake_worker(interval=25)

    SchedulerIntervalMixin._start_scheduler(worker)  # type: ignore[arg-type]

    scheduler = worker.scheduler
    assert isinstance(scheduler, FakeScheduler)
    assert scheduler.kwargs["interval"] == 25
    assert scheduler.queues == ["queue"]
    assert scheduler.connection == "connection"
    assert scheduler.kwargs["serializer"] == "serializer"
    assert scheduler.calls == ["acquire_locks", "start"]


def test_start_scheduler_burst_enqueues_once_and_releases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_main, "RQScheduler", FakeScheduler)
    worker = fake_worker(interval=10)

    SchedulerIntervalMixin._start_scheduler(worker, burst=True)  # type: ignore[arg-type]

    assert worker.scheduler.calls == [
        "acquire_locks",
        "register_birth",
        "enqueue_scheduled_jobs",
        "release_locks",
        "register_death",
    ]


def test_start_scheduler_without_lock_does_not_start(monkeypatch: pytest.MonkeyPatch) -> None:
    class LockedOutScheduler(FakeScheduler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.acquired_locks = set()

    monkeypatch.setattr(worker_main, "RQScheduler", LockedOutScheduler)
    worker = fake_worker(interval=10)

    SchedulerIntervalMixin._start_scheduler(worker)  # type: ignore[arg-type]

    assert worker.scheduler.calls == ["acquire_locks"]


def test_build_worker_applies_scheduler_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    class FakeWorker:
        scheduler_interval_seconds = 10

        def __init__(self, queues: Any, connection: Any) -> None:
            created["queues"] = queues
            created["connection"] = connection

    monkeypatch.setattr(worker_main, "worker_class", lambda: FakeWorker)
    settings = Settings(
        _env_file=None,
        redis_url="rediss://default:pw@example.upstash.io:6379",
        rq_scheduler_interval_seconds=30,
    )

    worker = build_worker(settings)

    assert isinstance(worker, FakeWorker)
    assert worker.scheduler_interval_seconds == 30
    assert created["queues"][0].name == QUEUE_NAME


# --- Redis connection settings -------------------------------------------------------

DUMMY_URL = "rediss://default:pw@example.invalid:6379"


def test_build_connection_adds_health_check_keepalive_and_retries() -> None:
    # Creating the client and a connection object does not open a socket.
    connection = build_connection(DUMMY_URL).connection_pool.make_connection()

    assert connection.health_check_interval == worker_main.REDIS_HEALTH_CHECK_INTERVAL_SECONDS
    assert connection.socket_keepalive is True
    assert connection.socket_connect_timeout == worker_main.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
    assert connection.retry.get_retries() == worker_main.REDIS_COMMAND_RETRIES
    assert RedisConnectionError in connection.retry._supported_errors


def test_connection_settings_survive_the_scheduler_child_rebuild() -> None:
    # RQ rebuilds the connection in the scheduler process from the pool's kwargs.
    kwargs = pickle.loads(pickle.dumps(get_connection_kwargs(build_connection(DUMMY_URL))))
    child = Redis(**kwargs).connection_pool.make_connection()

    assert child.health_check_interval == worker_main.REDIS_HEALTH_CHECK_INTERVAL_SECONDS
    assert child.socket_keepalive is True
    assert child.retry.get_retries() == worker_main.REDIS_COMMAND_RETRIES


# --- Restart loop ----------------------------------------------------------------------


class FakeConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.pings = 0

    def ping(self) -> bool:
        self.pings += 1
        if self.error is not None:
            raise self.error
        return True


class ScriptedWorker:
    """Fake RQ worker. ``work`` ends the way a real worker would for the given outcome."""

    def __init__(self, outcome: str, connection: FakeConnection | None = None) -> None:
        self.outcome = outcome
        self.connection = connection or FakeConnection()
        self._shutdown_requested_date: str | None = None
        self._stop_requested = False
        self.work_calls: list[dict[str, Any]] = []

    def work(self, **kwargs: Any) -> bool:
        self.work_calls.append(kwargs)
        if self.outcome == "stop":
            self._shutdown_requested_date = "requested"
        elif self.outcome == "redis_error":
            raise RedisConnectionError("simulated reset during teardown")
        # "exit": RQ logs "Redis connection timeout, quitting..." and returns.
        return False


def scripted_build(steps: list[Any]) -> Callable[[Settings], Any]:
    remaining = list(steps)

    def build(settings: Settings) -> Any:
        step = remaining.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    return build


def fixed_clock() -> float:
    return 0.0


def redis_settings() -> Settings:
    return Settings(_env_file=None, redis_url="redis://localhost:6379/0")


def test_worker_restarts_after_an_unexpected_exit_and_stops_on_request() -> None:
    first, second = ScriptedWorker("exit"), ScriptedWorker("stop")
    sleeps: list[float] = []

    code = run_forever(
        redis_settings(),
        build=scripted_build([first, second]),
        sleep=sleeps.append,
        clock=fixed_clock,
    )

    assert code == 0
    assert sleeps == [RESTART_DELAY_SECONDS]
    assert first.work_calls == [{"with_scheduler": True}]
    assert second.work_calls == [{"with_scheduler": True}]
    assert first.connection.pings == 1  # REDIS_URL is checked once, on the first attempt
    assert second.connection.pings == 0


def test_restart_delay_doubles_up_to_the_cap() -> None:
    steps = [ScriptedWorker("exit") for _ in range(7)] + [ScriptedWorker("stop")]
    sleeps: list[float] = []

    run_forever(
        redis_settings(), build=scripted_build(steps), sleep=sleeps.append, clock=fixed_clock
    )

    assert sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0]
    assert max(sleeps) == MAX_RESTART_DELAY_SECONDS


def test_restart_delay_resets_after_a_stable_run() -> None:
    steps = [
        ScriptedWorker("exit"),
        ScriptedWorker("exit"),
        ScriptedWorker("exit"),
        ScriptedWorker("stop"),
    ]
    # start/end pairs per run: short, short, stable; the stopped run reads only its start.
    times: Iterator[float] = iter([0.0, 1.0, 10.0, 11.0, 20.0, 20.0 + STABLE_RUN_SECONDS, 400.0])
    sleeps: list[float] = []

    run_forever(
        redis_settings(),
        build=scripted_build(steps),
        sleep=sleeps.append,
        clock=lambda: next(times),
    )

    assert sleeps == [5.0, 10.0, 5.0]


def test_bad_redis_url_fails_fast_without_retrying() -> None:
    sleeps: list[float] = []

    code = run_forever(
        redis_settings(),
        build=scripted_build([RedisConnectionError("refused")]),
        sleep=sleeps.append,
        clock=fixed_clock,
    )

    assert code == 1
    assert sleeps == []


def test_unreachable_redis_on_first_ping_fails_fast() -> None:
    worker = ScriptedWorker("exit", connection=FakeConnection(RedisConnectionError("refused")))
    sleeps: list[float] = []

    code = run_forever(
        redis_settings(), build=scripted_build([worker]), sleep=sleeps.append, clock=fixed_clock
    )

    assert code == 1
    assert worker.work_calls == []
    assert sleeps == []


def test_reconnect_failures_after_startup_are_retried() -> None:
    steps = [ScriptedWorker("exit"), RedisConnectionError("reset"), ScriptedWorker("stop")]
    sleeps: list[float] = []

    code = run_forever(
        redis_settings(), build=scripted_build(steps), sleep=sleeps.append, clock=fixed_clock
    )

    assert code == 0
    assert sleeps == [5.0, 10.0]


def test_redis_error_escaping_the_work_loop_triggers_a_restart() -> None:
    steps = [ScriptedWorker("redis_error"), ScriptedWorker("stop")]
    sleeps: list[float] = []

    code = run_forever(
        redis_settings(), build=scripted_build(steps), sleep=sleeps.append, clock=fixed_clock
    )

    assert code == 0
    assert sleeps == [RESTART_DELAY_SECONDS]


def test_ctrl_c_while_waiting_to_restart_exits_cleanly() -> None:
    def interrupted_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    code = run_forever(
        redis_settings(),
        build=scripted_build([ScriptedWorker("exit")]),
        sleep=interrupted_sleep,
        clock=fixed_clock,
    )

    assert code == 0


def test_stop_requested_reads_both_rq_flags() -> None:
    worker = ScriptedWorker("exit")
    assert not stop_requested(worker)  # type: ignore[arg-type]

    worker._stop_requested = True
    assert stop_requested(worker)  # type: ignore[arg-type]

    other = ScriptedWorker("exit")
    other._shutdown_requested_date = "requested"
    assert stop_requested(other)  # type: ignore[arg-type]


def test_main_without_redis_url_exits_with_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_main, "get_settings", lambda: Settings(_env_file=None))

    assert worker_main.main() == 1
