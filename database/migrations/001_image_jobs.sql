-- GenBench M2: plain PostgreSQL schema for one local image-generation worker.
-- Apply to a dedicated genbench database. No pgvector extension is required.

BEGIN;

CREATE SCHEMA IF NOT EXISTS genbench;

CREATE TABLE IF NOT EXISTS genbench.generation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    prompt text NOT NULL CHECK (char_length(btrim(prompt)) BETWEEN 1 AND 500),
    negative_prompt text NOT NULL DEFAULT '',
    seed bigint NOT NULL CHECK (seed >= 0),
    steps smallint NOT NULL CHECK (steps BETWEEN 1 AND 100),
    guidance_scale numeric(5, 2) NOT NULL CHECK (guidance_scale BETWEEN 0 AND 20),
    width smallint NOT NULL CHECK (width BETWEEN 256 AND 768 AND width % 8 = 0),
    height smallint NOT NULL CHECK (height BETWEEN 256 AND 768 AND height % 8 = 0),
    model_id text NOT NULL,
    model_revision text,
    dtype text NOT NULL CHECK (dtype IN ('float16', 'float32')),
    offload_mode text NOT NULL CHECK (offload_mode IN ('none', 'model')),
    progress smallint NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    attempt_count smallint NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    worker_id text,
    heartbeat_at timestamptz,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    CHECK (status <> 'queued' OR (started_at IS NULL AND finished_at IS NULL)),
    CHECK (status <> 'running' OR started_at IS NOT NULL),
    CHECK (status NOT IN ('succeeded', 'failed') OR finished_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS generation_jobs_queue_idx
    ON genbench.generation_jobs (created_at, id)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS generation_jobs_history_idx
    ON genbench.generation_jobs (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS generation_jobs_running_heartbeat_idx
    ON genbench.generation_jobs (heartbeat_at)
    WHERE status = 'running';

CREATE TABLE IF NOT EXISTS genbench.generated_images (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL UNIQUE REFERENCES genbench.generation_jobs(id) ON DELETE CASCADE,
    storage_key text NOT NULL UNIQUE,
    format text NOT NULL DEFAULT 'png' CHECK (format = 'png'),
    width smallint NOT NULL CHECK (width > 0),
    height smallint NOT NULL CHECK (height > 0),
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (storage_key !~ '(^/|^[A-Za-z]:|\.\.)')
);

CREATE TABLE IF NOT EXISTS genbench.generation_metrics (
    job_id uuid PRIMARY KEY REFERENCES genbench.generation_jobs(id) ON DELETE CASCADE,
    model_setup_ms numeric(14, 2) CHECK (model_setup_ms >= 0),
    model_setup_may_include_download boolean NOT NULL DEFAULT false,
    warmup_ms numeric(14, 2) CHECK (warmup_ms >= 0),
    inference_ms numeric(14, 2) CHECK (inference_ms >= 0),
    image_save_ms numeric(14, 2) CHECK (image_save_ms >= 0),
    gpu_peak_allocated_mib numeric(12, 2) CHECK (gpu_peak_allocated_mib >= 0),
    gpu_peak_reserved_mib numeric(12, 2) CHECK (gpu_peak_reserved_mib >= 0),
    gpu_name text,
    torch_version text,
    torch_cuda_version text,
    diffusers_version text,
    python_version text,
    nsfw_content_detected boolean,
    all_black_image boolean,
    runtime_warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    measured_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(runtime_warnings) = 'array')
);

COMMIT;
