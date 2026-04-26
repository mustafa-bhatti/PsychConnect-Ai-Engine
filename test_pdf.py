"""
test_pdf.py — Standalone PDF generation test. No Gemini API needed.

Usage:
    python test_pdf.py

Reads test_output.json if it matches the new schema (has a "summary" key).
Otherwise falls back to built-in mock data so you can test immediately.

Output: test_report.pdf in the project root.
"""

import json
import sys
from pathlib import Path


# ── Mock data: realistic Gemini output with common Unicode chars ──────────────
MOCK_SYNTHESIS_DATA = {
    "clinical_impression": (
        "The three drawings present a consistent picture of an individual experiencing "
        "significant internal tension and environmental constriction. Themes of "
        "guardedness and emotional withdrawal appear across all drawings, which may be "
        "consistent with the presenting complaint of chronic fatigue and diffuse anxiety. "
        "The Tree drawing's scar feature and the House drawing's absent chimney may "
        "suggest unresolved past experiences that could be contributing to the patient's "
        "current presentation. This impression is preliminary and must be confirmed or "
        "revised by the supervising psychologist following direct clinical interview."
    ),
    "key_themes": [
        {
            "theme"   : "Emotional Guardedness",
            "evidence": "Locked door on the House, arms pressed close to body on the Person figure, and sparse foliage on the Tree collectively suggest a pattern of interpersonal caution.",
            "severity": "moderate",
        },
        {
            "theme"   : "Anxiety and Internal Tension",
            "evidence": "Sketchy and variable line quality throughout all three drawings, heavy shading on the tree trunk, and a scowling facial expression on the Person figure.",
            "severity": "high",
        },
        {
            "theme"   : "Past Trauma Indicators",
            "evidence": "A prominent scar on the Tree trunk, which is often associated with past experiences perceived as psychologically wounding.",
            "severity": "moderate",
        },
        {
            "theme"   : "Feelings of Environmental Constriction",
            "evidence": "Large drawing sizes on both the House and Tree, filling most of the available page space.",
            "severity": "low",
        },
    ],
    "risk_flags": [
        "Tree trunk contains a dark scar requiring clinical follow-up regarding possible past trauma.",
    ],
    "house_observations": [
        {
            "feature"       : "No chimney present",
            "interpretation": "May suggest a lack of emotional warmth in the perceived home environment, or a passive, constrained approach to expressing feelings.",
        },
        {
            "feature"       : "Door appears closed with no visible handle",
            "interpretation": "Could be consistent with guardedness and reluctance to allow others into personal space.",
        },
        {
            "feature"       : "Ground line extending across full width",
            "interpretation": "May indicate a need to anchor the drawing to something concrete, often associated with general insecurity.",
        },
        {
            "feature"       : "Sketchy roof tile detail",
            "interpretation": "Variable, sketchy line quality can be associated with indecisiveness or underlying anxiety.",
        },
    ],
    "tree_observations": [
        {
            "feature"       : "Dark scar on upper trunk",
            "interpretation": "Often associated with a past experience the subject perceives as psychologically wounding. Position on upper trunk may suggest an event in later adolescence or early adulthood.",
        },
        {
            "feature"       : "No leaves visible",
            "interpretation": "Leaflessness may suggest reduced functional contact with the environment, or could reflect current emotional barrenness.",
        },
        {
            "feature"       : "Strong baseline present",
            "interpretation": "May indicate insecurity and a need to anchor the self to something tangible.",
        },
    ],
    "person_observations": [
        {
            "feature"       : "Arms held close to body",
            "interpretation": "May suggest emotional rigidity or difficulty expressing feelings outwardly.",
        },
        {
            "feature"       : "Disproportionately large nose",
            "interpretation": "Could be associated with phallic preoccupation or sensitivity to criticism.",
        },
        {
            "feature"       : "Simplified hands without fingers",
            "interpretation": "May indicate feelings of inadequacy or helplessness in social situations.",
        },
        {
            "feature"       : "Scowling facial expression",
            "interpretation": "Warrants exploration of the patient's conscious and unconscious social presentation and underlying emotional state.",
        },
        {
            "feature"       : "Figure drawn in profile",
            "interpretation": "May reflect evasiveness in social contact or a reserved, studied approach to interaction.",
        },
    ],
    "session_focus_areas": [
        "Explore the significance of the missing chimney -- ask what warmth or comfort looks like in the patient's home environment.",
        "Gently inquire about the scar on the tree trunk and whether the patient associates it with any past experiences.",
        "Discuss the closed door and absent handle -- explore themes of trust and allowing others close.",
        "Ask about the angry expression on the Person figure and what the figure might be feeling or thinking.",
        "Explore the pattern of the patient seeking satisfaction in fantasy rather than reality, and how this relates to the drawing themes.",
    ],
    "phq9": {
        "score"              : 11,
        "severity"           : "Moderate",
        "drawing_consistency": "consistent",
    },
    "dass21_depression": {
        "score"              : 14,
        "severity"           : "Moderate",
        "drawing_consistency": "consistent",
    },
    "dass21_anxiety": {
        "score"              : 18,
        "severity"           : "Severe",
        "drawing_consistency": "consistent",
    },
    "dass21_stress": {
        "score"              : 22,
        "severity"           : "Moderate",
        "drawing_consistency": "neutral",
    },
}

