# API Reference

The AI Engine exposes a minimal REST API via FastAPI. Interactive docs are available at `/docs` (Swagger UI) and `/redoc` when the server is running.

**Base URL:** `http://localhost:8000` (local) or your deployed domain.

---

## Endpoints

### `GET /health`

Health check endpoint for monitoring and load balancers.

**Tags:** `System`

#### Response `200 OK`

```json
{
  "status": "ok",
  "service": "htp-assessment",
  "version": "2.1.0",
  "queue_size": 0
}
```

#### Response `503 Service Unavailable`

Returned if the pipeline or Supabase client has not been initialized (e.g., during startup or after a critical failure).

```json
{
  "detail": "Service not initialised."
}
```

---

### `POST /assess`

Enqueues a full HTP assessment for background processing.

**Tags:** `Assessment`

#### Request Body

**Content-Type:** `application/json`

```json
{
  "assessment_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assessment_id` | `string` (UUID) | Yes | The unique ID of the assessment row in the Supabase `assessments` table |

> **Note:** The assessment row must already exist in Supabase with `house_drawing_url`, `tree_drawing_url`, and `person_drawing_url` populated before calling this endpoint.

#### Response `202 Accepted`

```json
{
  "message": "Assessment processing started."
}
```

The assessment is queued for background processing. The frontend should poll the `assessments` table for status changes:

| Status | Meaning |
|--------|---------|
| `pending` | Assessment created, not yet sent to AI Engine |
| `processing` | Assessment is being processed (set by frontend before calling) |
| `completed` | AI report is ready in `ai_report_json` |
| `failed` | Pipeline failed — check server logs |

#### Response `503 Service Unavailable`

```json
{
  "error": "Service not initialised.",
  "detail": null
}
```

---

## Assessment Result Schema

When processing completes, the worker writes the following JSON structure to the `ai_report_json` column:

```json
{
  "patient_id": "uuid-string",
  "disclaimer": "DISCLAIMER: This AI-generated report is an assistive tool...",
  "house_report": {
    "drawing_type": "House",
    "features": { /* DrawingFeatures */ },
    "interpretation": "ANALYSIS OF HOUSE\n\nDISCLAIMER: ..."
  },
  "tree_report": {
    "drawing_type": "Tree",
    "features": { /* DrawingFeatures */ },
    "interpretation": "ANALYSIS OF TREE\n\nDISCLAIMER: ..."
  },
  "person_report": {
    "drawing_type": "Person",
    "features": { /* DrawingFeatures */ },
    "interpretation": "ANALYSIS OF PERSON\n\nDISCLAIMER: ..."
  },
  "ppat_report": null,
  "synthesis_report": "INTEGRATED CLINICAL SYNTHESIS — HTP ASSESSMENT\n\n...",
  "overall_confidence": 0.87,
  "low_confidence_warning": false,
  "processing_time_seconds": 45.23
}
```

See [Data Models](./data-models.md) for the full schema definitions.

---

## Calling from Next.js

### Server Action / API Route Example

```typescript
// lib/htp.ts
export async function triggerHTPAssessment(assessmentId: string) {
  const res = await fetch(`${process.env.HTP_SERVICE_URL}/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assessment_id: assessmentId }),
  });

  if (!res.ok) {
    throw new Error(`HTP Engine error: ${res.status} ${await res.text()}`);
  }

  return res.json(); // { message: "Assessment processing started." }
}
```

### Environment Variable

Add to your Next.js `.env.local`:

```env
# Local development
HTP_SERVICE_URL=http://localhost:8000

# Production (Railway)
HTP_SERVICE_URL=https://your-service.up.railway.app
```

### Polling for Results

After calling `/assess`, poll the Supabase `assessments` table:

```typescript
import { createClient } from "@/lib/supabase/client";

async function pollAssessmentResult(assessmentId: string) {
  const supabase = createClient();

  const checkStatus = async (): Promise<any> => {
    const { data, error } = await supabase
      .from("assessments")
      .select("status, ai_report_json")
      .eq("id", assessmentId)
      .single();

    if (error) throw error;

    if (data.status === "completed") {
      return data.ai_report_json;
    }

    if (data.status === "failed") {
      throw new Error("Assessment processing failed");
    }

    // Still processing — wait and retry
    await new Promise((resolve) => setTimeout(resolve, 5000));
    return checkStatus();
  };

  return checkStatus();
}
```

---

## CORS Configuration

The service accepts requests from origins listed in the `ALLOWED_ORIGINS` environment variable (comma-separated). Default: `http://localhost:3000,http://127.0.0.1:3000`.

Allowed methods: `GET`, `POST`

---

## Error Handling

All errors follow this structure:

```json
{
  "error": "Human-readable error message",
  "detail": "Optional additional context"
}
```

| Status Code | Meaning |
|-------------|---------|
| `202` | Assessment enqueued successfully |
| `422` | Validation error (invalid `assessment_id` format) |
| `503` | Service not initialized |
