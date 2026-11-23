# GenBench database — M2 preparation

The first schema uses **plain PostgreSQL**. It does not install pgvector or create RAG tables. The database acts as the job book: requests, lifecycle state, image file references, and measured inference results.

`migrations/001_image_jobs.sql` is prepared but not applied yet. Apply it only to a dedicated `genbench` database after the M0 valid-image gate and database credentials are configured. It creates tables in a `genbench` schema, leaving other databases and schemas alone.

The API will insert a `queued` row. One Python GPU worker will claim the oldest queued row inside a transaction using `FOR UPDATE SKIP LOCKED`, then update it to `running`. On completion it writes metrics and an image record, then marks the job `succeeded`; on failure it records a sanitized `error_code` and marks `failed`. A heartbeat allows recovery of interrupted `running` jobs.

The database stores a relative `storage_key`, not image bytes or a browser-visible absolute path. The API resolves that key under an approved output directory when streaming a completed image.

When the Knowledge Lab begins, a later migration can enable pgvector and add document and embedding tables to the same database.
