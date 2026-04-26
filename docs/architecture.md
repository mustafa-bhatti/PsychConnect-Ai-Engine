# Architecture

This document describes the system architecture, pipeline design, and key technical decisions behind the PsychConnect AI Engine.

---

## System Overview

The AI Engine is a **FastAPI microservice** that receives assessment requests from the PsychConnect Next.js frontend. It downloads patient drawings from Supabase Storage, runs them through a multi-phase Gemini AI pipeline, and writes the clinical report back to the database.

```
┌─────────────────────┐       POST /assess        ┌──────────────────────────┐
│                     │ ─────────────────────────► │                          │
│  PsychConnect       │   { assessment_id }        │  AI Engine (FastAPI)     │
│  Next.js Frontend   │                            │                          │
│                     │ ◄───────────────────────── │  ┌──────────────────┐    │
└─────────────────────┘   202 Accepted             │  │ Background Worker│    │
                                                   │  │  (asyncio queue) │    │
                                                   │  └────────┬─────────┘    │
                                                   │           │              │
                                                   │           ▼              │
                                                   │  ┌──────────────────┐    │
                                                   │  │  HTP Pipeline    │    │
                                                   │  │  (pipeline.py)   │    │
                                                   │  └────────┬─────────┘    │
                                                   └───────────┼──────────────┘
                                                               │
                         ┌─────────────────────────────────────┼──────────┐
                         │                                     │          │
                         ▼                                     ▼          ▼
                ┌─────────────────┐                 ┌──────────────┐  ┌────────┐
                │  Supabase       │                 │  Vertex AI   │  │  GCS   │
                │  (PostgreSQL +  │                 │  (Gemini     │  │ Bucket │
                │   Storage)      │                 │   Flash/Pro) │  │(manual)│
                └─────────────────┘                 └──────────────┘  └────────┘
```

---

## Request Lifecycle

1. **Frontend** creates an `assessments` row in Supabase (status: `pending`) with drawing URLs
2. **Frontend** sends `POST /assess` with the `assessment_id`
3. **AI Engine** returns `202 Accepted` immediately and enqueues the assessment
4. **Background Worker** picks up the assessment from the queue
5. Worker **fetches** the assessment row + patient data from Supabase
6. Worker **downloads** the drawing images from Supabase Storage (authenticated)
7. Worker runs the **3-phase HTP Pipeline**
8. Worker **updates** the assessment row with `ai_report_json` and `status: completed`
9. On failure, worker sets `status: failed`

---

## Pipeline Phases

The pipeline is designed for **maximum parallelism** and **cost efficiency**.

### Phase 1 — Feature Extraction (Parallel)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Flash |
| **Input** | Drawing image only (no manual) |
| **Output** | Structured JSON (`DrawingFeatures`) |
| **Temperature** | 0.0 (deterministic) |
| **Parallelism** | All 3-4 drawings processed simultaneously |

Gemini Flash extracts raw visual features from each drawing: line quality, size, placement, omissions, shading, distortions, and clinical flags. The output schema is enforced via Gemini's `response_schema` parameter — no manual JSON parsing required.

**Why no manual in Phase 1?** Feature extraction is purely observational. Sending the manual here would add cost without benefit, since interpretation happens in Phase 2.

### Phase 2 — Individual Interpretation (Parallel)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Flash |
| **Input** | Drawing image + extracted features + HTP manual (via context cache) |
| **Output** | Structured clinical text report |
| **Temperature** | 0.2 (slight creativity for interpretive language) |
| **Parallelism** | All 3-4 drawings processed simultaneously |

Each drawing gets its own clinical interpretation report, grounded in the HTP manual and the patient's demographic context. The manual is served from a Vertex AI **context cache** to save ~90% on input token costs.

### Phase 3 — Synthesis (Sequential)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Pro |
| **Input** | All drawing images + all Phase 2 reports + HTP manual (via context cache) |
| **Output** | Integrated clinical synthesis report |
| **Temperature** | 0.2 |
| **Parallelism** | Single call (needs all Phase 2 outputs) |

The Pro model synthesizes all individual reports into a comprehensive integrated assessment, cross-referencing findings across drawings and correlating with questionnaire scores (PHQ-9, DASS-21) when available.

### Performance

```
Sequential approach:  7× single-call latency  (old)
Current approach:     ~3× single-call latency  (Phases 1+2 parallelized)
```

---

## Context Caching Strategy

The HTP manual PDF (~19 MB) is registered as a **Vertex AI Context Cache** at startup.

### How It Works

1. On startup, the pipeline creates two caches:
   - **Flash cache** — for Phase 2 (interpretation)
   - **Pro cache** — for Phase 3 (synthesis)
2. Each cache stores the full manual PDF server-side on Google's infrastructure
3. Subsequent API calls reference the cache by name instead of re-uploading the PDF
4. Vertex AI charges **10% of input-token price** for cached content (90% discount)

### Cache Lifecycle

| Parameter | Value |
|-----------|-------|
| TTL | 24 hours (`CACHE_TTL_SECONDS = 86400`) |
| Max inline size | 10 MB (`CACHE_MAX_INLINE_MB`) |
| GCS fallback | Set `HTP_MANUAL_GCS_URI` for manuals > 10 MB |

### Deduplication

Before creating a new cache, the pipeline lists existing caches and reuses any with a matching `display_name`. This prevents duplicate caches from accumulating across restarts.

### Graceful Fallback

If cache creation fails (quota, permissions, region issues), the pipeline falls back to sending the manual PDF inline with every request. This is slower and more expensive but fully functional.

---

## Background Worker

The service uses a single `asyncio.Queue` + worker pattern:

```python
assessment_queue: asyncio.Queue = asyncio.Queue()

async def assessment_worker():
    while True:
        assessment_id = await assessment_queue.get()
        await process_assessment_task(assessment_id)
        assessment_queue.task_done()
```

### Design Decisions

- **Sequential processing** — Assessments are processed one at a time to avoid overwhelming Vertex AI quotas
- **Fire-and-forget** — The `/assess` endpoint returns `202 Accepted` immediately
- **Error isolation** — A failed assessment doesn't block the queue; the worker catches all exceptions and updates the database
- **Queue size monitoring** — The `/health` endpoint reports current queue size

---

## Retry Strategy

All Gemini API calls use exponential backoff with jitter:

```
wait = min(BASE_DELAY × 2^attempt + random(0, 1), MAX_DELAY)
```

| Parameter | Value |
|-----------|-------|
| Max attempts | 5 |
| Base delay | 1.0s |
| Max delay | 60.0s |
| Timeout per call | 200s |

**Only** `429` / `RESOURCE_EXHAUSTED` quota errors trigger retries. All other exceptions propagate immediately.

---

## Security

### Image Downloads

Drawing images are stored in Supabase Storage. Even if a bucket is accidentally set to Private, the service rewrites public URLs to authenticated endpoints and passes the `SUPABASE_SERVICE_ROLE_KEY`:

```python
secure_url = url.replace("/object/public/", "/object/authenticated/")
headers = {
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
}
```

### Patient Privacy

- `patient_id` is used for audit logging and database joins only
- It is **never** included in the body of clinical reports (Clinical Rule 7)
- Patient names are never sent to the AI pipeline
