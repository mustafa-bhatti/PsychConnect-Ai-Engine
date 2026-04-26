# Contributing

Guidelines for contributing to the PsychConnect AI Engine.

---

## Code Structure

```
PsychConnect-Ai-Engine/
├── main.py            ← FastAPI app, routes, background worker
├── pipeline.py        ← Core HTP pipeline (Gemini Flash + Pro)
├── schemas.py         ← Pydantic models (request / response)
├── prompts.py         ← All system prompts and clinical rules
├── config.py          ← Environment-driven configuration
├── test_local.py      ← Local end-to-end test
├── requirements.txt   ← Python dependencies
├── docs/              ← This documentation
└── resources/         ← HTP manual + test images
```

---

## Development Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run `python test_local.py` to verify the pipeline works end-to-end
4. Test with the FastAPI server (`uvicorn main:app --reload`)
5. Submit a pull request with a clear description

---

## Coding Standards

- **Type hints** — Use type annotations for all function signatures
- **Docstrings** — All classes and public functions must have docstrings
- **Logging** — Use `logger.info()` / `logger.warning()` / `logger.error()` (not `print()`)
- **Error handling** — Catch specific exceptions; log context before re-raising
- **Config** — All tuneable values go in `config.py` via environment variables

---

## Prompt Change Policy

> **⚠️ All changes to `prompts.py` must be reviewed by the project's psychology advisor before deployment.**

Prompts directly affect clinical output. When modifying:

1. **Never remove** any of the 9 clinical rules
2. **Never remove** the mandatory disclaimer (Rule 9)
3. **Document the rationale** for each change in the PR
4. **Run a full test** and compare output against the previous version
5. **Get psychology advisor approval** before merging

---

## Schema Changes

When modifying `schemas.py`:

1. Ensure backward compatibility with existing `ai_report_json` data in Supabase
2. Update the [Data Models](./data-models.md) documentation
3. Coordinate with the frontend team for any `AssessmentResponse` changes
4. Test with `test_local.py` to verify Gemini still produces valid output

---

## Security Rules

- **Never commit** `.env`, `psychconnect-key.json`, or any credentials
- **Never log** patient PII, service keys, or API keys
- **Never include** `patient_id` in clinical report text (Rule 7)
- **Always use** `SUPABASE_SERVICE_ROLE_KEY` only server-side

---

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add PPAT drawing support to Phase 1 extraction
fix: handle missing date_of_birth with safe default age
docs: update API reference with new polling example
refactor: extract cache creation into separate method
```
