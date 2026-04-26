# Configuration

All configuration is driven by environment variables, loaded from `.env` (local) or the platform dashboard (Railway / Cloud Run). The single source of truth is `config.py`.

---

## Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VERTEX_PROJECT_ID` | Google Cloud project ID | `my-gcp-project-123` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key | `psychconnect-key.json` |
| `SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (full access) | `eyJhbGc...` |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VERTEX_LOCATION` | `global` | Vertex AI region |
| `HTP_MANUAL_PATH` | `resources/book_htp_combined.pdf` | Path to the HTP manual PDF |
| `HTP_MANUAL_GCS_URI` | *(empty)* | GCS URI for large manuals (`gs://bucket/file.pdf`) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | Comma-separated CORS origins |

## Model Configuration

| Constant | Default | Used In |
|----------|---------|---------|
| `FLASH_MODEL` | `gemini-2.5-flash` | Phase 1 + 2 |
| `PRO_MODEL` | `gemini-2.5-pro` | Phase 3 |

## Retry Policy

| Constant | Default | Description |
|----------|---------|-------------|
| `RETRY_MAX_ATTEMPTS` | `5` | Max retries per API call |
| `RETRY_BASE_DELAY` | `1.0s` | Initial delay |
| `RETRY_MAX_DELAY` | `60.0s` | Max delay cap |

Formula: `wait = min(BASE × 2^attempt + random(0,1), MAX_DELAY)`

## Context Caching

| Constant | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | `86400` (24h) | Cache persistence duration |
| `CACHE_MAX_INLINE_MB` | `10.0` | Max PDF size for inline caching |
| `MAX_IMAGE_SIZE_MB` | `10` | Max image upload size |

For manuals > 10 MB, upload to GCS and set `HTP_MANUAL_GCS_URI`.
