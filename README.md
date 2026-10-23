# DeVoice
Real-time vocal removal for any Chrome tab - GPU-powered stem separation to help you focus.

## Run the backend

```bash
uv sync
cd backend
EXTENSION_ID=<your-extension-id> uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

`EXTENSION_ID` is the ID of the loaded Chrome extension (`chrome://extensions`). Stems are held in memory and never written to disk.
