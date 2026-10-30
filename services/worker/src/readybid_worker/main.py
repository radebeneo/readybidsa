"""RQ worker entry point.

Run from the repository root:
    uv run readybid-worker
"""

import sys
import time
from collections.abc import Callable

from redis import Redis
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry
from rq import Queue, SimpleWorker, Worker
from rq.defaults import DEFAULT_LOGGING_DATE_FORMAT, DEFAULT_LOGGING_FORMAT
from rq.scheduler import RQScheduler
from rq.timeouts import TimerDeathPenalty

from readybid_core.config import DEFAULT_RQ_SCHEDULER_INTERVAL_SECONDS, Settings, get_settings
from readybid_core.jobs import QUEUE_NAME

# Redis connection settings. ``Redis.from_url`` applies no command retries and no health
# check by default. These values must stay picklable: RQ rebuilds the connection in the
# scheduler child process from the pool's connection kwargs.
REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 10
REDIS_COMMAND_RETRIES = 3

# Restart loop: RQ's work loop exits on a Redis timeout or on a connection error outside the
# blocking dequeue (for example a heartbeat), so the worker is rebuilt here instead.
RESTART_DELAY_SECONDS = 5.0
MAX_RESTART_DELAY_SECONDS = 60.0
STABLE_RUN_SECONDS = 300.0


class SchedulerIntervalMixin:
    """Run RQ's scheduler with a configurable polling interval.

    RQ's worker creates its scheduler with the default interval of 1 second. Each loop
    sends several Redis commands (heartbeat, lock refresh, registry scan), which would use
    up a hosted plan's command quota (for example Upstash's free tier) within days. This
    mirrors ``BaseWorker._start_scheduler`` from RQ 2.x and only adds ``interval``. RQ
    reuses the same scheduler object when it restarts a dead scheduler process, so the
    interval also applies after restarts.
    """

    scheduler_interval_seconds: int = DEFAULT_RQ_SCHEDULER_INTERVAL_SECONDS

    def _start_scheduler(
        self,
        burst: bool = False,
        logging_level: str | None = "INFO",
        date_format: str = DEFAULT_LOGGING_DATE_FORMAT,
        log_format: str = DEFAULT_LOGGING_FORMAT,
    ) -> None:
        worker = self  # typed loosely: the concrete class is an RQ worker
        scheduler = RQScheduler(
            worker.queues,  # type: ignore[attr-defined]
            connection=worker.connection,  # type: ignore[attr-defined]
            interval=self.scheduler_interval_seconds,
            logging_level=logging_level if logging_level is not None else worker.log.level,  # type: ignore[attr-defined]
            date_format=date_format,
            log_format=log_format,
            serializer=worker.serializer,  # type: ignore[attr-defined]
        )
        worker.scheduler = scheduler  # type: ignore[attr-defined]
        scheduler.acquire_locks()
        if not scheduler.acquired_locks:
            return
        if burst:
            try:
                scheduler.register_birth()
                scheduler.enqueue_scheduled_jobs()
            finally:
                scheduler.release_locks()
                scheduler.register_death()
        else:
            scheduler.start()


class ReadyBidWorker(SchedulerIntervalMixin, Worker):
    """POSIX worker: forks per job, with the configurable scheduler interval."""


class WindowsWorker(SchedulerIntervalMixin, SimpleWorker):
    """Windows has no fork() or SIGALRM, so run jobs in-process with timer-based timeouts."""

    death_penalty_class = TimerDeathPenalty


def worker_class() -> type[Worker]:
    return WindowsWorker if sys.platform == "win32" else ReadyBidWorker


def build_connection(redis_url: str) -> Redis:
    """Create a Redis client that survives idle resets from hosted Redis (such as Upstash).

    Keepalive and a health check (a PING before a command on a connection idle for more than
    the interval) detect dead sockets early, and a few jittered retries ride out brief
    resets. Creating the client does not open a connection.
    """
    return Redis.from_url(
        redis_url,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
        socket_keepalive=True,
        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
        retry=Retry(ExponentialWithJitterBackoff(base=1, cap=10), REDIS_COMMAND_RETRIES),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    )


def build_queue(connection: Redis) -> Queue:
    # Creating a Queue does not open a Redis connection.
    return Queue(QUEUE_NAME, connection=connection)


def build_worker(settings: Settings) -> Worker:
    """Create the worker. This connects to Redis, so REDIS_URL must point at a running server."""
    if settings.redis_url is None:
        raise RuntimeError("Integration not configured: set REDIS_URL to start the worker.")

    connection = build_connection(settings.redis_url)
    worker = worker_class()([build_queue(connection)], connection=connection)
    worker.scheduler_interval_seconds = settings.rq_scheduler_interval_seconds  # type: ignore[attr-defined]
    return worker


def stop_requested(worker: Worker) -> bool:
    """True when RQ received a stop signal (such as Ctrl+C), so the exit was intentional."""
    return getattr(worker, "_shutdown_requested_date", None) is not None or bool(
        getattr(worker, "_stop_requested", False)
    )


def _log(message: str) -> None:
    print(f"readybid-worker: {message}", file=sys.stderr, flush=True)


def run_forever(
    settings: Settings,
    *,
    build: Callable[[Settings], Worker] = build_worker,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Run the worker, rebuilding it whenever it exits without a stop request.

    A Redis error on the very first build exits with code 1, so a wrong REDIS_URL fails
    fast instead of retrying forever. Later failures are retried with exponential backoff
    (reset after a run of at least STABLE_RUN_SECONDS). A new worker re-acquires the
    scheduler lock once the previous holder's lock has expired.
    """
    delay = RESTART_DELAY_SECONDS
    first_attempt = True
    while True:
        started = clock()
        worker: Worker | None = None
        try:
            worker = build(settings)
            if first_attempt:
                # Creating the client does not connect, so check REDIS_URL once up front.
                worker.connection.ping()
        except RedisError as error:
            if first_attempt:
                _log(f"could not connect to Redis (check REDIS_URL): {type(error).__name__}")
                return 1
            _log(f"could not reconnect to Redis: {type(error).__name__}")
        first_attempt = False

        if worker is not None:
            try:
                # The scheduler moves retries with an interval (see
                # readybid_core.jobs.enqueue_analysis) back onto the queue. Without it,
                # scheduled retries would never run.
                worker.work(with_scheduler=True)
            except RedisError as error:
                # RQ's teardown talks to Redis too, so it can raise during an outage.
                _log(f"worker lost its Redis connection: {type(error).__name__}")
            if stop_requested(worker):
                return 0
            if clock() - started >= STABLE_RUN_SECONDS:
                delay = RESTART_DELAY_SECONDS

        _log(f"worker stopped unexpectedly; restarting in {delay:.0f} s")
        try:
            sleep(delay)
        except KeyboardInterrupt:
            return 0
        delay = min(delay * 2, MAX_RESTART_DELAY_SECONDS)


def main() -> int:
    try:
        return run_forever(get_settings())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
