# GenBench

GenBench is a local-first image and inference workbench for a Windows laptop with a GTX 1650 (4 GB VRAM). Start with [the beginner story guide](docs/BEGINNER_STORY_GUIDE.md) to understand how the system works, then use [the project specification](docs/PROJECT_SPEC.md) for the architecture, model choices, acceptance criteria, and build order.

**Current state:** The Milestone 1 Python image worker exists under `services/ml-worker/`. The first FP16 run saved a black, safety-flagged PNG after a numerical warning. A later float32/model-offload run generated a visible, unflagged 512×512 lighthouse image. A second run produced the same PNG SHA256 and confirmed float32 for the UNet, VAE, and text encoder. Inference took about 14.6 minutes on the first successful run and 8.7 minutes on the repeat. The downloader now includes `hf_xet`. PostgreSQL migrations for image jobs and accounts are prepared but not applied. The API and frontend are not built yet.

The next controlled diagnostic from `services/ml-worker/` is:

```powershell
$env:HF_HOME = "D:\GenBench\hf-cache"
$env:HF_HUB_DOWNLOAD_TIMEOUT = "60"
.\.venv\Scripts\python.exe generate.py --prompt "a lighthouse at dusk, oil painting" --seed 42 --dtype float32 --offload model
```

The model is cached on D: after the successful download. A repeat may still be slow. Keep the safety checker enabled and inspect both the PNG and JSON sidecar. `HF_HUB_DOWNLOAD_TIMEOUT=60` helps when the connection is slow.
