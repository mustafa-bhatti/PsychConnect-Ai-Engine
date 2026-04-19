"""
pipeline.py — Core async HTP assessment pipeline.

Authentication  : Google Vertex AI via service account JSON.
Context caching : The HTP manual PDF is registered once at startup as a Vertex AI
                  Context Cache (one cache per model).  Every Phase-2 and Phase-3
                  call references the cache instead of re-uploading the full PDF,
                  giving a 90 % discount on manual input tokens.

Architecture
------------
Phase 1 (parallel) : Gemini Flash — extract structured visual features from each
                     drawing image.  No manual sent (fast + cheap).
Phase 2 (parallel) : Gemini Flash — write a per-drawing clinical interpretation
                     report.  Manual served from context cache.
Phase 3 (single)   : Gemini Pro   — synthesise all individual reports + all raw
                     images into a final integrated clinical report.
                     Manual served from context cache.

Both Phase 1 and Phase 2 run with asyncio.gather — fully parallel.
All API calls are wrapped in exponential back-off + jitter retry logic that
handles Vertex AI 429 / RESOURCE_EXHAUSTED errors without artificial sleeps.
"""

import os
import asyncio
import json
import time
import random
import mimetypes
import logging
from pathlib import Path
from typing import Optional, Any

from google import genai
from google.genai import types
from google.genai.types import (
    GenerateContentConfig,
    CreateCachedContentConfig,
    Content,
    HttpOptions,
)

import config as cfg
from schemas import DrawingFeatures, IndividualReport, AssessmentResponse, PatientContext
from prompts import (
    build_extraction_prompt,
    build_interpretation_prompt,
    build_synthesis_prompt,
    build_patient_context_summary,
    DISCLAIMER,
)

logger = logging.getLogger(__name__)


