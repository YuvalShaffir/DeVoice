import hashlib
from collections.abc import Callable
from typing import Annotated

from api import (
    CONTENT_TYPE_HEADER,
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
from starlette.concurrency import run_in_threadpool
from stems import STEMS


def create_app(
    token: str,
    separate: Callable[[bytes], dict[str, bytes]],
    extension_origin: str,
) -> FastAPI:
    pending: dict[str, dict[str, bytes]] = {}

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
        media_type = request.headers.get(CONTENT_TYPE_HEADER, "").split(";")[0]
        if media_type.strip().lower() != WAV_MEDIA_TYPE:
            raise HTTPException(415, f"{CONTENT_TYPE_HEADER} must be {WAV_MEDIA_TYPE}")
        # Raw body, not multipart: Starlette spools multipart uploads over 1 MB to disk.
        data = await request.body()
        content_hash = hashlib.sha256(data).hexdigest()
        if content_hash not in pending:
            # Calling threadpool because demucs is GPU intensive and blocks event loop.
            pending[content_hash] = await run_in_threadpool(separate, data)
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
        if stem not in STEMS:
            raise HTTPException(404, f"Unknown stem: {stem}")
        stems = pending.get(content_hash, {})
        wav_bytes = stems.pop(stem, None)
        if wav_bytes is None:
            raise HTTPException(404, "Stem not found")
        if not stems:
            del pending[content_hash]
        return Response(wav_bytes, media_type=WAV_MEDIA_TYPE)

    return app