MOCK_INTERPRETATIONS = {
    "House": (
        "1. KEY OBSERVATIONS\n"
        "Missing chimney -- May suggest constrained emotional expression or a perceived lack of warmth in the home situation.\n"
        "Closed door, no handle -- Could indicate guardedness and reluctance to allow others into personal space.\n"
        "Full-width ground line -- Often associated with insecurity and a need to anchor the drawing to something concrete.\n"
        "Sketchy roof tile shading -- Variable line quality may be associated with indecisiveness or mild anxiety.\n\n"
        "2. INTERPRETIVE THEMES\n"
        "The House drawing may suggest an individual who perceives their home environment as emotionally constrained "
        "and who maintains clear boundaries around personal access. The overall quality of the drawing is "
        "consistent with mild-to-moderate anxiety as a background state.\n\n"
        "3. FOLLOW-UP QUESTIONS FOR PSYCHOLOGIST\n"
        "1. You did not draw a chimney -- what does the chimney mean to you in a house?\n"
        "2. The door appears closed with no handle. Who would be allowed to enter this house?\n"
        "3. You drew a line across the full bottom of the page. What is the ground like around this house?\n"
        "4. You added quite a lot of detail to the roof tiles. What drew your attention there?"
    ),
    "Tree": (
        "1. KEY OBSERVATIONS\n"
        "Dark scar on upper trunk -- Often associated with a past experience perceived as psychologically wounding.\n"
        "No leaves -- May indicate reduced contact with the environment or current emotional barrenness.\n"
        "Strong baseline -- May indicate insecurity and a need to anchor the self to something concrete.\n\n"
        "2. INTERPRETIVE THEMES\n"
        "The Tree is often regarded as a portrait of the self's basic resources and strength. This drawing "
        "may suggest an individual who has experienced a significant wounding event in the past and who "
        "currently feels depleted or disconnected from their environment.\n\n"
        "3. FOLLOW-UP QUESTIONS FOR PSYCHOLOGIST\n"
        "1. There is a dark mark on the trunk of your tree. Can you tell me what that is?\n"
        "2. Your tree has no leaves. What season is it for this tree, or is it always like this?\n"
        "3. What kind of tree is this?\n"
        "4. You drew a line under the tree. What is the ground like around it?"
    ),
    "Person": (
        "1. KEY OBSERVATIONS\n"
        "Arms close to body -- May suggest emotional rigidity or difficulty expressing feelings outwardly.\n"
        "Large nose, heavily shaded -- Could be associated with heightened sensitivity or phallic preoccupation.\n"
        "No individual fingers -- May indicate feelings of social inadequacy or helplessness.\n"
        "Scowling expression -- Warrants exploration of underlying emotional state and social presentation.\n"
        "Profile view -- May reflect evasiveness or a reserved approach to social contact.\n\n"
        "2. INTERPRETIVE THEMES\n"
        "The Person drawing may suggest an individual who is socially guarded, experiencing internal tension, "
        "and presenting a controlled exterior that may mask significant underlying conflict. The combination "
        "of physical rigidity and facial aggression is clinically notable.\n\n"
        "3. FOLLOW-UP QUESTIONS FOR PSYCHOLOGIST\n"
        "1. The person you drew looks quite angry. What might he be feeling or thinking?\n"
        "2. The arms are held close to the body. What is this person about to do with their hands?\n"
        "3. You drew the person from the side. Why did you choose that angle?\n"
        "4. The nose is quite prominent. Is there anything specific about that feature you want to tell me?"
    ),
}

