"""
main.py — FastAPI microservice for the HTP Assessment Pipeline.
Authentication: Google Vertex AI via service account JSON file.
All configuration is driven by environment variables — see config.py.
"""

import json
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
import httpx

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

import config as cfg
from schemas import PatientContext, AssessmentRequest, ErrorResponse
from pipeline import HTPPipeline

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Globals ────────────────────────────────────────────────────────────────────
pipeline: HTPPipeline | None = None
supabase_client: Client | None = None
assessment_queue: asyncio.Queue = asyncio.Queue()

# ── Worker ─────────────────────────────────────────────────────────────────────
def calculate_age(dob_str: str) -> int:
    if not dob_str:
        return 30 # Default if missing
    try:
        dob = datetime.fromisoformat(dob_str.replace("Z", "+00:00")).date()
        today = datetime.now().date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception as e:
        logger.warning(f"Error calculating age for dob {dob_str}: {e}")
        return 30

async def download_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    if not url:
        return None, None
    logger.info(f"Downloading image from: {url}")
    
    # ── Security fix: Allow downloading from private Medical buckets ──
    # If the bucket is accidentally or intentionally set to Private, the
    # standard /public/ URL will return "Bucket not found" (404).
    # We rewrite it to the authenticated endpoint and pass the Service Role key.
    secure_url = url.replace("/object/public/", "/object/authenticated/")
    headers = {
        "Authorization": f"Bearer {cfg.SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": cfg.SUPABASE_SERVICE_ROLE_KEY
    }
    
    response = await client.get(secure_url, headers=headers)
    if response.status_code != 200:
        logger.error(f"Failed to download image. Status: {response.status_code}, Body: {response.text}")
        response.raise_for_status()
    # Extract filename from url or just provide a default
    filename = url.split("/")[-1].split("?")[0] or "image.jpg"
    return response.content, filename

async def process_assessment_task(assessment_id: str):
    logger.info(f"Worker processing assessment: {assessment_id}")
    
    try:
        # 1. Fetch assessment with patient info
        resp = supabase_client.table("assessments").select("*, patients(*)").eq("id", assessment_id).execute()
        if not resp.data:
            raise ValueError(f"Assessment {assessment_id} not found in database.")
        
        assessment = resp.data[0]
        patient    = assessment.get("patients", {})
        if not patient:
            raise ValueError(f"Patient not found for assessment {assessment_id}")

        patient_id = assessment.get("patient_id")
        
        # 2. Extract questionnaire_scores jsonb which contains patient context
        q_scores = assessment.get("questionnaire_scores", {}) or {}
        
        age = calculate_age(patient.get("date_of_birth"))
        if age < 5:
            age = 30  # Give a safe default if date_of_birth is missing or invalid
        
        gender_input = patient.get("gender") or "prefer_not_to_say"
        # Force map custom string inputs onto our enum choices, or fallback
        if gender_input.lower() not in ["male", "female", "other", "prefer_not_to_say"]:
            gender_input = "other"
            
        # Build patient context enforcing schema constraints
        patient_context = PatientContext(
            patient_id=str(patient_id),
            age=age,
            gender=gender_input,
            presenting_complaint=q_scores.get("presenting_complaint", "Patient presenting for psychological assessment."),
            relevant_history=patient.get("medical_history") or q_scores.get("relevant_history"),
            referral_source=q_scores.get("referral_source"),
            phq9_score=q_scores.get("phq9_score"),
            dass21=q_scores.get("dass21")
        )

        # 3. Download images
        async with httpx.AsyncClient() as http_client:
            house_bytes, house_name = await download_image(http_client, assessment.get("house_drawing_url"))
            tree_bytes, tree_name = await download_image(http_client, assessment.get("tree_drawing_url"))
            person_bytes, person_name = await download_image(http_client, assessment.get("person_drawing_url"))
            ppat_bytes, ppat_name = None, None  # Optional, usually in ppat_drawing_url if it exists later

        if not house_bytes or not tree_bytes or not person_bytes:
            raise ValueError("Missing one or more required drawing URLs (House, Tree, Person).")

        # 4. Process pipeline
        logger.info(f"Running pipeline for {assessment_id}")
        result = await pipeline.run_assessment(
            patient_context=patient_context,
            house_bytes=house_bytes, house_name=house_name,
            tree_bytes=tree_bytes, tree_name=tree_name,
            person_bytes=person_bytes, person_name=person_name,
            ppat_bytes=ppat_bytes, ppat_name=ppat_name,
        )

        # 5. Success DB update
        logger.info(f"Pipeline complete for {assessment_id}, saving to DB..")
        supabase_client.table("assessments").update({
            "status": "completed",
            "ai_report_json": result.model_dump()
        }).eq("id", assessment_id).execute()
        logger.info(f"Assessment {assessment_id} finalized.")

    except Exception as exc:
        logger.exception(f"Pipeline error for assessment_id={assessment_id}")
        # Failure DB update (omitting error column per user instructions)
        try:
            supabase_client.table("assessments").update({
                "status": "failed"
            }).eq("id", assessment_id).execute()
        except Exception as update_exc:
            logger.error(f"Failed to update assessment status to 'failed': {update_exc}")

async def assessment_worker():
    """Background task pulling from queue and processing sequentially."""
    logger.info("Background assessment worker started.")
    while True:
        assessment_id = await assessment_queue.get()
        try:
            await process_assessment_task(assessment_id)
        except Exception as e:
            logger.error(f"Worker unhandled exception processing {assessment_id}: {e}")
        finally:
            assessment_queue.task_done()

# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    global supabase_client

    # Validate required config
    missing = [
        name for name, value in [
            ("VERTEX_PROJECT_ID", cfg.VERTEX_PROJECT_ID),
            ("GOOGLE_APPLICATION_CREDENTIALS", cfg.CREDENTIALS_PATH),
            ("SUPABASE_URL", cfg.SUPABASE_URL),
            ("SUPABASE_SERVICE_ROLE_KEY", cfg.SUPABASE_SERVICE_ROLE_KEY),
        ] if not value
    ]
    if missing:
        msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)

    # Init clients
    pipeline = HTPPipeline()
    supabase_client = create_client(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY)
    
    # Start background worker
    worker_task = asyncio.create_task(assessment_worker())
    logger.info("HTP Pipeline & Supabase initialized. Queue started.")

    yield  # Application runs here

    logger.info("HTP Service shutting down.")
    worker_task.cancel()

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PsychConnect — HTP Assessment Microservice",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    if pipeline is None or supabase_client is None:
        raise HTTPException(status_code=503, detail="Service not initialised.")
    return {
        "status"          : "ok",
        "service"         : "htp-assessment",
        "version"         : "2.1.0",
        "queue_size"      : assessment_queue.qsize(),
    }

@app.post(
    "/assess",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        503: {"model": ErrorResponse},
    },
    tags=["Assessment"],
    summary="Enqueue full HTP assessment",
)
async def enqueue_assessment(payload: AssessmentRequest):
    if pipeline is None or supabase_client is None:
        raise HTTPException(status_code=503, detail="Service not initialised.")
    
    await assessment_queue.put(payload.assessment_id)
    logger.info(f"Enqueued assessment {payload.assessment_id}. Queue size: {assessment_queue.qsize()}")
    
    return {"message": "Assessment processing started."}
