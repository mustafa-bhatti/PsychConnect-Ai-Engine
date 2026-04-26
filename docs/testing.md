# Testing

This document covers how to test the PsychConnect AI Engine locally.

---

## Local Pipeline Test

The `test_local.py` script runs the complete 3-phase pipeline without a server:

```bash
python test_local.py
```

### Prerequisites

1. All environment variables configured in `.env`
2. HTP manual PDF in `resources/book_htp_combined.pdf`
3. Test drawing images in `resources/`:
   - `test_house.png`
   - `test_tree.png`
   - `test_person.png`

### What It Does

1. Validates all required files exist
2. Initializes the `HTPPipeline` (including context caches)
3. Runs a full assessment with a predefined test patient
4. Prints the synthesis report to stdout
5. Saves the complete result to `test_output.json`

### Test Patient

The test uses a hardcoded patient context:

```python
PatientContext(
    patient_id           = "test-patient-001",
    age                  = 26,
    gender               = Gender.male,
    presenting_complaint = "Chronic fatigue, diffuse anxiety, low frustration thresholds",
    relevant_history     = "26-year-old male. Prone to seeking satisfaction in fantasy.",
    phq9_score           = 11,
    dass21               = DASS21Scores(depression=14, anxiety=18, stress=22),
)
```

### Expected Output

```
🚀 Initializing PsychConnect Pipeline
────────────────────────────────
Project ID : your-project-id
Location   : global
Manual     : resources/book_htp_combined.pdf
Auth File  : psychconnect-key.json
────────────────────────────────

🎬 Running assessment...

✅ Assessment complete!
⏱️  Total Processing Time : ~45.00s
🎯 Overall Confidence    : 0.87

==================== SYNTHESIS REPORT ====================
INTEGRATED CLINICAL SYNTHESIS — HTP ASSESSMENT
...
==========================================================

💾 Full analysis result saved to: test_output.json
```

---

## API Testing (with server running)

### Start the server

```bash
uvicorn main:app --reload --port 8000
```

### Health check

```bash
curl http://localhost:8000/health
```

### Submit an assessment

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"assessment_id": "your-assessment-uuid"}'
```

> **Note:** The assessment must already exist in Supabase with drawing URLs populated.

### Interactive docs

Visit `http://localhost:8000/docs` for the Swagger UI, where you can test endpoints interactively.

---

## Reviewing Test Output

The `test_output.json` file contains the full `AssessmentResponse`. Key things to check:

1. **Disclaimer present** in all reports
2. **Confidence scores** are reasonable (> 0.50 for clear drawings)
3. **Clinical flags** are populated when appropriate
4. **Cautious language** used throughout (no definitive statements)
5. **Cultural flags** present where Western norms are applied
6. **Report structure** follows the required format exactly
7. **No PII** in report body (patient_id only in the top-level field)

---

## Test Resources

The `resources/` folder contains test case sets:

| Case | Files | Purpose |
|------|-------|---------|
| Default | `test_house.png`, `test_tree.png`, `test_person.png` | Primary test case |
| Case 2 | `house2.png`, `tree2.png`, `person2.png`, `Case2.pdf` | Additional validation |
| Case 3 | `house3.png`, `tree3.png`, `person3.png`, `Case3.pdf` | Additional validation |
| Case 4 | `house4.png`, `tree4.png`, `person4.png`, `Case4.pdf` | Additional validation |

The PDF files contain reference solutions for comparison against AI output.