class HTPPipeline:
    """
    Instantiated once at FastAPI startup.
    Holds the Vertex AI client, the loaded manual bytes, and the context-cache
    resource names (or None if caching could not be set up).
    """

    def __init__(self) -> None:
        # ── Authentication ─────────────────────────────────────────────────────
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cfg.CREDENTIALS_PATH
        if not Path(cfg.CREDENTIALS_PATH).exists():
            raise FileNotFoundError(
                f"Service account JSON not found at '{cfg.CREDENTIALS_PATH}'. "
                "Set GOOGLE_APPLICATION_CREDENTIALS in your .env file."
            )

        # ── Vertex AI client ───────────────────────────────────────────────────
        # api_version="v1" is required for the context-caching endpoints.
        self.client = genai.Client(
            vertexai=True,
            project=cfg.VERTEX_PROJECT_ID,
            location=cfg.VERTEX_LOCATION,
            http_options=HttpOptions(api_version="v1"),
        )
        logger.info(
            "Vertex AI client ready — project=%s  location=%s",
            cfg.VERTEX_PROJECT_ID,
            cfg.VERTEX_LOCATION,
        )

        # ── HTP manual ─────────────────────────────────────────────────────────
        self.manual_bytes, self.manual_mime = self._load_manual(cfg.HTP_MANUAL_PATH)
        manual_mb = len(self.manual_bytes) / (1024 * 1024)
        logger.info("Manual loaded — %.1f MB  mime=%s", manual_mb, self.manual_mime)

        # ── Context caches ─────────────────────────────────────────────────────
        # Caches are model-scoped on Vertex AI, so we need one per model.
        # Flash cache → Phase 2 (interpretation)
        # Pro cache   → Phase 3 (synthesis)
        self._flash_cache: Optional[str] = self._create_cache(
            cfg.FLASH_MODEL, "htp-manual-flash"
        )
        self._pro_cache: Optional[str] = self._create_cache(
            cfg.PRO_MODEL, "htp-manual-pro"
        )

        # Fallback Part: used when the context cache is unavailable.
        # Pre-encoded once at startup to avoid re-encoding bytes on every call.
        self._manual_part_fallback = types.Part.from_bytes(
            data=self.manual_bytes,
            mime_type=self.manual_mime,
        )

        logger.info(
            "HTPPipeline ready — flash_cache=%s  pro_cache=%s",
            "ACTIVE" if self._flash_cache else "INACTIVE (inline fallback)",
            "ACTIVE" if self._pro_cache   else "INACTIVE (inline fallback)",
        )

    # ── Startup helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _load_manual(path: str) -> tuple[bytes, str]:
        """Loads the HTP manual from disk once at startup."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"HTP manual not found at '{path}'. "
                "Place book_htp_combined.pdf in the resources/ folder."
            )
        mime = "application/pdf" if p.suffix.lower() == ".pdf" else "text/plain"
        return p.read_bytes(), mime

    def _create_cache(self, model_name: str, display_name: str) -> Optional[str]:
        """
        Registers the HTP manual as a Vertex AI Context Cache for the given model.

        Returns the cache resource name (a string like
        'projects/.../locations/.../cachedContents/...')
        which is passed as cached_content= in subsequent GenerateContentConfig calls.

        Returns None if:
          - The PDF exceeds CACHE_MAX_INLINE_MB (upload to GCS to fix this).
          - The API call fails for any reason (quota, permissions, region issue).
        In both cases a warning is logged and the pipeline falls back to sending
        the manual inline with each request.
        """
        # ── Prevent creating duplicate caches to save money ────────────────────
        try:
            for existing_cache in self.client.caches.list():
                if existing_cache.display_name == display_name:
                    logger.info("Found existing context cache — model=%s  name=%s", model_name, existing_cache.name)
                    return existing_cache.name
        except Exception as exc:
            logger.warning("Failed to list existing caches: %s", exc)

        size_mb = len(self.manual_bytes) / (1024 * 1024)

        if size_mb > cfg.CACHE_MAX_INLINE_MB and not cfg.HTP_MANUAL_GCS_URI:
            logger.warning(
                "Manual is %.1f MB which exceeds the %.0f MB inline-cache limit. "
                "Context caching DISABLED for %s. "
                "To enable caching for large manuals, upload the PDF to a GCS bucket "
                "and set HTP_MANUAL_GCS_URI in your environment.",
                size_mb, cfg.CACHE_MAX_INLINE_MB, model_name,
            )
            return None

        # Decide whether to use inline bytes or a GCS URI depending on configuration and size
        if cfg.HTP_MANUAL_GCS_URI:
            manual_part = types.Part.from_uri(
                file_uri=cfg.HTP_MANUAL_GCS_URI,
                mime_type=self.manual_mime,
            )
            logger.info("Using GCS URI for context cache: %s", cfg.HTP_MANUAL_GCS_URI)
        else:
            manual_part = types.Part.from_bytes(
                data=self.manual_bytes,
                mime_type=self.manual_mime,
            )

        try:
            cache = self.client.caches.create(
                model=model_name,
                config=CreateCachedContentConfig(
                    contents=[
                        Content(
                            role="user",
                            parts=[manual_part],
                        )
                    ],
                    display_name=display_name,
                    ttl=f"{cfg.CACHE_TTL_SECONDS}s",
                ),
            )
            tokens = getattr(cache.usage_metadata, "total_token_count", "?")
            logger.info(
                "Context cache created — model=%s  name=%s  tokens=%s  ttl=%ds",
                model_name,
                cache.name,
                tokens,
                cfg.CACHE_TTL_SECONDS,
            )
            return cache.name

        except Exception as exc:
            logger.warning(
                "Context cache creation failed for %s: %s. "
                "Falling back to sending manual inline with each request.",
                model_name,
                exc,
            )
            return None

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _image_part(image_bytes: bytes, filename: str) -> types.Part:
        """Builds a Gemini Part from raw image bytes, detecting MIME type from filename."""
        mime, _ = mimetypes.guess_type(filename)
        if not mime or not mime.startswith("image/"):
            mime = "image/png"
        return types.Part.from_bytes(data=image_bytes, mime_type=mime)

    def _manual_inline(self) -> types.Part:
        """Returns the pre-encoded manual Part (used only when the cache is inactive)."""
        return self._manual_part_fallback

    def _log_usage(self, phase: str, label: str, response: Any) -> None:
        """Logs input / output / cached / total token counts from a Gemini response."""
        u = getattr(response, "usage_metadata", None)
        if not u:
            return
        cached = getattr(u, "cached_content_token_count", 0) or 0
        logger.info(
            "Tokens [%s | %s]  input=%s  output=%s  cached=%s  total=%s",
            phase,
            label,
            getattr(u, "prompt_token_count",    "?"),
            getattr(u, "candidates_token_count", "?"),
            cached,
            getattr(u, "total_token_count",      "?"),
        )

    async def _call_with_retry(self, coro_fn, label: str = "", timeout_seconds: float = 200.0) -> Any:
        """
        Calls an async callable with exponential back-off + random jitter and a timeout.

        Retries ONLY on 429 / RESOURCE_EXHAUSTED quota errors, which are
        temporary contention events on Vertex AI's Dynamic Shared Quota.
        Any other exception propagates immediately without retry.

        Back-off formula:  wait = min(BASE * 2^attempt + jitter(0..1), MAX_DELAY)
        """
        for attempt in range(cfg.RETRY_MAX_ATTEMPTS):
            try:
                return await asyncio.wait_for(coro_fn(), timeout=timeout_seconds)

            except asyncio.TimeoutError:
                logger.error("Timeout [%s] after %.1fs", label, timeout_seconds)
                raise
            except Exception as exc:
                is_quota_error = any(
                    kw in str(exc)
                    for kw in ("429", "RESOURCE_EXHAUSTED", "quota", "rate limit")
                )
                if not is_quota_error:
                    raise  # Non-quota errors bubble up immediately

                if attempt == cfg.RETRY_MAX_ATTEMPTS - 1:
                    logger.error(
                        "Max retries (%d) reached for [%s]: %s",
                        cfg.RETRY_MAX_ATTEMPTS, label, exc,
                    )
                    raise

                delay = min(
                    cfg.RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0.0, 1.0),
                    cfg.RETRY_MAX_DELAY,
                )
                logger.warning(
                    "Rate limited [%s] — attempt %d/%d, retrying in %.1fs",
                    label, attempt + 1, cfg.RETRY_MAX_ATTEMPTS, delay,
                )
                await asyncio.sleep(delay)

    # ── Phase 1: Feature extraction (Flash, no manual) ─────────────────────────

    async def _extract_features(
        self,
        image_bytes: bytes,
        filename: str,
        drawing_type: str,
        is_combined: bool = False,
    ) -> DrawingFeatures:
        """
        Sends one drawing image to Gemini Flash and gets back structured
        DrawingFeatures via response_schema (no manual parsing needed).
        The manual is NOT sent here — Phase 1 is purely visual feature extraction.
        """
        prompt_text = build_extraction_prompt(drawing_type, is_combined_sheet=is_combined)
        contents    = [
            self._image_part(image_bytes, filename),
            types.Part.from_text(text=prompt_text),
        ]
        gen_config = GenerateContentConfig(
            temperature=0.0,                    # Deterministic for feature extraction
            response_mime_type="application/json",
            response_schema=DrawingFeatures,    # Gemini enforces the schema
        )

        response = await self._call_with_retry(
            lambda: self.client.aio.models.generate_content(
                model=cfg.FLASH_MODEL,
                contents=contents,
                config=gen_config,
            ),
            label=f"Phase1/{drawing_type}",
        )
        self._log_usage("Phase1", drawing_type, response)
        logger.info("Phase 1 — %s extraction done.", drawing_type)

        try:
            data = json.loads(response.text)
            data["drawing_type"] = drawing_type  # Guarantee correct type label
            return DrawingFeatures(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse Phase 1 %s response: %s", drawing_type, exc)
            raise RuntimeError(f"Invalid Phase 1 response format for {drawing_type}: {exc}") from exc

    # ── Phase 2: Individual interpretation (Flash, cached manual) ──────────────

    async def _interpret_drawing(
        self,
        features: DrawingFeatures,
        image_bytes: bytes,
        filename: str,
        patient_context_summary: str,
    ) -> str:
        """
        Sends extracted features + original image to Gemini Flash for clinical
        interpretation.  The HTP manual is served from the server-side context
        cache (if available) rather than re-uploaded, saving ~90 % of manual
        input-token cost.
        """
        prompt_text = build_interpretation_prompt(
            drawing_type=features.drawing_type,
            features_json=features.model_dump_json(indent=2),
            patient_context_summary=patient_context_summary,
        )

        if self._flash_cache:
            # Manual is in the cache — contents only need the image + prompt
            contents   = [
                self._image_part(image_bytes, filename),
                types.Part.from_text(text=prompt_text),
            ]
            gen_config = GenerateContentConfig(
                temperature=0.2,
                cached_content=self._flash_cache,
            )
        else:
            # Fallback: send the manual inline (original behaviour)
            contents   = [
                self._manual_inline(),
                self._image_part(image_bytes, filename),
                types.Part.from_text(text=prompt_text),
            ]
            gen_config = GenerateContentConfig(temperature=0.2)

        response = await self._call_with_retry(
            lambda: self.client.aio.models.generate_content(
                model=cfg.FLASH_MODEL,
                contents=contents,
                config=gen_config,
            ),
            label=f"Phase2/{features.drawing_type}",
        )
        self._log_usage("Phase2", features.drawing_type, response)
        logger.info("Phase 2 — %s interpretation done.", features.drawing_type)
        return response.text

    # ── Phase 3: Synthesis (Pro, cached manual + all images) ───────────────────

    async def _synthesise(
        self,
        reports: dict[str, tuple[DrawingFeatures, str]],
        images: dict[str, tuple[bytes, str]],
        patient_context_summary: str,
    ) -> str:
        """
        Sends all individual interpretation reports + all raw images to Gemini Pro
        for the final integrated clinical synthesis.
        The manual is served from the Pro context cache (if available).
        """
        prompt_text = build_synthesis_prompt(
            house_report  = reports.get("House",  (None, ""))[1],
            tree_report   = reports.get("Tree",   (None, ""))[1],
            person_report = reports.get("Person", (None, ""))[1],
            ppat_report   = reports.get("PPAT",   (None, ""))[1] if "PPAT" in reports else "",
            patient_context_summary=patient_context_summary,
        )

        # Images sent in a fixed clinical order
        image_parts = [
            self._image_part(images[dt][0], images[dt][1])
            for dt in ("House", "Tree", "Person", "PPAT")
            if dt in images
        ]

        if self._pro_cache:
            contents   = image_parts + [types.Part.from_text(text=prompt_text)]
            gen_config = GenerateContentConfig(
                temperature=0.2,
                cached_content=self._pro_cache,
            )
        else:
            contents   = [self._manual_inline()] + image_parts + [types.Part.from_text(text=prompt_text)]
            gen_config = GenerateContentConfig(temperature=0.2)

        response = await self._call_with_retry(
            lambda: self.client.aio.models.generate_content(
                model=cfg.PRO_MODEL,
                contents=contents,
                config=gen_config,
            ),
            label="Phase3/Synthesis",
        )
        self._log_usage("Phase3", "Synthesis", response)
        logger.info("Phase 3 — synthesis done.")
        return response.text

    # ── Public entry point ─────────────────────────────────────────────────────

    async def run_assessment(
        self,
        patient_context : PatientContext,
        house_bytes     : bytes,
        house_name      : str,
        tree_bytes      : bytes,
        tree_name       : str,
        person_bytes    : bytes,
        person_name     : str,
        ppat_bytes      : Optional[bytes] = None,
        ppat_name       : Optional[str]   = None,
    ) -> AssessmentResponse:
        """
        Runs the full three-phase HTP assessment pipeline.

        Phase 1 and Phase 2 execute in parallel (asyncio.gather).
        Phase 3 is a single sequential call after Phase 2 completes.
        All phases use exponential back-off retry on quota errors.
        """
        start = time.perf_counter()
        patient_context_summary = build_patient_context_summary(patient_context)

        # Build the image registry used throughout the pipeline
        images: dict[str, tuple[bytes, str]] = {
            "House" : (house_bytes,  house_name),
            "Tree"  : (tree_bytes,   tree_name),
            "Person": (person_bytes, person_name),
        }
        if ppat_bytes and ppat_name:
            images["PPAT"] = (ppat_bytes, ppat_name)

        drawing_types = list(images.keys())

        # ── Phase 1: Parallel feature extraction ──────────────────────────────
        logger.info(
            "=== Phase 1 started — extracting features from %d drawings in parallel ===",
            len(images),
        )
        extracted: list[DrawingFeatures] = await asyncio.gather(*[
            self._extract_features(
                image_bytes=images[dt][0],
                filename   =images[dt][1],
                drawing_type=dt,
            )
            for dt in drawing_types
        ])
        features_map: dict[str, DrawingFeatures] = {f.drawing_type: f for f in extracted}
        logger.info("=== Phase 1 complete ===")

        # ── Phase 2: Parallel interpretation ──────────────────────────────────
        logger.info(
            "=== Phase 2 started — generating %d interpretation reports in parallel ===",
            len(images),
        )
        interpretations: list[str] = await asyncio.gather(*[
            self._interpret_drawing(
                features               =features_map[dt],
                image_bytes            =images[dt][0],
                filename               =images[dt][1],
                patient_context_summary=patient_context_summary,
            )
            for dt in drawing_types
        ])
        reports_map: dict[str, tuple[DrawingFeatures, str]] = {
            dt: (features_map[dt], interpretations[i])
            for i, dt in enumerate(drawing_types)
        }
        logger.info("=== Phase 2 complete ===")

        # ── Phase 3: Synthesis ─────────────────────────────────────────────────
        logger.info("=== Phase 3 started — generating synthesis report ===")
        synthesis = await self._synthesise(reports_map, images, patient_context_summary)
        logger.info("=== Phase 3 complete ===")

        # ── Assemble response ──────────────────────────────────────────────────
        elapsed            = round(time.perf_counter() - start, 2)
        overall_confidence = (
            sum(f.confidence_score for f in features_map.values()) / len(features_map)
            if features_map else 0.0
        )
        low_conf_warning   = any(f.confidence_score < 0.50 for f in features_map.values())

        def _make_report(dt: str) -> IndividualReport:
            feat, interp = reports_map[dt]
            return IndividualReport(drawing_type=dt, features=feat, interpretation=interp)

        result = AssessmentResponse(
            patient_id              = patient_context.patient_id,
            disclaimer              = DISCLAIMER,
            house_report            = _make_report("House"),
            tree_report             = _make_report("Tree"),
            person_report           = _make_report("Person"),
            ppat_report             = _make_report("PPAT") if "PPAT" in reports_map else None,
            synthesis_report        = synthesis,
            overall_confidence      = round(overall_confidence, 2),
            low_confidence_warning  = low_conf_warning,
            processing_time_seconds = elapsed,
        )

        logger.info(
            "Assessment complete — patient_id=%s  confidence=%.2f  time=%.2fs  low_conf_warning=%s",
            patient_context.patient_id,
            overall_confidence,
            elapsed,
            low_conf_warning,
        )
        return result
