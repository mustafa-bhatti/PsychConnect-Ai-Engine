# Data Models

All data models are defined in `schemas.py` using Pydantic v2. These enforce strict validation for both API inputs and Gemini AI outputs.

---

## Enums

### `Gender`
```python
"male" | "female" | "other" | "prefer_not_to_say"
```

### `ReferralSource`
```python
"self_referred" | "doctor" | "family" | "school" | "court" | "other"
```

---

## Input Models

### `AssessmentRequest`
The payload sent to `POST /assess`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assessment_id` | `string` | Yes | UUID of the assessment in Supabase |

### `PatientContext`
Built internally from Supabase data — never sent directly by the frontend:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `patient_id` | `string` | Yes | — | Platform UUID (audit log only, never in reports) |
| `age` | `int` | Yes | 5–100 | Patient age in years |
| `gender` | `Gender` | Yes | Enum | Patient gender |
| `presenting_complaint` | `string` | Yes | min 10 chars | Main reason for seeking help |
| `relevant_history` | `string` | No | — | Brief clinical background |
| `referral_source` | `ReferralSource` | No | Enum | How the patient was referred |
| `phq9_score` | `int` | No | 0–27 | PHQ-9 total score |
| `dass21` | `DASS21Scores` | No | — | DASS-21 subscale scores |

### `DASS21Scores`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `depression` | `int` | 0–42 | DASS-21 Depression subscale |
| `anxiety` | `int` | 0–42 | DASS-21 Anxiety subscale |
| `stress` | `int` | 0–42 | DASS-21 Stress subscale |

---

## Output Models

### `DrawingFeatures`
Structured output from Phase 1 (Gemini Flash). Schema is enforced via `response_schema`.

| Field | Type | Description |
|-------|------|-------------|
| `drawing_type` | `string` | `"House"`, `"Tree"`, `"Person"`, or `"PPAT"` |
| `line_quality` | `string` | Pressure and stroke description |
| `size` | `string` | `"Small"`, `"Average"`, or `"Large"` relative to page |
| `placement` | `string` | Position on the page |
| `omissions` | `list[str]` | Missing expected elements |
| `shading_areas` | `list[str]` | Areas with notable shading |
| `distortions` | `string` | Disproportionate or unusual elements |
| `key_details` | `list[str]` | Other clinically notable features |
| `confidence_score` | `float` | 0.0–1.0 analysis clarity rating |
| `clinical_flags` | `list[str]` | Features needing urgent attention |

### `IndividualReport`

| Field | Type | Description |
|-------|------|-------------|
| `drawing_type` | `string` | Drawing identifier |
| `features` | `DrawingFeatures` | Phase 1 extraction output |
| `interpretation` | `string` | Phase 2 clinical interpretation text |

### `AssessmentResponse`
The full result written to `ai_report_json` in Supabase:

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | `string` | Patient UUID |
| `disclaimer` | `string` | Clinical disclaimer (always present) |
| `house_report` | `IndividualReport` | House drawing analysis |
| `tree_report` | `IndividualReport` | Tree drawing analysis |
| `person_report` | `IndividualReport` | Person drawing analysis |
| `ppat_report` | `IndividualReport?` | PPAT analysis (optional) |
| `synthesis_report` | `string` | Integrated clinical synthesis |
| `overall_confidence` | `float` | Average confidence across drawings |
| `low_confidence_warning` | `bool` | `true` if any drawing < 0.50 confidence |
| `processing_time_seconds` | `float` | Total pipeline execution time |

### `ErrorResponse`

| Field | Type | Description |
|-------|------|-------------|
| `error` | `string` | Error message |
| `detail` | `string?` | Additional context |

---

## Database Tables

The AI Engine reads from and writes to these Supabase tables:

### `assessments`

| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` (PK) | Assessment identifier |
| `patient_id` | `uuid` (FK → patients) | Patient reference |
| `type` | `text` | Assessment type |
| `status` | `htp_status` | `pending` → `completed` / `failed` |
| `house_drawing_url` | `text` | Supabase Storage URL |
| `tree_drawing_url` | `text` | Supabase Storage URL |
| `person_drawing_url` | `text` | Supabase Storage URL |
| `questionnaire_scores` | `jsonb` | PHQ-9, DASS-21, presenting complaint |
| `ai_report_json` | `jsonb` | Full `AssessmentResponse` output |
| `ai_confidence_score` | `float` | Overall confidence |
| `pdf_report_url` | `text` | Generated PDF report URL |
| `created_at` | `timestamptz` | Creation timestamp |

### `patients`

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | `uuid` (PK, FK → profiles) | Patient identifier |
| `date_of_birth` | `date` | Used to calculate age |
| `gender` | `text` | Mapped to `Gender` enum |
| `medical_history` | `text` | Becomes `relevant_history` |

See `.github/SCHEMA.md` for the complete database schema including all tables.
