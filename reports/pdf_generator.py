"""
Professional PDF Report Generator for Pedne Sewa Trust - Employment Registry.
Uses ReportLab to generate publication-quality documents with Trust branding,
logo headers, structured data tables, and summary statistics.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from app.config import config
from utils.logger import logger


class NumberedCanvas(canvas.Canvas):
    """Adds page numbers and footer to each page of the generated PDF."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        text = f"Pedne Sewa Trust — Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 40, 25, text)
        self.drawString(40, 25, "Confidential — Community Employment Data")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 38, A4[0] - 40, 38)
        self.restoreState()


class PDFReportGenerator:
    """Generates official branded PDF reports."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or config.get("export_dir"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        report_title: str,
        headers: List[str],
        data_rows: List[List[Any]],
        subtitle: str = "Pernem Taluka Employment Registry",
        filter_summary: str = "All Registered Candidates",
        target_filepath: Optional[str] = None
    ) -> str:
        """
        Creates an A4 PDF document containing report tables, Trust header,
        and branding logo.
        """
        if not target_filepath:
            clean_title = "".join(c for c in report_title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_filepath = str(self.output_dir / f"PST_{clean_title}_{ts}.pdf")

        doc = SimpleDocTemplate(
            target_filepath,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()
        # Custom typography
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F234B")
        )

        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0D9488")
        )

        meta_style = ParagraphStyle(
            "ReportMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748B")
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#FFFFFF"),
            alignment=1
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1E293B")
        )

        story = []

        # 1. Header with Logo & Trust Branding
        logo_path = config.resolve_logo_path()
        header_table_data = []

        header_text = [
            Paragraph("PEDNE SEWA TRUST", title_style),
            Paragraph(subtitle, subtitle_style),
            Paragraph(f"<b>Report:</b> {report_title} | <b>Filters:</b> {filter_summary} | <b>Generated:</b> {datetime.now().strftime('%d-%b-%Y %H:%M')}", meta_style)
        ]

        if logo_path and os.path.exists(logo_path):
            try:
                logo_img = RLImage(logo_path, width=1.0 * inch, height=1.0 * inch)
                header_table_data = [[logo_img, header_text]]
            except Exception as e:
                logger.warning("Could not render logo in PDF: %s", e)
                header_table_data = [[header_text]]
        else:
            header_table_data = [[header_text]]

        header_table = Table(header_table_data, colWidths=[1.2 * inch, doc.width - 1.2 * inch] if len(header_table_data[0]) > 1 else [doc.width])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 14))

        # Horizontal accent bar
        accent_bar = Table([[""]], colWidths=[doc.width], rowHeights=[2])
        accent_bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0D9488")),
            ("PADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(accent_bar)
        story.append(Spacer(1, 16))

        # 2. Main Data Table
        # Wrap all headers and cells in Paragraphs for text wrapping
        formatted_headers = [Paragraph(str(h), table_header_style) for h in headers]
        formatted_rows = []
        for row in data_rows:
            formatted_row = [Paragraph(str(cell), table_cell_style) for cell in row]
            formatted_rows.append(formatted_row)

        table_content = [formatted_headers] + formatted_rows

        num_cols = len(headers)
        col_width = doc.width / max(1, num_cols)
        # Adapt column widths: give first column more room if it's a title/name
        col_widths = [col_width * 1.5] + [col_width * (doc.width - col_width * 1.5) / (col_width * (num_cols - 1))] * (num_cols - 1) if num_cols > 2 else [col_width] * num_cols

        data_table = Table(table_content, colWidths=col_widths, repeatRows=1)
        data_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F234B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))

        story.append(data_table)

        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        logger.info("Generated PDF report: %s", target_filepath)
        return target_filepath


pdf_generator = PDFReportGenerator()
