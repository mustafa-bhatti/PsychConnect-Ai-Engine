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
        result = await pipe.run_assessment(
            patient_context = TEST_PATIENT,
            house_bytes     = HOUSE_PATH.read_bytes(),   house_name  = HOUSE_PATH.name,
            tree_bytes      = TREE_PATH.read_bytes(),    tree_name   = TREE_PATH.name,
            person_bytes    = PERSON_PATH.read_bytes(),  person_name = PERSON_PATH.name,
        )

        print("\n✅ Assessment complete!")
        print(f"⏱️  Total Processing Time : {result.processing_time_seconds:.2f}s")
        print(f"🎯 Overall Confidence    : {result.overall_confidence}")

        print("\n" + "="*20 + " SYNTHESIS REPORT " + "="*20)
        print(result.synthesis_report)
        print("="*58)

        # Save output for review
        output_path = Path("test_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"\n💾 Full analysis result saved to: {output_path}")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())