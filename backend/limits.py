import asyncio
import logging
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool
from stems import Stems

MAX_RUNNING = 1
MAX_WAITING = 3
TIMEOUT_SECONDS = 20.0
RESULT_TTL_SECONDS = 30.0

logger = logging.getLogger(__name__)


class QueueFull(Exception):
    pass


class SeparationTimeout(Exception):
    pass


class SeparationQueue:
    """Runs `separate` at most `max_running` at a time, with a bounded wait line."""

    def __init__(
        self,
        separate: Callable[[bytes], Stems],
        *,
        max_running: int = MAX_RUNNING,
        max_waiting: int = MAX_WAITING,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._separate = separate
        self._capacity = max_running + max_waiting
        self._timeout = timeout
        self._admitted = 0
        self._running = asyncio.Semaphore(max_running)

    async def run(self, data: bytes) -> Stems:
        # Checked and counted before the first await, so no two requests race past it.
        if self._admitted >= self._capacity:
            raise QueueFull()
        self._admitted += 1
        try:
            await self._running.acquire()
        except BaseException:
            self._admitted -= 1
            raise
        # Threadpool because Demucs blocks the event loop.
        work = asyncio.ensure_future(run_in_threadpool(self._separate, data))
        # Released only when the thread returns, so a timed-out run never overlaps the next.
        work.add_done_callback(self._finished)
        try:
            return await asyncio.wait_for(asyncio.shield(work), self._timeout)
        except TimeoutError:
            logger.warning("separation timed out after %s s", self._timeout)
            raise SeparationTimeout() from None

    def _finished(self, work: asyncio.Future) -> None:
        self._running.release()
        self._admitted -= 1
        if not work.cancelled():
            work.exception()  # Marks a late failure of a timed-out run as handled.


class Results:
    """Finished stems by content hash, dropped `ttl` seconds after they finished."""

    def __init__(
        self, *, ttl: float = RESULT_TTL_SECONDS, now: Callable[[], float]
    ) -> None:
        self._ttl = ttl
        self._now = now
        self._entries: dict[str, tuple[float, Stems]] = {}

    def __contains__(self, content_hash: str) -> bool:
        return content_hash in self._entries

    def add(self, content_hash: str, stems: Stems) -> None:
        self._entries[content_hash] = (self._now(), stems)

    def sweep(self) -> None:
        cutoff = self._now() - self._ttl
        expired = [h for h, (done, _) in self._entries.items() if done <= cutoff]
        for content_hash in expired:
            del self._entries[content_hash]

    def pop_stem(self, content_hash: str, stem: str) -> bytes | None:
        # Each stem is served once; the entry goes with its last stem.
        entry = self._entries.get(content_hash)
        if entry is None:
            return None
        stems = entry[1]
        wav_bytes = stems.pop(stem, None)
        if not stems:
            del self._entries[content_hash]
        return wav_bytes
