"""
pdf_report.py — Generates a visually appealing clinical PDF report using fpdf2.

This module creates the detailed clinical document that complements the
simplified dashboard JSON. The PDF contains full Phase 2 interpretation
reports and the Phase 3 synthesis in a branded, professional format.
"""

import logging
from io import BytesIO
from datetime import datetime

from fpdf import FPDF

from prompts import DISCLAIMER

logger = logging.getLogger(__name__)

# ── Brand Colors ───────────────────────────────────────────────────────────────
COLOR_PRIMARY    = (79, 70, 229)    # Indigo-600
COLOR_SECONDARY  = (99, 102, 241)   # Indigo-500
COLOR_ACCENT     = (16, 185, 129)   # Emerald-500
COLOR_DARK       = (30, 27, 75)     # Indigo-950
COLOR_MUTED      = (100, 116, 139)  # Slate-500
COLOR_LIGHT_BG   = (241, 245, 249)  # Slate-100
COLOR_WHITE      = (255, 255, 255)
COLOR_RED        = (220, 38, 38)    # Red-600
COLOR_BORDER     = (203, 213, 225)  # Slate-300
COLOR_TEXT        = (30, 41, 59)     # Slate-800


class HTPReportPDF(FPDF):
    """Custom PDF class with PsychConnect branding."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        """Page header with branding stripe."""
        # Top accent bar
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 4, "F")

        # Logo text
        self.set_y(10)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 6, "PsychConnect", new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 4, "AI-Assisted HTP Assessment Report", new_x="LMARGIN", new_y="NEXT")

        # Separator line
        self.set_draw_color(*COLOR_BORDER)
        self.line(10, 24, 200, 24)
        self.set_y(28)

    def footer(self):
        """Page footer with page number and disclaimer."""
        self.set_y(-20)
        self.set_draw_color(*COLOR_BORDER)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-17)
        self.set_font("Helvetica", "I", 6.5)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 4, "AI-assistive tool only - not for diagnosis without clinical review", align="L")
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")

    def _ensure_space(self, min_height: float) -> None:
        """
        If there is less than `min_height` mm remaining on the current page
        before the bottom margin, insert a page break now.
        This prevents orphaned titles and cards that start at the bottom of a
        page and push their content to the next page, leaving a blank gap.
        """
        remaining = self.h - self.b_margin - self.get_y()
        if remaining < min_height:
            self.add_page()

    def _section_title(self, title: str):
        """Render a styled section heading."""
        # Require at least 35 mm so the title + first line of content fit together
        self._ensure_space(35)
        self.ln(4)
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(10, self.get_y(), 3, 7, "F")
        self.set_x(16)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*COLOR_DARK)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _subsection_title(self, title: str):
        """Render a smaller subsection heading."""
        # Require at least 20 mm so subtitle + first observation row fit together
        self._ensure_space(20)
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def _body_text(self, text: str):
        """Render body text with proper formatting."""
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*COLOR_TEXT)
        self.multi_cell(0, 4.5, self._sanitize(text))
        self.ln(1)

    def _info_box(self, text: str, bg_color=COLOR_LIGHT_BG, border_color=COLOR_BORDER):
        """Render a highlighted info box."""
        text = self._sanitize(text)
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*bg_color)
        self.set_draw_color(*border_color)
        # Calculate height needed
        self.set_font("Helvetica", "", 8)
        w = self.w - 2 * self.l_margin - 6
        lines = self._estimate_lines(text, w)
        h = max(lines * 4.5 + 6, 12)
        self.rect(x, y, self.w - 2 * self.l_margin, h, "DF")
        self.set_xy(x + 3, y + 3)
        self.set_text_color(*COLOR_TEXT)
        self.multi_cell(w, 4.5, text)
        self.set_y(y + h + 2)

    @staticmethod
    def _sanitize(text: str) -> str:
        """
        Replace common Unicode symbols with ASCII equivalents, then drop any
        remaining characters outside the Latin-1 range (0-255) so that fpdf2
        with its built-in Helvetica font never raises FPDFUnicodeEncodingException.
        """
        replacements = {
            "\u2019": "'",   # right single quotation mark
            "\u2018": "'",   # left single quotation mark
            "\u201c": '"',   # left double quotation mark
            "\u201d": '"',   # right double quotation mark
            "\u2014": "--",  # em dash
            "\u2013": "-",   # en dash
            "\u2026": "...", # ellipsis
            "\u2022": "-",   # bullet
            "\u2023": "-",   # triangular bullet
            "\u25cf": "-",   # black circle
            "\u2192": "->",  # right arrow
            "\u2190": "<-",  # left arrow
            "\u2713": "[x]", # check mark
            "\u2717": "[ ]", # ballot x
            "\u26a0": "[!]", # warning sign
            "\u2764": "<3",  # heart
            "\u00e2\u0080\u0099": "'",  # UTF-8 artifact for '
        }
        for uni, asc in replacements.items():
            text = text.replace(uni, asc)
        # Drop anything still outside Latin-1
        return text.encode("latin-1", errors="ignore").decode("latin-1")

    def _estimate_lines(self, text: str, width: float) -> int:
        """Estimate number of lines a text will occupy."""
        text = self._sanitize(text)
        words = text.split()
        if not words:
            return 1
        lines = 1
        current_width = 0
        for word in words:
            word_width = self.get_string_width(word + " ")
            if current_width + word_width > width:
                lines += 1
                current_width = word_width
            else:
                current_width += word_width
        return lines

    def _observation_row(self, feature: str, interpretation: str):
        """Render a feature to interpretation row."""
        feature = self._sanitize(feature)
        interpretation = self._sanitize(interpretation)
        y_start = self.get_y()

        # Feature column (left 40%)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*COLOR_DARK)
        x_start = self.get_x()
        col_w = 70
        self.multi_cell(col_w, 4.2, feature)
        y_after_feature = self.get_y()

        # Interpretation column (right 60%)
        self.set_xy(x_start + col_w + 4, y_start)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*COLOR_TEXT)
        interp_w = self.w - 2 * self.l_margin - col_w - 4
        self.multi_cell(interp_w, 4.2, interpretation)
        y_after_interp = self.get_y()

        # Move to whichever column was taller
        self.set_y(max(y_after_feature, y_after_interp))

        # Subtle separator
        self.set_draw_color(*COLOR_LIGHT_BG)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def _risk_flag(self, flag_text: str):
        """Render a risk flag alert."""
        flag_text = self._sanitize(flag_text)
        self.set_font("Helvetica", "", 8)
        w = self.w - 2 * self.l_margin
        lines = self._estimate_lines(f"[!] {flag_text}", w - 6)
        h = max(lines * 4.5 + 6, 10)
        # Ensure the whole box fits on this page
        self._ensure_space(h + 4)
        y = self.get_y()
        self.set_fill_color(254, 226, 226)  # Red-100
        self.set_draw_color(*COLOR_RED)
        self.rect(self.l_margin, y, w, h, "DF")
        self.set_xy(self.l_margin + 3, y + 3)
        self.set_text_color(*COLOR_RED)
        self.set_font("Helvetica", "B", 8)
        self.multi_cell(w - 6, 4.5, f"ALERT: {flag_text}")
        self.set_y(max(self.get_y(), y + h) + 2)

    def _theme_card(self, theme: str, evidence: str, severity: str):
        """Render a theme card with severity badge."""
        theme    = self._sanitize(theme)
        evidence = self._sanitize(evidence)

        # Severity colors
        sev_colors = {
            "low":      ((22, 163, 74),  (220, 252, 231)),   # Green
            "moderate": ((202, 138, 4),  (254, 249, 195)),   # Yellow
            "high":     ((220, 38, 38),  (254, 226, 226)),   # Red
        }
        text_c, bg_c = sev_colors.get(severity.lower(), sev_colors["moderate"])

        w = self.w - 2 * self.l_margin

        # Estimate height with a 30% safety buffer to prevent content overflow
        self.set_font("Helvetica", "", 8)
        ev_lines = self._estimate_lines(evidence, w - 10)
        h = (22 + ev_lines * 4.5) * 1.3  # 30% buffer

        # Ensure the whole card fits on this page before drawing the background rect
        self._ensure_space(h + 4)
        y = self.get_y()  # Re-read y AFTER potential page break

        # Card background
        self.set_fill_color(*COLOR_LIGHT_BG)
        self.set_draw_color(*COLOR_BORDER)
        self.rect(self.l_margin, y, w, h, "DF")

        # Severity badge
        self.set_xy(self.l_margin + 4, y + 3)
        badge_w = self.get_string_width(severity.upper()) + 6
        self.set_fill_color(*bg_c)
        self.set_draw_color(*text_c)
        self.rect(self.get_x(), self.get_y(), badge_w, 5, "DF")
        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(*text_c)
        self.cell(badge_w, 5, severity.upper(), align="C")

        # Theme name
        self.set_xy(self.l_margin + 4 + badge_w + 4, y + 3)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*COLOR_DARK)
        self.cell(0, 5, theme)

        # Evidence — disable auto page-break while inside the card
        self.set_xy(self.l_margin + 5, y + 12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*COLOR_TEXT)
        prev_break = self.will_page_break(h)  # peek
        self.set_auto_page_break(False)
        self.multi_cell(w - 10, 4.5, evidence)
        self.set_auto_page_break(True, self.b_margin)

        # Advance past the card (use whichever is lower: actual cursor or estimated end)
        self.set_y(max(self.get_y(), y + h) + 3)


def generate_pdf_report(
    patient_context_summary: str,
    house_interpretation: str,
    tree_interpretation: str,
    person_interpretation: str,
    synthesis_data: dict,
    features_map: dict,
) -> bytes:
    """
    Generates a branded clinical PDF report.

    Args:
        patient_context_summary: Formatted patient demographic string
        house_interpretation: Phase 2 text report for House
        tree_interpretation: Phase 2 text report for Tree
        person_interpretation: Phase 2 text report for Person
        synthesis_data: Phase 3 structured JSON output
        features_map: Dict of DrawingFeatures per drawing type

    Returns:
        PDF file as bytes
    """
    pdf = HTPReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── Title Page Content ─────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*COLOR_DARK)
    pdf.cell(0, 10, "HTP Assessment Report", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COLOR_MUTED)
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    pdf.cell(0, 6, f"Generated on {now}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Disclaimer box
    pdf._info_box(DISCLAIMER, bg_color=(254, 249, 195), border_color=(202, 138, 4))
    pdf.ln(4)

    # ── Patient Context ────────────────────────────────────────────────────
    pdf._section_title("Patient Context")
    for line in patient_context_summary.strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_DARK)
            pdf.cell(55, 5, key.strip() + ":")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_TEXT)
            pdf.cell(0, 5, val.strip(), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf._body_text(line)
    pdf.ln(2)

    # ── Clinical Impression ────────────────────────────────────────────────
    pdf._section_title("Clinical Impression")
    impression = HTPReportPDF._sanitize(synthesis_data.get("clinical_impression", ""))
    pdf._body_text(impression)

    # ── Risk Flags ─────────────────────────────────────────────────────────
    risk_flags = synthesis_data.get("risk_flags", [])
    if risk_flags:
        pdf._section_title("Risk Flags")
        for flag in risk_flags:
            pdf._risk_flag(flag)

    # ── Key Themes ─────────────────────────────────────────────────────────
    pdf._section_title("Key Themes")
    for theme_item in synthesis_data.get("key_themes", []):
        pdf._theme_card(
            theme=theme_item.get("theme", ""),
            evidence=theme_item.get("evidence", ""),
            severity=theme_item.get("severity", "moderate"),
        )

    # ── Drawing Analyses ───────────────────────────────────────────────────
    drawing_reports = {
        "House":  house_interpretation,
        "Tree":   tree_interpretation,
        "Person": person_interpretation,
    }

    obs_keys = {
        "House":  "house_observations",
        "Tree":   "tree_observations",
        "Person": "person_observations",
    }

    for drawing_type, report_text in drawing_reports.items():
        pdf.add_page()
        pdf._section_title(f"{drawing_type} Drawing Analysis")

        # Confidence badge
        feat = features_map.get(drawing_type)
        if feat:
            conf = feat.confidence_score
            conf_label = f"Analysis Confidence: {conf:.0%}"
            if conf >= 0.8:
                badge_color = (22, 163, 74)
            elif conf >= 0.5:
                badge_color = (202, 138, 4)
            else:
                badge_color = (220, 38, 38)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*badge_color)
            pdf.cell(0, 5, conf_label, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Observations table
        pdf._subsection_title("Observations & Interpretations")
        observations = synthesis_data.get(obs_keys.get(drawing_type, ""), [])
        for obs in observations:
            pdf._observation_row(
                feature=obs.get("feature", ""),
                interpretation=obs.get("interpretation", ""),
            )

        # Full interpretation text
        pdf._subsection_title("Detailed Interpretation")
        # Clean up the report text — remove the disclaimer line if present
        clean_text = report_text
        for remove_str in ["DISCLAIMER:", "ANALYSIS OF"]:
            lines = clean_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith(remove_str)]
            clean_text = "\n".join(lines)
        clean_text = clean_text.replace("---", "").strip()
        pdf._body_text(clean_text)

    # ── Session Focus Areas ────────────────────────────────────────────────
    pdf.add_page()
    pdf._section_title("Recommended Session Focus Areas")
    for i, area in enumerate(synthesis_data.get("session_focus_areas", []), 1):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(8, 5, f"{i}.")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COLOR_TEXT)
        pdf.multi_cell(0, 5, HTPReportPDF._sanitize(area))
        pdf.ln(2)

    # ── Questionnaire Correlation ──────────────────────────────────────────
    has_questionnaire = any(
        synthesis_data.get(k) is not None
        for k in ["phq9", "dass21_depression", "dass21_anxiety", "dass21_stress"]
    )
    if has_questionnaire:
        pdf._section_title("Questionnaire Correlation")

        q_items = [
            ("PHQ-9", synthesis_data.get("phq9")),
            ("DASS-21 Depression", synthesis_data.get("dass21_depression")),
            ("DASS-21 Anxiety", synthesis_data.get("dass21_anxiety")),
            ("DASS-21 Stress", synthesis_data.get("dass21_stress")),
        ]

        for label, q_data in q_items:
            if q_data is None:
                continue
            score = q_data.get("score", "?")
            severity = q_data.get("severity", "?")
            consistency = q_data.get("drawing_consistency", "?")

            cons_colors = {
                "consistent":    (22, 163, 74),
                "contradictory": (220, 38, 38),
                "neutral":       (202, 138, 4),
            }
            cons_color = cons_colors.get(consistency, COLOR_MUTED)

            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_DARK)
            pdf.cell(50, 5, f"{label}:")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_TEXT)
            pdf.cell(30, 5, f"Score: {score}")
            pdf.cell(40, 5, f"Severity: {severity}")
            pdf.set_text_color(*cons_color)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, consistency.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    # ── Generate PDF bytes ─────────────────────────────────────────────────
    pdf_bytes = pdf.output()
    logger.info("PDF report generated — %d pages, %.1f KB", pdf.pages_count, len(pdf_bytes) / 1024)
    return bytes(pdf_bytes)
