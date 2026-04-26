# Data Models

All data models are defined in `schemas.py` using Pydantic v2. The output follows a **two-layer design**:
- **Dashboard JSON** (`AssessmentResponse`) — Structured data for the psychologist UI
- **PDF Report** — Detailed clinical document uploaded to Supabase Storage

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

### `Severity`
```python
"low" | "moderate" | "high"
```

### `DrawingConsistency`
```python
"consistent" | "contradictory" | "neutral"
```

---

## Input Models

### `AssessmentRequest`
The payload sent to `POST /assess`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assessment_id` | `string` | Yes | UUID of the assessment in Supabase |

### `PatientContext`
Built internally from Supabase data:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `patient_id` | `string` | Yes | — | Platform UUID (audit log only) |
| `age` | `int` | Yes | 5–100 | Patient age in years |
| `gender` | `Gender` | Yes | Enum | Patient gender |
| `presenting_complaint` | `string` | Yes | min 10 chars | Main reason for seeking help |
| `relevant_history` | `string` | No | — | Brief clinical background |
| `referral_source` | `ReferralSource` | No | Enum | How patient was referred |
| `phq9_score` | `int` | No | 0–27 | PHQ-9 total score |
| `dass21` | `DASS21Scores` | No | — | DASS-21 subscale scores |

### `DASS21Scores`

| Field | Type | Constraints |
|-------|------|-------------|
| `depression` | `int` | 0–42 |
| `anxiety` | `int` | 0–42 |
| `stress` | `int` | 0–42 |

---

## Phase 1 Output

### `DrawingFeatures`
Structured output from Gemini Flash — enforced via `response_schema`:

| Field | Type | Description |
|-------|------|-------------|
| `drawing_type` | `string` | `"House"`, `"Tree"`, or `"Person"` |
| `line_quality` | `string` | Pressure and stroke description |
| `size` | `string` | `"Small"`, `"Average"`, or `"Large"` |
| `placement` | `string` | Position on the page |
| `omissions` | `list[str]` | Missing expected elements |
| `shading_areas` | `list[str]` | Areas with notable shading |
| `distortions` | `string` | Disproportionate or unusual elements |
| `key_details` | `list[str]` | Other notable features |
| `confidence_score` | `float` | 0.0–1.0 analysis clarity rating |
| `clinical_flags` | `list[str]` | Features needing urgent attention |

---

## Dashboard JSON — `AssessmentResponse`

The main output stored in `ai_report_json` in Supabase:

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | `string` | Patient UUID |
| `assessed_at` | `string` | ISO timestamp of assessment |
| `overall_confidence` | `float` | Average confidence across drawings |
| `summary` | `ReportSummary` | Clinical impression, themes, risk flags |
| `drawings` | `list[DrawingSummary]` | Per-drawing observation cards |
| `questionnaire_match` | `QuestionnaireSummary?` | Score correlation data |
| `session_focus_areas` | `list[str]` | 4–5 exploration prompts |
| `pdf_report_url` | `string?` | URL to the detailed PDF report |
| `processing_time_seconds` | `float` | Total pipeline execution time |
| `disclaimer` | `string` | Clinical disclaimer |

### `ReportSummary`

| Field | Type | Description |
|-------|------|-------------|
| `clinical_impression` | `string` | Overall psychological picture |
| `key_themes` | `list[ThemeItem]` | Cross-drawing themes with severity |
| `risk_flags` | `list[str]` | Urgent flags (red alerts) |

### `ThemeItem`

| Field | Type | Description |
|-------|------|-------------|
| `theme` | `string` | e.g. "Emotional Guardedness" |
| `evidence` | `string` | Specific features supporting this theme |
| `severity` | `string` | `"low"`, `"moderate"`, or `"high"` |

### `DrawingSummary`

| Field | Type | Description |
|-------|------|-------------|
| `drawing_type` | `string` | `"House"`, `"Tree"`, or `"Person"` |
| `confidence` | `float` | Phase 1 confidence score |
| `observations` | `list[Observation]` | Feature → interpretation pairs |

### `Observation`

| Field | Type | Description |
|-------|------|-------------|
| `feature` | `string` | What was observed (e.g. "Locked door") |
| `interpretation` | `string` | What it may suggest psychologically |

### `QuestionnaireSummary`

| Field | Type | Description |
|-------|------|-------------|
| `phq9` | `QuestionnaireScore?` | PHQ-9 correlation |
| `dass21_depression` | `QuestionnaireScore?` | DASS-21 Depression |
| `dass21_anxiety` | `QuestionnaireScore?` | DASS-21 Anxiety |
| `dass21_stress` | `QuestionnaireScore?` | DASS-21 Stress |

### `QuestionnaireScore`

| Field | Type | Description |
|-------|------|-------------|
| `score` | `int` | Raw score value |
| `severity` | `string` | Severity label |
| `drawing_consistency` | `string` | `"consistent"`, `"contradictory"`, or `"neutral"` |

---

## Frontend Usage Guide

### Rendering the Dashboard

```tsx
// Summary section — clinical impression card
<Card>{data.summary.clinical_impression}</Card>

// Risk flags — red alert banners at the top
{data.summary.risk_flags.map(flag => <Alert variant="destructive">{flag}</Alert>)}

// Key themes — severity cards
{data.summary.key_themes.map(theme => (
  <ThemeCard severity={theme.severity} title={theme.theme}>
    {theme.evidence}
  </ThemeCard>
))}

// Per-drawing cards with expandable observations
{data.drawings.map(drawing => (
  <DrawingCard type={drawing.drawing_type} confidence={drawing.confidence}>
    {drawing.observations.map(obs => (
      <ObservationRow feature={obs.feature} interpretation={obs.interpretation} />
    ))}
  </DrawingCard>
))}

// Questionnaire correlation badges
{data.questionnaire_match?.phq9 && (
  <Badge severity={data.questionnaire_match.phq9.severity}>
    PHQ-9: {data.questionnaire_match.phq9.score} — {data.questionnaire_match.phq9.drawing_consistency}
  </Badge>
)}

// Session focus areas checklist
{data.session_focus_areas.map((area, i) => <ChecklistItem key={i}>{area}</ChecklistItem>)}

// PDF download button
<Button href={data.pdf_report_url}>Download Full Report (PDF)</Button>
```
