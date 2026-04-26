"""
test_local.py — Quick local test to verify the pipeline runs end-to-end.
Synced with the user's config.py (using CREDENTIALS_PATH).
"""

import asyncio
import json
from pathlib import Path

# Import the centralized config
import config as cfg
from schemas import PatientContext, Gender, DASS21Scores
from pipeline import HTPPipeline

# ── Test patient context ──────────────────────────────────────────────────────
TEST_PATIENT = PatientContext(
    patient_id           = "test-patient-001",
    age                  = 26,
    gender               = Gender.male,
    presenting_complaint = (
        "Complains of chronic fatigue, diffuse anxiety, low thresholds for frustration."
    ),
    relevant_history     = (
        "26-year-old male. Prone to seeking satisfaction in fantasy rather than reality."
    ),
    phq9_score = 11,
    dass21     = DASS21Scores(depression=14, anxiety=18, stress=22),
)

# ── Test image paths ──────────────────────────────────────────────────────────
RESOURCES   = Path("resources")
HOUSE_PATH  = RESOURCES / "test_house.png"
TREE_PATH   = RESOURCES / "test_tree.png"
PERSON_PATH = RESOURCES / "test_person.png"

async def main():
    # ── Verify Resources Exist ───────────────────────────────────────────────
    missing_files = []
    for p in [HOUSE_PATH, TREE_PATH, PERSON_PATH]:
        if not p.exists():
            missing_files.append(str(p))
    
    manual = Path(cfg.HTP_MANUAL_PATH)
    if not manual.exists():
        missing_files.append(f"Manual not found at: {cfg.HTP_MANUAL_PATH}")

    if missing_files:
        print("❌ ERROR: Missing required files:")
        for f in missing_files:
            print(f"  - {f}")
        return

    # ── Display Active Config (Using your config.py variable names) ──────────
    print("🚀 Initializing PsychConnect Pipeline")
    print("-" * 40)
    print(f"Project ID : {cfg.VERTEX_PROJECT_ID}")
    print(f"Location   : {cfg.VERTEX_LOCATION}")
    print(f"Manual     : {cfg.HTP_MANUAL_PATH}")
    print(f"Auth File  : {cfg.CREDENTIALS_PATH}")
    print("-" * 40)

    # Initialize the pipeline
    pipe = HTPPipeline()

    print("\n🎬 Running assessment...")
    print("Note: Phases will run in parallel using Vertex AI.\n")

    try:
        result, pdf_bytes = await pipe.run_assessment(
            patient_context = TEST_PATIENT,
            house_bytes     = HOUSE_PATH.read_bytes(),   house_name  = HOUSE_PATH.name,
            tree_bytes      = TREE_PATH.read_bytes(),    tree_name   = TREE_PATH.name,
            person_bytes    = PERSON_PATH.read_bytes(),  person_name = PERSON_PATH.name,
        )

        print("\n✅ Assessment complete!")
        print(f"⏱️  Total Processing Time : {result.processing_time_seconds:.2f}s")
        print(f"🎯 Overall Confidence    : {result.overall_confidence}")

        # Display key themes
        print("\n" + "="*20 + " KEY THEMES " + "="*20)
        for theme in result.summary.key_themes:
            icon = {"high": "🔴", "moderate": "🟡", "low": "🟢"}.get(theme.severity, "⚪")
            print(f"  {icon} [{theme.severity.upper()}] {theme.theme}")
            print(f"     Evidence: {theme.evidence}")
        
        # Display risk flags
        if result.summary.risk_flags:
            print("\n⚠️  RISK FLAGS:")
            for flag in result.summary.risk_flags:
                print(f"  🚩 {flag}")

        # Display clinical impression
        print("\n" + "="*20 + " CLINICAL IMPRESSION " + "="*20)
        print(result.summary.clinical_impression)
        print("="*58)

        # Display session focus areas
        print("\n📋 SESSION FOCUS AREAS:")
        for i, area in enumerate(result.session_focus_areas, 1):
            print(f"  {i}. {area}")

        # Save JSON output
        output_path = Path("test_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"\n💾 Dashboard JSON saved to: {output_path}")

        # Save PDF output
        pdf_path = Path("test_report.pdf")
        pdf_path.write_bytes(pdf_bytes)
        print(f"📄 PDF report saved to: {pdf_path}")
        print(f"   PDF size: {len(pdf_bytes) / 1024:.1f} KB")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())