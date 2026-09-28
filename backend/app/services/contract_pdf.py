"""Static PDF rendering for the AMR contract template.

Only the variable zones on pages 1, 2 and 7 are painted; the legal clauses
from the approved machote are copied unchanged.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def _line(pdf: canvas.Canvas, text: str, x: float, y: float, size: int = 8) -> None:
    pdf.setFont("Helvetica", size)
    pdf.drawString(x, y, text[:110])


def _overlay(lines: list[tuple[str, float, float, int]]) -> BytesIO:
    content = BytesIO()
    pdf = canvas.Canvas(content, pagesize=letter)
    pdf.setFillColorRGB(0, 0, 0)
    for text, x, y, size in lines:
        _line(pdf, text, x, y, size)
    pdf.save(); content.seek(0)
    return content


def render_contract(template: Path, destination: Path, values: dict[str, str]) -> None:
    """Overlay the reviewed variable fields and create one immutable PDF."""
    reader = PdfReader(str(template))
    writer = PdfWriter()
    page_lines = {
        0: [
            (values["customer_name"], 115, 612, 9),
            (values["address"], 115, 581, 8),
            (values["phone"], 115, 550, 9),
            (values["plan"], 360, 550, 9),
            (values["monthly_price"], 360, 519, 9),
            (values["payment_day"], 360, 488, 9),
            (values["equipment"], 115, 410, 8),
            (values["contract_date"], 360, 410, 9),
        ],
        1: [(values["contract_number"], 438, 696, 10)],
        6: [
            (values["promissory_amount"], 400, 611, 9),
            (values["contract_date"], 120, 580, 9),
            (values["promissory_due_date"], 395, 580, 9),
            (values["customer_name"], 120, 510, 9),
            (values["address"], 120, 480, 8),
        ],
    }
    for index, page in enumerate(reader.pages):
        if index in page_lines:
            page.merge_page(PdfReader(_overlay(page_lines[index])).pages[0])
        writer.add_page(page)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream:
        writer.write(stream)
