"""Integration clients used by the API, built lazily from settings.

Real clients are only built when an endpoint first needs them, so a missing integration
returns 503 "Integration not configured" on the endpoints that depend on it instead of
stopping the API from starting. Automated tests pass in-memory fakes through the
constructor; the app itself never uses fakes.
"""

import threading
from typing import Any

from readybid_api.auth import SupabaseTokenVerifier, TokenVerifier
from readybid_core.clients import NotConfigured, build_repository_and_storage
from readybid_core.config import Settings
from readybid_core.integrations import _missing
from readybid_core.jobs import QUEUE_NAME
from readybid_core.repository import Repository
from readybid_core.storage import DocumentStorage


class Services:
    def __init__(
        self,
        settings: Settings,
        *,
        repo: Repository | None = None,
        storage: DocumentStorage | None = None,
        queue: Any | None = None,
        verifier: TokenVerifier | None = None,
    ) -> None:
        self.settings = settings
        self._repo = repo
        self._storage = storage
        self._queue = queue
        self._verifier = verifier
        self._lock = threading.Lock()

    def _build_supabase(self) -> None:
        repo, storage = build_repository_and_storage(self.settings)
        if self._repo is None:
            self._repo = repo
        if self._storage is None:
            self._storage = storage

    def repo(self) -> Repository:
        with self._lock:
            if self._repo is None:
                self._build_supabase()
            assert self._repo is not None
            return self._repo

    def storage(self) -> DocumentStorage:
        with self._lock:
            if self._storage is None:
                self._build_supabase()
            assert self._storage is not None
            return self._storage

    def queue(self) -> Any:
        with self._lock:
            if self._queue is None:
                if self.settings.redis_url is None:
                    raise NotConfigured(_missing(["REDIS_URL"]))
                from redis import Redis
                from rq import Queue

                # Creating these does not connect; enqueueing does, with short timeouts.
                connection = Redis.from_url(
                    self.settings.redis_url, socket_connect_timeout=2, socket_timeout=5
                )
                self._queue = Queue(QUEUE_NAME, connection=connection)
            return self._queue

    def verifier(self) -> TokenVerifier:
        with self._lock:
            if self._verifier is None:
                self._verifier = SupabaseTokenVerifier(self.settings)
            return self._verifier

    def ensure_llm_configured(self) -> None:
        """The worker makes the model calls, but fail fast here rather than queue a doomed job."""
        if self.settings.groq_api_key is None:
            raise NotConfigured(_missing(["GROQ_API_KEY"]))
