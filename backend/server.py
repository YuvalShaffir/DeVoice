import hashlib
from collections.abc import Callable
from typing import Annotated

from auth import make_require_token
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from stems import STEMS


def create_app(
    token: str,
    separate: Callable[[bytes], dict[str, bytes]],
    extension_origin: str,
) -> FastAPI:
    pending: dict[str, dict[str, bytes]] = {}

    app = FastAPI(
        dependencies=[Depends(make_require_token(token))],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[extension_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["X-Auth-Token", "Content-Type"],
    )

    @app.post("/separate")
    async def seperate_endpoint(file: UploadFile) -> dict:
        data = await file.read()
        content_hash = hashlib.sha256(data).hexdigest()
        if content_hash not in pending:
            # Calling threadpool because demucs is GPU intensive and blocks event loop.
            pending[content_hash] = await run_in_threadpool(separate, data)
        return {"id": content_hash, "stems": STEMS}

    @app.get(
        "/stem/{content_hash}/{stem}",
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
        return Response(wav_bytes, media_type="audio/wav")

    return app
