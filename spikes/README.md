# Spikes

Small standalone scripts from Oct 19–20 that proved the two riskiest parts before we built the backend. The backend has the production versions (`backend/porchlight/watcher.py` and `vision.py`), so you don't need these to run Porchlight.

```bash
# from the repo root, after `make setup`
.venv/bin/python spikes/whep_frames.py 3 3                  # save 3 frames, 3 s apart, from the Ring live stream to frames/
.venv/bin/python spikes/bedrock_vision.py frames/<file>.jpg # describe one frame with Claude on Bedrock
```
