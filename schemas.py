"""
schemas.py - All Pydantic data models for the HTP Assessment Service.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class Gender(str, Enum):
    male            = "male"
    female          = "female"
    other           = "other"
    prefer_not_say  = "prefer_not_to_say"


class ReferralSource(str, Enum):
    self_referred   = "self_referred"
    doctor          = "doctor"
    family          = "family"
    school          = "school"
    court           = "court"
    other           = "other"


# ─────────────────────────────────────────────
# Patient Inputs  (replaces hardcoded PATIENT_CONTEXT_TEXT)
# ─────────────────────────────────────────────

class DASS21Scores(BaseModel):
    """
    Subscale scores from DASS-21.
    Each subscale raw score is 0-21 (multiply item sum × 2 for severity mapping).
    """
    depression : Optional[int] = Field(None, ge=0, le=42, description="DASS-21 Depression subscale score")
    anxiety    : Optional[int] = Field(None, ge=0, le=42, description="DASS-21 Anxiety subscale score")
    stress     : Optional[int] = Field(None, ge=0, le=42, description="DASS-21 Stress subscale score")


class AssessmentRequest(BaseModel):
    """
    Request payload to start an assessment via the background worker queue.
    """
    assessment_id: str = Field(..., description="The unique UUID of the assessment in the Supabase database.")


class PatientContext(BaseModel):
    """
    All patient information collected BEFORE the HTP drawing session.
    This replaces the hardcoded PATIENT_CONTEXT_TEXT in the notebook.

    The platform (Next.js) should collect and POST these fields from:
      - Registration / onboarding form (age, gender)
      - Pre-session questionnaire module (phq9_score, dass21)
      - Session intake form (presenting_complaint, relevant_history, referral_source)

    PRIVACY NOTE:
      - patient_id is for audit logging only; it is NEVER included in the
        body of the clinical report (Rule 7).
      - Do NOT send full name — use patient_id only.
    """
    patient_id            : str   = Field(..., description="Platform UUID for this patient — used for audit log only")
    age                   : int   = Field(..., ge=5,  le=100, description="Patient age in years")
    gender                : Gender
    presenting_complaint  : str   = Field(..., min_length=10,
                                          description="Main reason for seeking help, in patient's own words")
    relevant_history      : Optional[str] = Field(
        None,
        description=(
            "Brief relevant background: family situation, trauma, medication, "
            "previous diagnoses (if any). Keep factual and concise."
        )
    )
    referral_source       : Optional[ReferralSource] = None

    # Scores already collected by the platform's questionnaire module
    phq9_score            : Optional[int]        = Field(None, ge=0, le=27,
                                                          description="PHQ-9 total score (0-27)")
    dass21                : Optional[DASS21Scores] = None


# ─────────────────────────────────────────────
# Drawing Feature Schema  (structured output from Gemini Flash)
# ─────────────────────────────────────────────

class DrawingFeatures(BaseModel):
    """
    Structured visual features extracted by Gemini Flash from a single drawing.
    Gemini returns this directly as JSON via response_schema — no manual parsing needed.
    """
    drawing_type    : str          # "House" | "Tree" | "Person" | "PPAT"
    line_quality    : str          # e.g. "Heavy and consistent throughout"
    size            : str          # "Small", "Average", "Large" relative to page
    placement       : str          # e.g. "Centered, slightly left of midline"
    omissions       : List[str]    # e.g. ["No roots visible", "Missing chimney"]
    shading_areas   : List[str]    # e.g. ["Heavy shading on torso", "Shaded windows"]
    distortions     : str          # e.g. "Door disproportionately small relative to house"
    key_details     : List[str]    # Any other clinically notable features
    confidence_score: float        # 0.0 – 1.0: how clearly the drawing could be analyzed
    clinical_flags  : List[str]    # Features that warrant urgent psychologist attention


# ─────────────────────────────────────────────
# API Request / Response
# ─────────────────────────────────────────────

class IndividualReport(BaseModel):
    drawing_type    : str
    features        : DrawingFeatures
    interpretation  : str   # Clinician-readable text report for this drawing


class AssessmentResponse(BaseModel):
    """Full response returned to the Next.js frontend."""
    patient_id              : str
    disclaimer              : str   # Always present — Rule 9
    house_report            : IndividualReport
    tree_report             : IndividualReport
    person_report           : IndividualReport
    ppat_report             : Optional[IndividualReport] = None
    synthesis_report        : str
    overall_confidence      : float
    low_confidence_warning  : bool  # True if any drawing scored < 0.50
    processing_time_seconds : float


class ErrorResponse(BaseModel):
    error   : str
    detail  : Optional[str] = None
