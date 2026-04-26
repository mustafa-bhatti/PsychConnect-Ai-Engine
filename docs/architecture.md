# Architecture

This document describes the system architecture, pipeline design, and key technical decisions behind the PsychConnect AI Engine.

---

## System Overview

The AI Engine is a **FastAPI microservice** that receives assessment requests from the PsychConnect Next.js frontend. It downloads patient drawings from Supabase Storage, runs them through a multi-phase Gemini AI pipeline, generates a branded PDF report, and writes the structured results back to the database.

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
                                                   │           │              │
                                                   │           ▼              │
                                                   │  ┌──────────────────┐    │
                                                   │  │  PDF Generator   │    │
                                                   │  │  (pdf_report.py) │    │
                                                   │  └──────────────────┘    │
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

## Two-Layer Output Design

The pipeline produces **two distinct outputs**:

| Layer | Format | Purpose | Storage |
|-------|--------|---------|---------|
| **Dashboard JSON** | Structured JSON | Quick-glance insights on psychologist dashboard | `ai_report_json` column |
| **PDF Report** | Branded PDF | Detailed clinical document for download/records | Supabase Storage → `pdf_report_url` |

---

## Request Lifecycle

1. **Frontend** creates an `assessments` row in Supabase (status: `pending`) with drawing URLs
2. **Frontend** sends `POST /assess` with the `assessment_id`
3. **AI Engine** returns `202 Accepted` immediately and enqueues the assessment
4. **Background Worker** picks up the assessment from the queue
5. Worker **fetches** the assessment row + patient data from Supabase
6. Worker **downloads** the drawing images from Supabase Storage (authenticated)
7. Worker runs the **3-phase HTP Pipeline**
8. Worker **generates a PDF report** from the pipeline outputs
9. Worker **uploads the PDF** to Supabase Storage
10. Worker **updates** the assessment row with `ai_report_json`, `pdf_report_url`, and `status: completed`

---

## Pipeline Phases

### Phase 1 — Feature Extraction (Parallel)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Flash |
| **Input** | Drawing image only (no manual) |
| **Output** | Structured JSON (`DrawingFeatures`) |
| **Temperature** | 0.0 (deterministic) |
| **Parallelism** | All 3 drawings processed simultaneously |

Gemini Flash extracts raw visual features from each drawing. The output schema is enforced via Gemini's `response_schema` parameter.

### Phase 2 — Individual Interpretation (Parallel)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Flash |
| **Input** | Drawing image + extracted features + HTP manual (via context cache) |
| **Output** | Clinical interpretation text (observations + themes + follow-up questions) |
| **Temperature** | 0.2 |
| **Parallelism** | All 3 drawings processed simultaneously |

Phase 2 output serves **dual purpose**:
- Used by Phase 3 to distill structured dashboard JSON
- Included in the PDF report as detailed interpretation text

### Phase 3 — Synthesis (Structured JSON)

| Attribute | Value |
|-----------|-------|
| **Model** | Gemini 2.5 Pro |
| **Input** | All drawing images + all Phase 2 reports + HTP manual (via context cache) |
| **Output** | Structured JSON for dashboard (themes, observations, questionnaire correlation) |
| **Temperature** | 0.2 |
| **Schema enforcement** | `response_mime_type="application/json"` |

### PDF Generation (Local)

| Attribute | Value |
|-----------|-------|
| **Library** | fpdf2 (pure Python) |
| **Input** | Phase 2 reports + Phase 3 synthesis + patient context |
| **Output** | Branded clinical PDF (~5-10 pages) |
| **Time** | ~1-2 seconds (no external API call) |

---

## Context Caching Strategy

The HTP manual PDF (~19 MB) is registered as a **Vertex AI Context Cache** at startup, providing a 90% discount on manual input tokens.

| Parameter | Value |
|-----------|-------|
| TTL | 24 hours |
| Flash cache | Phase 2 (interpretation) |
| Pro cache | Phase 3 (synthesis) |

Caches are deduplicated by `display_name` to prevent accumulation across restarts. Falls back gracefully to inline sending if caching fails.

---

## Background Worker

Sequential processing via `asyncio.Queue` to avoid overwhelming Vertex AI quotas:

- **Fire-and-forget** — `/assess` returns `202 Accepted` immediately
- **Error isolation** — Failed assessments don't block the queue
- **Queue monitoring** — `/health` reports current queue size

---

## Retry Strategy

All Gemini API calls use exponential backoff: `wait = min(1.0 × 2^attempt + jitter, 60.0)`

Only `429` / `RESOURCE_EXHAUSTED` errors trigger retries (max 5 attempts).
