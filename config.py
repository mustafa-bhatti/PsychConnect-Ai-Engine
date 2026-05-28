"""
config.py — Single source of truth for all environment-driven configuration.

To change any setting:
  1. Edit the relevant variable in your .env file (or Railway / Cloud Run dashboard).
  2. Restart the service — everything picks it up automatically.
     No code changes required anywhere else.
"""

import os
from dotenv import load_dotenv

# Loads .env for local development.
# In production (Railway / Cloud Run) variables come from the platform environment.
load_dotenv()

# ── Google Cloud / Vertex AI ───────────────────────────────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION   = os.environ.get("VERTEX_LOCATION", "global")
CREDENTIALS_PATH  = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

# Support loading credentials from raw JSON string in env (for platforms like Railway)
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")
if not CREDENTIALS_PATH and GOOGLE_CREDS_JSON:
    import tempfile
    # Write credentials JSON string to a temporary file
    temp_creds_path = os.path.join(tempfile.gettempdir(), "google-credentials.json")
    with open(temp_creds_path, "w", encoding="utf-8") as f:
        f.write(GOOGLE_CREDS_JSON)
    CREDENTIALS_PATH = temp_creds_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_creds_path


# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL              = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET   = os.environ.get("SUPABASE_STORAGE_BUCKET", "assessments")

# ── Resources ──────────────────────────────────────────────────────────────────
HTP_MANUAL_PATH = os.environ.get("HTP_MANUAL_PATH", "resources/book_htp_combined.pdf")
HTP_MANUAL_GCS_URI = os.environ.get("HTP_MANUAL_GCS_URI", "")

# ── Server / CORS ──────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
MAX_IMAGE_SIZE_MB = 10

# ── Gemini model identifiers ───────────────────────────────────────────────────
# Flash: Phase 1 (feature extraction) + Phase 2 (interpretation) — fast, high quota.
# Pro  : Phase 3 (synthesis) only — deep reasoning, stricter quota.
FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL   = "gemini-2.5-pro"

# ── Retry policy (exponential back-off + random jitter on 429 / quota errors) ──
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY   = 1.0   # seconds — wait before first retry
RETRY_MAX_DELAY    = 60.0  # seconds — cap on any single wait

# ── Vertex AI Context Caching ──────────────────────────────────────────────────
# The HTP manual PDF is registered as a server-side cache at startup.
# Vertex AI charges the full input-token price once (to populate the cache),
# then only 10 % of the input-token price for every subsequent call that
# references it — a 90 % discount on manual tokens.
#
# Inline-byte limit: PDFs > CACHE_MAX_INLINE_MB must be uploaded to a GCS bucket
# and referenced with Part.from_uri() instead.  The pipeline handles this
# gracefully: if your manual exceeds the limit it falls back to sending the PDF
# inline with every request (original behaviour) and logs a warning.
CACHE_TTL_SECONDS   = 86_400  # 24 hours — survives a full working day
CACHE_MAX_INLINE_MB = 10.0