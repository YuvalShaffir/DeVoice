# DeVoice
Real-time vocal removal for any Chrome tab - GPU-powered stem separation to help you focus.

## Run the backend

```bash
uv sync
cd backend
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

The extension ID is derived from the pinned `key` in `extension/manifest.json`, so CORS matches the loaded extension with no configuration. Run it as a normal user: the backend refuses to start as root or Administrator. Uploaded chunks and stems are held in memory and never written to disk.
