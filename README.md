# PsychConnect — HTP Assessment Microservice

AI-assisted House-Tree-Person projective drawing analysis, built as a
FastAPI microservice for the PsychConnect telepsychology platform.

> **Clinical Notice**: All outputs are AI-assistive tools for licensed
> psychologists only. This service never provides autonomous diagnoses.

## 📖 Documentation

Full documentation is available in the [`docs/`](./docs/) folder:

| Document | Description |
|----------|-------------|
| [Getting Started](./docs/getting-started.md) | Installation, setup, and first run |
| [Architecture](./docs/architecture.md) | System design, pipeline phases, and data flow |
| [API Reference](./docs/api-reference.md) | HTTP endpoints and response schemas |
| [Configuration](./docs/configuration.md) | Environment variables and tuning |
| [Data Models](./docs/data-models.md) | Pydantic schemas and database tables |
| [Clinical Rules](./docs/clinical-rules.md) | The 9 clinical safety rules |
| [Prompt Engineering](./docs/prompt-engineering.md) | How AI prompts are structured |
| [Deployment](./docs/deployment.md) | Docker, Railway, and Cloud Run guides |
| [Testing](./docs/testing.md) | Local testing and validation |
| [Contributing](./docs/contributing.md) | Code standards and PR workflow |

---

## Project Structure

```
htp_service/
├── main.py            ← FastAPI app + all HTTP endpoints
├── pipeline.py        ← Core async pipeline (Gemini Flash + Pro)
├── schemas.py         ← Pydantic models (request / response)
├── prompts.py         ← All system prompts and clinical rules
├── test_local.py      ← Local end-to-end test (no server needed)
├── requirements.txt
├── Dockerfile
├── Procfile           ← Railway deployment
├── .env.example       ← Copy to .env and fill in values
└── resources/
    ├── book_htp.pdf   ← HTP manual (place here)
    ├── test_house.png ← Test images (for test_local.py)
    ├── test_tree.png
    └── test_person.png
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
```

### 3. Place resources

- Put your HTP manual PDF at: `resources/book_htp.pdf`
- For local testing, put 3 test drawing images in `resources/`

---

## Running

### Local development

```bash
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:3000/docs  
Health check: http://localhost:8000/health

### Local test (no server needed)

```bash
python test_local.py
```

### Docker

```bash
docker build -t htp-service .
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=your_key \
  -v $(pwd)/resources:/app/resources \
  htp-service
```

### Railway deployment

1. Push this folder to a GitHub repo
2. Create a new Railway project → Deploy from GitHub
3. Set environment variables in Railway dashboard:
   - `GOOGLE_API_KEY`
   - `ALLOWED_ORIGINS` (your Next.js domain)
4. Railway auto-detects the `Procfile`

---

## API Reference

### `POST /assess`

Runs the full HTP assessment.

**Content-Type**: `multipart/form-data`

| Field                  | Type        | Required | Description                                         |
|------------------------|-------------|----------|-----------------------------------------------------|
| `patient_context_json` | string      | Yes      | JSON string of patient context (see schema below)   |
| `house_image`          | file        | Yes      | House drawing (JPEG / PNG / WEBP, max 10 MB)        |
| `tree_image`           | file        | Yes      | Tree drawing                                        |
| `person_image`         | file        | Yes      | Person drawing                                      |
| `ppat_image`           | file        | No       | PPAT drawing (optional)                             |

**`patient_context_json` fields:**

```json
{
  "patient_id": "uuid-from-your-platform",
  "age": 28,
  "gender": "female",
  "presenting_complaint": "Persistent low mood for 3 months",
  "relevant_history": "No prior treatment. Stressful work environment.",
  "referral_source": "self_referred",
  "phq9_score": 14,
  "dass21": {
    "depression": 18,
    "anxiety": 12,
    "stress": 20
  }
}
```

`gender` options: `"male"`, `"female"`, `"other"`, `"prefer_not_to_say"`
`referral_source` options: `"self_referred"`, `"doctor"`, `"family"`, `"school"`, `"court"`, `"other"`

---

## Calling from Next.js

```typescript
// lib/htp.ts
export async function runHTPAssessment(
  patientContext: PatientContext,
  houseFile: File,
  treeFile: File,
  personFile: File,
  ppatFile?: File,
) {
  const form = new FormData();
  form.append("patient_context_json", JSON.stringify(patientContext));
  form.append("house_image", houseFile);
  form.append("tree_image", treeFile);
  form.append("person_image", personFile);
  if (ppatFile) form.append("ppat_image", ppatFile);

  const res = await fetch(`${process.env.HTP_SERVICE_URL}/assess`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();  // AssessmentResponse
}
```

Add to your `.env.local`:
```
HTP_SERVICE_URL=http://localhost:8000       # local dev
HTP_SERVICE_URL=https://your-service.railway.app   # production
```

---

## Architecture

```
Next.js frontend
      │
      │  POST /assess  (multipart/form-data)
      ▼
FastAPI  (main.py)
      │
      ▼
HTPPipeline  (pipeline.py)
      │
      ├─ Phase 1: asyncio.gather ──────────────────────────────────────────┐
      │   ├── Gemini Flash → extract House features  (structured JSON)     │
      │   ├── Gemini Flash → extract Tree features   (structured JSON)     │
      │   └── Gemini Flash → extract Person features (structured JSON)     │
      │                                                                    │
      ├─ Phase 2: asyncio.gather ──────────────────────────────────────────┤
      │   ├── Gemini Pro  → interpret House  (manual + image + features)   │
      │   ├── Gemini Pro  → interpret Tree   (manual + image + features)   │
      │   └── Gemini Pro  → interpret Person (manual + image + features)   │
      │                                                                    │
      └─ Phase 3: single call ─────────────────────────────────────────────┘
          Gemini Pro → synthesise (manual + ALL images + ALL reports)
                │
                ▼
          AssessmentResponse  (JSON)
```

**Manual handling**: The HTP manual PDF is loaded into RAM once at startup
and passed in full to every Gemini call. No RAG, no chunking, no FAISS.

**Speed**: Phases 1 and 2 are fully parallelised with `asyncio.gather`.
Total time ≈ 3× single-call latency instead of 7× (old sequential approach).

---

## Clinical Rules Summary

All prompts enforce the following rules (see `prompts.py` for full text):

1. Only use the HTP manual as interpretive context
2. Never diagnose
3. Use cautious language throughout ("may suggest...", "often associated with...")
4. Anchor every claim to a specific observed visual feature
5. Always include a Limitations section
6. Flag Western-normative interpretations requiring cultural verification (Pakistan context)
7. Never include patient_id or name in the report body
8. Never provide treatment recommendations
9. Begin every report with the clinical disclaimer