MOCK_PATIENT_CONTEXT = (
    "Age: 26\n"
    "Gender: male\n"
    "Presenting Complaint: Chronic fatigue, diffuse anxiety, low thresholds for frustration.\n"
    "Relevant History: Prone to seeking satisfaction in fantasy rather than reality.\n"
    "PHQ-9 Total Score: 11 / 27\n"
    "DASS-21 Scores: Depression=14, Anxiety=18, Stress=22"
)


def load_new_schema_json(report_json: dict) -> tuple[dict, dict, str]:
    """
    Load synthesis_data, interpretations, and patient summary from a
    new-schema test_output.json (must have a 'summary' key).
    """
    summary  = report_json.get("summary", {})
    drawings = report_json.get("drawings", [])

    obs_map = {}
    interp_map = {}
    for d in drawings:
        dt  = d.get("drawing_type", "")
        key = f"{dt.lower()}_observations"
        obs_map[key] = d.get("observations", [])
        lines = [f"{o.get('feature', '')} -- {o.get('interpretation', '')}" for o in d.get("observations", [])]
        interp_map[dt] = "\n".join(lines) if lines else "(No detailed interpretation in saved JSON.)"

    q_match = report_json.get("questionnaire_match") or {}

    synthesis = {
        "clinical_impression": summary.get("clinical_impression", ""),
        "key_themes"         : [
            {"theme": t.get("theme", ""), "evidence": t.get("evidence", ""), "severity": t.get("severity", "moderate")}
            for t in summary.get("key_themes", [])
        ],
        "risk_flags"          : summary.get("risk_flags", []),
        "session_focus_areas" : report_json.get("session_focus_areas", []),
        **obs_map,
        "phq9"              : q_match.get("phq9"),
        "dass21_depression"  : q_match.get("dass21_depression"),
        "dass21_anxiety"     : q_match.get("dass21_anxiety"),
        "dass21_stress"      : q_match.get("dass21_stress"),
    }

    patient_summary = f"Overall Confidence: {report_json.get('overall_confidence', 'N/A')}"
    return synthesis, interp_map, patient_summary


def make_stub_features(drawing_types_with_conf: dict) -> dict:
    from schemas import DrawingFeatures
    stub_map = {}
    for dt, conf in drawing_types_with_conf.items():
        stub_map[dt] = DrawingFeatures(
            drawing_type=dt, line_quality="N/A", size="N/A", placement="N/A",
            omissions=[], shading_areas=[], distortions="N/A",
            key_details=[], confidence_score=conf, clinical_flags=[],
        )
    return stub_map


def main():
    # Try to load an existing new-schema JSON, else use mock data
    json_path = Path("test_output.json")
    synthesis_data    = MOCK_SYNTHESIS_DATA
    interpretations   = MOCK_INTERPRETATIONS
    patient_summary   = MOCK_PATIENT_CONTEXT
    confidence_map    = {"House": 0.90, "Tree": 0.85, "Person": 0.82}

    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            try:
                saved = json.load(f)
            except json.JSONDecodeError:
                saved = {}

        if "summary" in saved:
            print(f"Loading new-schema data from {json_path}...")
            synthesis_data, interpretations, patient_summary = load_new_schema_json(saved)
            confidence_map = {
                d.get("drawing_type", ""): d.get("confidence", 0.85)
                for d in saved.get("drawings", [])
                if d.get("drawing_type")
            }
        else:
            print(f"{json_path} uses old schema -- using built-in mock data instead.")
    else:
        print("No test_output.json found -- using built-in mock data.")

    from pdf_report import generate_pdf_report

    features_map = make_stub_features(confidence_map)

    print("Generating PDF...")
    try:
        pdf_bytes = generate_pdf_report(
            patient_context_summary = patient_summary,
            house_interpretation    = interpretations.get("House", ""),
            tree_interpretation     = interpretations.get("Tree", ""),
            person_interpretation   = interpretations.get("Person", ""),
            synthesis_data          = synthesis_data,
            features_map            = features_map,
        )
        out_path = Path("test_report.pdf")
        out_path.write_bytes(pdf_bytes)
        print(f"\nPDF saved: {out_path}  ({len(pdf_bytes) / 1024:.1f} KB)")

    except Exception as e:
        import traceback
        print(f"\nPDF generation failed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
