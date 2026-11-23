# GenBench

GenBench is a local-first image and inference workbench for a Windows laptop with a GTX 1650 (4 GB VRAM). Start with [the beginner story guide](docs/BEGINNER_STORY_GUIDE.md) to understand how the system works, then use [the project specification](docs/PROJECT_SPEC.md) for the architecture, model choices, acceptance criteria, and build order.

**Current state:** The Milestone 1 Python image worker exists under `services/ml-worker/`. The first FP16 run loaded Stable Diffusion 1.5 and completed inference, but saved a black, safety-flagged PNG after a numerical warning. A float32/model-offload attempt failed during the full-precision weight download with `ChunkedEncodingError` before inference. The downloader now includes `hf_xet`; a valid image baseline is still pending. Follow M0 in the specification before building the web app.

The next controlled diagnostic from `services/ml-worker/` is:

```powershell
$env:HF_HOME = "D:\GenBench\hf-cache"
$env:HF_HUB_DOWNLOAD_TIMEOUT = "60"
.\.venv\Scripts\python.exe generate.py --prompt "a lighthouse at dusk, oil painting" --seed 42 --dtype float32 --offload model
```

The float32 run will resume/download additional model weights and may be slow. Keep the safety checker enabled and inspect both the PNG and JSON sidecar. Set `HF_HUB_DOWNLOAD_TIMEOUT=60` if the connection is slow.
