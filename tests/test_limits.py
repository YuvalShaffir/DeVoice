import asyncio
import threading
import time

import httpx
import pytest
from api_client import (
    BASE_URL,
    auth_headers,
    crashing_separate,
    fake_stems,
    fetch_stem,
    upload,
)
from fastapi.testclient import TestClient
from limits import MAX_RUNNING, MAX_WAITING, RESULT_TTL_SECONDS
from stems import NO_VOCALS, VOCALS
from wav_factory import make_wav

CAPACITY = MAX_RUNNING + MAX_WAITING
SHORT_TIMEOUT = 0.1
# Time for in-process requests to reach the queue; far above what they need.
SETTLE_SECONDS = 0.2
OVERLAP_SECONDS = 0.05
GIVE_UP_SECONDS = 5
BASE_FRAMES = 1000


class GatedSeparate:
    """Fake `separate` that blocks until `gate` is set; records concurrency."""

    def __init__(self, hold=0.0):
        self.gate = threading.Event()
        self.calls = 0
        self.max_running = 0
        self._running = 0
        self._hold = hold
        self._lock = threading.Lock()

    def __call__(self, data):
        with self._lock:
            self.calls += 1
            self._running += 1
            self.max_running = max(self.max_running, self._running)
        time.sleep(self._hold)
        self.gate.wait(GIVE_UP_SECONDS)
        with self._lock:
            self._running -= 1
        return fake_stems()


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def distinct_wavs(count):
    return [make_wav(frames=BASE_FRAMES + i) for i in range(count)]


def run_async(app, scenario):
    async def main():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
            return await asyncio.wait_for(scenario(client), GIVE_UP_SECONDS)

    return asyncio.run(main())


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def timed_client(make_app, clock):
    return TestClient(make_app(now=clock), base_url=BASE_URL)


def test_concurrent_uploads_separate_one_at_a_time(make_app):
    fake = GatedSeparate(hold=OVERLAP_SECONDS)
    fake.gate.set()

    async def scenario(client):
        uploads = [upload(client, auth_headers(), body=w) for w in distinct_wavs(3)]
        return await asyncio.gather(*uploads)

    responses = run_async(make_app(separate=fake), scenario)
    assert [r.status_code for r in responses] == [200] * 3
    assert fake.max_running == MAX_RUNNING


def test_full_queue_rejects_next_upload_and_admits_again_once_drained(make_app):
    fake = GatedSeparate()
    first, *rest = distinct_wavs(CAPACITY + 2)
    admitted_wavs, (rejected_wav, later_wav) = (
        rest[: CAPACITY - 1],
        rest[CAPACITY - 1 :],
    )

    async def scenario(client):
        admitted = [
            asyncio.create_task(upload(client, auth_headers(), body=w))
            for w in [first, *admitted_wavs]
        ]
        await asyncio.sleep(SETTLE_SECONDS)
        rejected = await upload(client, auth_headers(), body=rejected_wav)
        calls_while_full = fake.calls
        fake.gate.set()
        drained = await asyncio.gather(*admitted)
        later = await upload(client, auth_headers(), body=later_wav)
        return rejected, calls_while_full, drained, later

    rejected, calls_while_full, drained, later = run_async(
        make_app(separate=fake), scenario
    )
    assert rejected.status_code == 429
    assert calls_while_full == MAX_RUNNING
    assert [r.status_code for r in drained] == [200] * CAPACITY
    assert later.status_code == 200


def test_timed_out_separation_holds_the_slot_until_its_thread_returns(make_app):
    fake = GatedSeparate()
    stuck_wav, next_wav = distinct_wavs(2)

    async def scenario(client):
        timed_out = await upload(client, auth_headers(), body=stuck_wav)
        queued = asyncio.create_task(upload(client, auth_headers(), body=next_wav))
        await asyncio.sleep(SETTLE_SECONDS)
        calls_while_stuck = fake.calls
        fake.gate.set()
        return timed_out, calls_while_stuck, await queued

    timed_out, calls_while_stuck, queued = run_async(
        make_app(separate=fake, timeout=SHORT_TIMEOUT), scenario
    )
    assert timed_out.status_code == 504
    assert calls_while_stuck == 1
    assert queued.status_code == 200
    assert fake.max_running == MAX_RUNNING


def test_failing_separation_returns_500_and_frees_the_slot(make_app):
    calls = []

    def fails_once(data):
        calls.append(data)
        if len(calls) == 1:
            return crashing_separate(data)
        return fake_stems()

    async def scenario(client):
        failed = await upload(client, auth_headers())
        retried = await upload(client, auth_headers())
        return failed, retried

    failed, retried = run_async(make_app(separate=fails_once), scenario)
    assert failed.status_code == 500
    assert retried.status_code == 200


@pytest.mark.parametrize(
    ("age", "status"),
    [
        (RESULT_TTL_SECONDS - 0.1, 200),
        (RESULT_TTL_SECONDS, 404),
        (RESULT_TTL_SECONDS + 1, 404),
    ],
)
def test_result_expires_ttl_after_it_finished(timed_client, clock, age, status):
    content_hash = upload(timed_client, auth_headers()).json()["id"]
    clock.now = age
    assert (
        fetch_stem(timed_client, content_hash, VOCALS, auth_headers()).status_code
        == status
    )


def test_partly_fetched_result_still_expires(timed_client, clock):
    content_hash = upload(timed_client, auth_headers()).json()["id"]
    clock.now = 1
    assert (
        fetch_stem(timed_client, content_hash, VOCALS, auth_headers()).status_code
        == 200
    )
    clock.now = RESULT_TTL_SECONDS
    res = fetch_stem(timed_client, content_hash, NO_VOCALS, auth_headers())
    assert res.status_code == 404


def test_dedupe_hit_does_not_refresh_expiry(timed_client, clock, separated):
    content_hash = upload(timed_client, auth_headers()).json()["id"]
    clock.now = RESULT_TTL_SECONDS - 10
    assert upload(timed_client, auth_headers()).json()["id"] == content_hash
    assert len(separated) == 1
    clock.now = RESULT_TTL_SECONDS + 1
    res = fetch_stem(timed_client, content_hash, VOCALS, auth_headers())
    assert res.status_code == 404


def test_upload_after_expiry_separates_again(timed_client, clock, separated):
    upload(timed_client, auth_headers())
    clock.now = RESULT_TTL_SECONDS
    assert upload(timed_client, auth_headers()).status_code == 200
    assert len(separated) == 2
