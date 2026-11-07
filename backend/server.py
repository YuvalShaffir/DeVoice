import hashlib
import time
from collections.abc import Callable
from typing import Annotated

from api import (
    CONTENT_TYPE_HEADER,
    INVALID_AUDIO,
    SEPARATE_PATH,
    STEM_PATH,
    TOKEN_HEADER,
    WAV_MEDIA_TYPE,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from guard import RequestGuard
from limits import (
    MAX_RUNNING,
    MAX_WAITING,
    RESULT_TTL_SECONDS,
    TIMEOUT_SECONDS,
    QueueFull,
    Results,
    SeparationQueue,
    SeparationTimeout,
    Stems,
)
from stems import STEMS
from wav import InvalidWav, validate_wav


def create_app(
    token: str,
    separate: Callable[[bytes], Stems],
    extension_origin: str,
    *,
    max_running: int = MAX_RUNNING,
    max_waiting: int = MAX_WAITING,
    timeout: float = TIMEOUT_SECONDS,
    ttl: float = RESULT_TTL_SECONDS,
    now: Callable[[], float] = time.monotonic,
) -> FastAPI:
    queue = SeparationQueue(
        separate, max_running=max_running, max_waiting=max_waiting, timeout=timeout
    )
    results = Results(ttl=ttl, now=now)

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Added first so CORS wraps it: CORS answers preflights and decorates guard errors.
    app.add_middleware(RequestGuard, token=token)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[extension_origin],
        allow_methods=["GET", "POST"],
        allow_headers=[TOKEN_HEADER, CONTENT_TYPE_HEADER],
    )

    @app.post(SEPARATE_PATH)
    async def separate_endpoint(request: Request) -> dict:
        results.sweep()
        media_type = request.headers.get(CONTENT_TYPE_HEADER, "").split(";")[0]
        if media_type.strip().lower() != WAV_MEDIA_TYPE:
            raise HTTPException(415, f"{CONTENT_TYPE_HEADER} must be {WAV_MEDIA_TYPE}")
        # Raw body, not multipart: Starlette spools multipart uploads over 1 MB to disk.
        data = await request.body()
        try:
            validate_wav(data)
        except InvalidWav:
            raise HTTPException(400, INVALID_AUDIO) from None
        content_hash = hashlib.sha256(data).hexdigest()
        # A dedupe hit keeps the original expiry.
        if content_hash not in results:
            try:
                results.add(content_hash, await queue.run(data))
            except QueueFull:
                raise HTTPException(429, "separation queue full") from None
            except SeparationTimeout:
                raise HTTPException(504, "separation timed out") from None
        return {"id": content_hash, "stems": STEMS}

    @app.get(
        STEM_PATH,
        responses={
            404: {
                "description": "Unknown stem, or no pending result for this hash (stems are served once)"
            }
        },
    )
    async def get_stem(
        content_hash: Annotated[str, PathParam(pattern=r"^[0-9a-f]{64}$")],
        stem: str,
    ) -> Response:
        results.sweep()
        if stem not in STEMS:
            raise HTTPException(404, f"Unknown stem: {stem}")
        wav_bytes = results.pop_stem(content_hash, stem)
        if wav_bytes is None:
            raise HTTPException(404, "Stem not found")
        return Response(wav_bytes, media_type=WAV_MEDIA_TYPE)

    return app
