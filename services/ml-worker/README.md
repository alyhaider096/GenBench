# GenBench ML worker — Milestone 1

Local Stable Diffusion 1.5 image generation with timing and CUDA memory metrics.

## Setup (Windows PowerShell)

Run these commands from `genbench/services/ml-worker`:

```powershell
nvidia-smi
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no GPU')"
```

The first generation downloads model weights from Hugging Face. Keep enough free disk space for the download and cache.

## Generate

```powershell
.\.venv\Scripts\python.exe generate.py --prompt "a lighthouse at dusk, oil painting" --seed 42 --warmup
```

If CUDA runs out of memory:

```powershell
.\.venv\Scripts\python.exe generate.py --prompt "a lighthouse at dusk, oil painting" --seed 42 --offload model
```

If FP16 produces a black image on this GPU, try:

```powershell
.\.venv\Scripts\python.exe generate.py --prompt "a lighthouse at dusk, oil painting" --seed 42 --dtype float32 --offload model
```

Each run writes a PNG and JSON sidecar under `outputs/`. Failed or filtered runs write a JSON sidecar with an error code; a diagnostic PNG may also be saved. A black or safety-filtered PNG is not counted as a successful image. The JSON includes the request, model revision when available, environment versions, startup time (which may include a first download), inference time, peak allocated and reserved CUDA memory, and PNG SHA256. VAE and attention slicing are enabled for the 4 GB GPU.

For a reproducibility check, repeat the same command and compare the two SHA256 values. A CPU random generator controls initial noise, but exact matches across software versions or hardware are not guaranteed. `--warmup` performs a full untimed generation before measurement, so it takes additional time. Keep the safety checker enabled; if it flags content, inspect the JSON `nsfw_content_detected` field.
