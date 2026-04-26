# Clinical Rules

The PsychConnect AI Engine enforces **9 strict clinical rules** in every AI prompt to ensure safe, ethical, and professionally responsible output. These rules are defined in `prompts.py` and embedded in every Phase 2 and Phase 3 prompt.

> **Important:** Any change to these rules must be reviewed by the project's psychology advisor before deployment.

---

## The 9 Rules

### Rule 1 — Manual-Only Interpretations
> Base interpretations ONLY on the HTP Manual provided in context and the visual features explicitly identified in the drawing. Do not introduce external psychological frameworks not present in the manual.

**Why:** Ensures interpretive consistency and prevents the AI from hallucinating psychological theories.

### Rule 2 — No Diagnosis
> Do NOT diagnose. Never say "The patient has depression," "This indicates schizophrenia," or any equivalent. Diagnoses are exclusively the clinician's responsibility.

**Why:** Diagnosis is a licensed clinical act. AI-generated diagnostic statements could be misused or create liability.

### Rule 3 — Cautious Language
> Do NOT claim certainty. Every interpretive statement must use cautious language such as "This may suggest...", "Often associated with...", "Could be consistent with...", "Warrants clinical exploration of..."

**Why:** Projective tests have contested reliability. Definitive language would overstate the evidence.

### Rule 4 — Feature Anchoring
> Every interpretive claim must be directly traceable to a specific visual feature you have identified.

**Why:** Prevents the AI from making unsupported psychological inferences. Every claim needs a visible evidence basis.

**Correct:** "The absence of roots on the Tree may suggest..."  
**Incorrect:** "The patient appears to feel ungrounded" (no visual basis cited)

### Rule 5 — Limitations Section
> Always include a Limitations section acknowledging:
> - (a) Projective tests have contested reliability and validity
> - (b) A single session is insufficient for clinical conclusions
> - (c) AI vision analysis may miss subtle or culturally specific cues

**Why:** Transparent about the tool's limitations to prevent over-reliance.

### Rule 6 — Cultural Context (Pakistan)
> This assessment is conducted in a Pakistani / South Asian clinical context. Where an interpretation relies on Western norms, explicitly flag this and recommend the psychologist verify cultural applicability.

**Why:** HTP manuals were standardized on Western populations. Drawing conventions and symbolic meanings may differ in Pakistani culture. The AI flags every Western-normative interpretation for manual review.

### Rule 7 — Patient Privacy
> Do NOT reference the patient's name, patient_id, or any personally identifying information in the interpretive body of the report.

**Why:** Clinical reports may be shared or stored. PII must only appear in system headers, not in the interpretive text.

### Rule 8 — No Treatment Recommendations
> Do NOT provide treatment recommendations, medication suggestions, or specific therapeutic interventions.

**Why:** The report is an observational support document. Treatment decisions belong to the licensed clinician.

### Rule 9 — Mandatory Disclaimer
> Begin every report with the clinical disclaimer verbatim.

The disclaimer text:

```
DISCLAIMER: This AI-generated report is an assistive tool for qualified
psychologists only. It must not be used for diagnosis or treatment without
professional clinical review. AI interpretation of projective drawings has
known reliability and validity limitations. All findings require verification
by a licensed mental health professional.
```

---

## Questionnaire Integration

When PHQ-9 or DASS-21 scores are available, the synthesis report includes a **Questionnaire vs Drawing Consistency Check** (Section XI). This section:

1. States the severity label for each score using standard reference tables
2. Compares questionnaire severity against visual drawing features
3. Flags contradictions as clinically significant
4. Notes that PHQ-9 and DASS-21 were developed on Western populations
5. Recommends considering AKUADS (Aga Khan University Anxiety and Depression Scale) for Pakistani patients

### Severity Tables Used

**PHQ-9:**
- 0–4: Minimal | 5–9: Mild | 10–14: Moderate | 15–19: Moderately Severe | 20–27: Severe

**DASS-21 (raw scores ×2):**
- Depression: 0–9 Normal → 28+ Extremely Severe
- Anxiety: 0–7 Normal → 20+ Extremely Severe
- Stress: 0–14 Normal → 34+ Extremely Severe

---

## How Rules Are Enforced

1. **Embedded in prompts** — The full `CLINICAL_RULES` text is injected into every Phase 2 and Phase 3 prompt
2. **Disclaimer constant** — `DISCLAIMER` is a Python constant, ensuring verbatim consistency
3. **Schema enforcement** — Phase 1 output uses Gemini's `response_schema` to guarantee structure
4. **Report format** — Prompts specify exact section headings and required content per section
