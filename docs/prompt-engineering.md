# Prompt Engineering

This document explains how the AI prompts are structured across the three pipeline phases, and the reasoning behind key design decisions.

All prompts are defined in `prompts.py`.

---

## Prompt Architecture

```
prompts.py
├── DISCLAIMER                      ← Universal clinical disclaimer
├── PHQ9_SEVERITY                   ← Severity reference table
├── DASS21_SEVERITY                 ← Severity reference table
├── QUESTIONNAIRE_INTEGRATION_FORMAT← Section XI template
├── CLINICAL_RULES                  ← 9 rules embedded in Phase 2+3
├── build_extraction_prompt()       ← Phase 1 prompt builder
├── build_interpretation_prompt()   ← Phase 2 prompt builder
├── build_synthesis_prompt()        ← Phase 3 prompt builder
└── build_patient_context_summary() ← Helper: PatientContext → text
```

---

## Phase 1 — Feature Extraction

**Function:** `build_extraction_prompt(drawing_type, is_combined_sheet)`

### Design Principles

- **No HTP manual sent** — Phase 1 is purely observational; the model describes what it sees without interpreting
- **No clinical rules** — Rules apply to interpretation, not observation
- **Structured output** — Uses Gemini's `response_schema` parameter to enforce `DrawingFeatures` JSON
- **Temperature 0.0** — Deterministic extraction; same image should produce the same features

### What It Extracts

1. **Line Quality** — Pressure and stroke character
2. **Size** — Relative to page (Small / Average / Large)
3. **Placement** — Position on the page
4. **Omissions** — Missing expected elements (type-specific checklists)
5. **Shading Areas** — Heavy fill or cross-hatching
6. **Distortions** — Disproportionate or unusual features
7. **Key Details** — Other notable features (transparent walls, weapons, etc.)
8. **Confidence Score** — 0.0–1.0 with specific deduction rules
9. **Clinical Flags** — Features needing urgent psychologist attention

### PPAT Support

When `drawing_type == "PPAT"`, additional extraction criteria are injected for the Person Picking an Apple from a Tree drawing.

### Combined Sheet Support

When `is_combined_sheet=True`, the prompt instructs Gemini to focus on only the specified drawing type within a multi-drawing image.

---

## Phase 2 — Individual Interpretation

**Function:** `build_interpretation_prompt(drawing_type, features_json, patient_context_summary)`

### Structure

```
1. CLINICAL_RULES (all 9 rules)
2. Role instruction ("You are an HTP assessment assistant...")
3. Patient demographic context (age, gender, complaint)
4. Extracted features JSON from Phase 1
5. Required report format template
```

### Required Report Sections

1. **SCORING RULES IDENTIFIED** — Maps each visual feature to its HTP manual rule
2. **INTERPRETIVE THEMES** — Tentative psychological themes with cautious language
3. **FOLLOW-UP QUESTIONS** — Exactly 4 session questions for the psychologist
4. **LIMITATIONS** — Confidence score impact, ambiguities, cultural factors

### Key Design Decisions

- **Features + Image sent together** — The model can verify features against the original image
- **Manual via context cache** — 90% token cost reduction on repeated calls
- **Cultural flagging inline** — Every Western-normative interpretation is tagged with `[Cultural verification recommended — Rule 6]`

---

## Phase 3 — Synthesis

**Function:** `build_synthesis_prompt(house_report, tree_report, person_report, ppat_report, patient_context_summary)`

### Structure

```
1. CLINICAL_RULES (all 9 rules)
2. PHQ-9 severity table
3. DASS-21 severity table
4. Role instruction ("You are a Clinical Psychologist...")
5. Patient context
6. All individual reports (Phase 2 outputs)
7. Required report format template (11 sections)
```

### Required Report Sections

| Section | Content |
|---------|---------|
| I. Details | Notable details per drawing with manual significance |
| II. Proportion | Size and ratio observations |
| III. Perspective & Placement | Page position patterns |
| IV. Line Quality | Stroke/pressure analysis |
| V. Cross-Drawing Synthesis | Recurring themes and contradictions |
| VI. Clinical Concepts | Core psychological theme per drawing |
| VII. Qualitative Summary | 3–5 numbered tentative themes |
| VIII. Clinical Impression | One cautious paragraph (no diagnosis) |
| IX. Recommended Focus Areas | 4–5 exploration prompts for session |
| X. Limitations | Standard limitations checklist |
| XI. Questionnaire Consistency | PHQ-9/DASS-21 vs drawing comparison |

### Key Design Decisions

- **All images re-sent** — Pro model can visually verify and supplement individual reports
- **Cross-referencing required** — Prompt explicitly asks for cross-drawing pattern identification
- **Questionnaire integration** — Scores are compared against visual findings with cultural validity notes
- **AKUADS recommendation** — Flags when Western questionnaires may be less valid for Pakistani patients

---

## Patient Context Summary

**Function:** `build_patient_context_summary(ctx: PatientContext)`

Converts a `PatientContext` model into a human-readable string for prompt injection. Deliberately **excludes** `patient_id` (Rule 7).

Output format:
```
Age: 28
Gender: female
Presenting Complaint: Persistent low mood for 3 months
Relevant History: No prior treatment. Stressful work environment.
Referral Source: self_referred
PHQ-9 Total Score: 14 / 27
DASS-21 Scores: Depression=18, Anxiety=12, Stress=20
```

---

## Modifying Prompts

> **⚠️ All prompt changes must be reviewed by the project's psychology advisor before deployment.**

When modifying prompts:

1. **Never remove clinical rules** — All 9 rules must be present in Phase 2 and 3 prompts
2. **Preserve the disclaimer** — Rule 9 requires verbatim inclusion
3. **Test with `test_local.py`** — Run a full pipeline test after changes
4. **Review output quality** — Check that reports follow the required format
5. **Document changes** — Note what was changed and why in commit messages
