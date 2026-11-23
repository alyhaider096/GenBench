"""Generate an SD 1.5 image and record reproducible inference measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


DEFAULT_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Text prompt (1–500 characters)")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--guidance-scale", type=float, default=7.5)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--dtype", choices=("float16", "float32"), default="float16")
    parser.add_argument("--offload", choices=("none", "model"), default="none")
    parser.add_argument("--warmup", action="store_true", help="Run one untimed generation first")
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "outputs")
    args = parser.parse_args()
    if not 1 <= len(args.prompt.strip()) <= 500:
        parser.error("--prompt must contain 1–500 non-whitespace characters")
    if not 0 <= args.seed < 2**63:
        parser.error("--seed must be between 0 and 2^63-1")
    if not 1 <= args.steps <= 100:
        parser.error("--steps must be between 1 and 100")
    if not 0 <= args.guidance_scale <= 20:
        parser.error("--guidance-scale must be between 0 and 20")
    for name in ("width", "height"):
        value = getattr(args, name)
        if not 256 <= value <= 768 or value % 8:
            parser.error(f"--{name} must be a multiple of 8 between 256 and 768")
    return args


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def main() -> int:
    args = arguments()
    try:
        import torch
        from diffusers import StableDiffusionPipeline
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Install requirements.txt and CUDA PyTorch.", file=sys.stderr)
        return 2

    if not torch.cuda.is_available():
        print("CUDA is unavailable. Check the NVIDIA driver and CUDA-enabled PyTorch installation.", file=sys.stderr)
        return 2

    dtype = torch.float16 if args.dtype == "float16" else torch.float32
    request = {
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "seed": args.seed,
        "steps": args.steps,
        "guidance_scale": args.guidance_scale,
        "width": args.width,
        "height": args.height,
        "model_id": args.model_id,
        "dtype": args.dtype,
        "offload": args.offload,
        "warmup": args.warmup,
    }
    metadata = {
        "request": request,
        "environment": {
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_total_vram_mb": round(torch.cuda.get_device_properties(0).total_memory / 2**20, 2),
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "diffusers_version": package_version("diffusers"),
            "transformers_version": package_version("transformers"),
            "accelerate_version": package_version("accelerate"),
            "python_version": sys.version.split()[0],
        },
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_seed{args.seed}_steps{args.steps}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.output_dir / f"{stem}.png"
    json_path = args.output_dir / f"{stem}.json"

    try:
        load_start = time.perf_counter()
        load_options = {"dtype": dtype, "use_safetensors": True}
        if args.dtype == "float16":
            load_options["variant"] = "fp16"
        pipe = StableDiffusionPipeline.from_pretrained(args.model_id, **load_options)
        pipe.enable_vae_slicing()
        pipe.enable_attention_slicing()
        if args.offload == "model":
            pipe.enable_model_cpu_offload()
        else:
            pipe.to("cuda")
        torch.cuda.synchronize()
        metadata["cold_load_ms"] = round((time.perf_counter() - load_start) * 1000, 2)
        metadata["model_revision"] = getattr(pipe.config, "_commit_hash", None)

        def generate():
            # Recreate the CPU generator so warmup does not consume the measured seed.
            generator = torch.Generator(device="cpu").manual_seed(args.seed)
            return pipe(
                prompt=args.prompt,
                negative_prompt=args.negative_prompt or None,
                num_inference_steps=args.steps,
                guidance_scale=args.guidance_scale,
                width=args.width,
                height=args.height,
                generator=generator,
            )

        if args.warmup:
            print("Running untimed warmup...", flush=True)
            generate()
            torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always", RuntimeWarning)
            result = generate()
        torch.cuda.synchronize()
        metadata["inference_ms"] = round((time.perf_counter() - started) * 1000, 2)
        metadata["gpu_peak_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 2)
        metadata["gpu_peak_reserved_mb"] = round(torch.cuda.max_memory_reserved() / 2**20, 2)
        metadata["nsfw_content_detected"] = result.nsfw_content_detected
        metadata["runtime_warnings"] = [str(w.message) for w in captured_warnings]
        image = result.images[0]
        image.save(image_path)
        metadata["image_sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        metadata["image_file"] = image_path.name
        extrema = image.convert("RGB").getextrema()
        metadata["all_black_image"] = all(high == 0 for _, high in extrema)
        if result.nsfw_content_detected and any(result.nsfw_content_detected):
            metadata["status"] = "failed"
            metadata["error_code"] = "SAFETY_FILTERED"
            print("The safety checker filtered this output; inspect the warnings and try a different benign prompt/seed.", file=sys.stderr)
        elif metadata["all_black_image"]:
            metadata["status"] = "failed"
            metadata["error_code"] = "BLACK_IMAGE"
            print("The model returned an all-black image; try float32 with model offloading.", file=sys.stderr)
        elif any("invalid value" in warning.lower() for warning in metadata["runtime_warnings"]):
            metadata["status"] = "failed"
            metadata["error_code"] = "NUMERICAL_WARNING"
            print("Image generation produced a numerical warning; the output needs inspection.", file=sys.stderr)
        else:
            metadata["status"] = "succeeded"
    except torch.cuda.OutOfMemoryError:
        metadata["status"] = "failed"
        metadata["error_code"] = "CUDA_OUT_OF_MEMORY"
        print("CUDA out of memory. Retry with --offload model, or smaller --width/--height.", file=sys.stderr)
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error_code"] = type(exc).__name__
        metadata["error_message"] = str(exc)[:500]
        print(f"Generation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        json_path.write_text(json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Metadata: {json_path}")

    if metadata["status"] != "succeeded":
        return 1
    print(f"Image: {image_path}")
    print(f"Inference: {metadata['inference_ms']} ms")
    print(f"Peak GPU allocated/reserved: {metadata['gpu_peak_allocated_mb']} / {metadata['gpu_peak_reserved_mb']} MiB")
    print(f"SHA256: {metadata['image_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
