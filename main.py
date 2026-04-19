"""
main.py — FastAPI microservice for the HTP Assessment Pipeline.

Authentication: Google Vertex AI via service account JSON file.

All configuration is driven by environment variables — see config.py.
To change any setting, edit your .env file and restart the service.

Running locally:
  uvicorn main:app --reload --port 8000

Running on Railway / Cloud Run:
  Set all variables in the platform dashboard.  Railway auto-detects the Procfile.
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import config as cfg
from schemas import PatientContext, AssessmentResponse, ErrorResponse
from pipeline import HTPPipeline
import asyncio

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan — initialise pipeline once at startup ─────────────────────────────
pipeline: HTPPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline

    # Validate required config before touching any Google APIs
    missing = [
        name
        for name, value in [
            ("VERTEX_PROJECT_ID",           cfg.VERTEX_PROJECT_ID),
            ("GOOGLE_APPLICATION_CREDENTIALS", cfg.CREDENTIALS_PATH),
        ]
        if not value
    ]
    if missing:
        msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(
        "Starting HTP service — project=%s  location=%s  credentials=%s",
        cfg.VERTEX_PROJECT_ID,
        cfg.VERTEX_LOCATION,
        cfg.CREDENTIALS_PATH,
    )

    try:
        pipeline = HTPPipeline()
        logger.info("HTP Pipeline initialised and ready.")
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("Startup failed: %s", exc)
        raise

    yield  # Application runs here

    logger.info("HTP Service shutting down.")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PsychConnect — HTP Assessment Microservice",
    description=(
        "AI-assisted House-Tree-Person projective drawing analysis. "
        "All outputs are assistive tools for licensed psychologists only. "
        "This service never provides autonomous diagnoses."
    ),
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins    =cfg.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods    =["POST", "GET"],
    allow_headers    =["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _read_and_validate_image(
    file: UploadFile, field_name: str
) -> tuple[bytes, str]:
    contents = await file.read()
    size_mb  = len(contents) / (1024 * 1024)

    if size_mb > cfg.MAX_IMAGE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"'{field_name}' exceeds {cfg.MAX_IMAGE_SIZE_MB} MB limit "
                f"({size_mb:.1f} MB uploaded)."
            ),
        )
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"'{field_name}' must be an image file (JPEG, PNG, WEBP). "
                f"Got: {file.content_type}"
            ),
        )
    return contents, file.filename or field_name


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Railway / Cloud Run healthchecks should poll this.
    Returns 200 only when the pipeline is fully initialised.
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")
    return {
        "status"          : "ok",
        "service"         : "htp-assessment",
        "version"         : "2.1.0",
        "vertex_project"  : cfg.VERTEX_PROJECT_ID,
        "vertex_location" : cfg.VERTEX_LOCATION,
    }


@app.post(
    "/assess",
    response_model=AssessmentResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Assessment"],
    summary="Run full HTP assessment",
    description=(
        "Accepts House, Tree, and Person drawing images plus structured patient context. "
        "PPAT drawing is optional. Returns individual drawing reports and an integrated "
        "synthesis report. All outputs are AI-assistive only — not diagnostic."
    ),
)
async def run_assessment(
    patient_context_json: str = Form(
        ...,
        description=(
            "JSON string of PatientContext. "
            "Fields: patient_id, age, gender, presenting_complaint, "
            "relevant_history (optional), referral_source (optional), "
            "phq9_score (optional), dass21 (optional: {depression, anxiety, stress})."
        ),
        example=json.dumps({
            "patient_id"           : "uuid-from-your-platform",
            "age"                  : 28,
            "gender"               : "female",
            "presenting_complaint" : "Persistent low mood and difficulty concentrating for 3 months",
            "relevant_history"     : "Reports stressful work environment. No prior mental health treatment.",
            "phq9_score"           : 14,
            "dass21"               : {"depression": 18, "anxiety": 12, "stress": 20},
        }),
    ),
    house_image  : UploadFile       = File(...,    description="House drawing. JPEG / PNG / WEBP, max 10 MB."),
    tree_image   : UploadFile       = File(...,    description="Tree drawing."),
    person_image : UploadFile       = File(...,    description="Person drawing."),
    ppat_image   : UploadFile | None = File(None,  description="Optional PPAT drawing."),
):
    # Parse and validate patient context
    try:
        ctx_data        = json.loads(patient_context_json)
        patient_context = PatientContext(**ctx_data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid patient_context_json: {exc}",
        )

    # Read and validate images
    house_bytes,  house_name  = await _read_and_validate_image(house_image,  "house_image")
    tree_bytes,   tree_name   = await _read_and_validate_image(tree_image,   "tree_image")
    person_bytes, person_name = await _read_and_validate_image(person_image, "person_image")

    ppat_bytes, ppat_name = None, None
    if ppat_image is not None:
        ppat_bytes, ppat_name = await _read_and_validate_image(ppat_image, "ppat_image")

    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    try:
        result = await pipeline.run_assessment(
            patient_context=patient_context,
            house_bytes    =house_bytes,   house_name    =house_name,
            tree_bytes     =tree_bytes,    tree_name     =tree_name,
            person_bytes   =person_bytes,  person_name   =person_name,
            ppat_bytes     =ppat_bytes,    ppat_name     =ppat_name,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "Pipeline error for patient_id=%s", patient_context.patient_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assessment pipeline error: {exc}",
        )

    return result
