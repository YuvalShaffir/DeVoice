import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from auth import make_require_token
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from stems import STEMS


def create_app(
    token: str,
    separate: Callable[[bytes], dict[str, bytes]],
    cache_dir: Path,
    extension_origin: str,
) -> FastAPI:
    cache_dir.mkdir(exist_ok=True)

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
        track_cache = cache_dir / content_hash
        if not track_cache.exists():
            # Calling threadpool because demucs is GPU intensive and blocks event loop.
            stems = await run_in_threadpool(separate, data)
            track_cache.mkdir(parents=True)
            for name, wav_bytes in stems.items():
                (track_cache / f"{name}.wav").write_bytes(wav_bytes)
        return {"id": content_hash, "stems": STEMS}

    @app.get(
        "/stem/{content_hash}/{stem}",
        responses={
            404: {"description": "Unknown stem, or no cached result for this hash"}
        },
    )
    async def get_stem(
        content_hash: Annotated[str, PathParam(pattern=r"^[0-9a-f]{64}$")],
        stem: str,
    ) -> FileResponse:
        if stem not in STEMS:
            raise HTTPException(404, f"Unknown stem: {stem}")
        path = cache_dir / content_hash / f"{stem}.wav"
        if not path.exists():
            raise HTTPException(404, "Stem not found")
        return FileResponse(path, media_type="audio/wav")

    return app
