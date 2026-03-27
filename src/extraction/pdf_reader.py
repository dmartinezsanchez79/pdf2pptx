"""
Lectura del PDF.

Responsabilidad única: abrir el archivo, extraer el texto por páginas
y devolver un ExtractedDocument con el texto bruto y las secciones detectadas.
No limpia ni segmenta: eso lo hace text_cleaner.
"""

from pathlib import Path

import pdfplumber

from src.domain.models import DocumentSection, ExtractedDocument
from src.extraction.text_cleaner import clean_and_segment


def read_pdf(path: str | Path) -> ExtractedDocument:
    """
    Lee un PDF y devuelve un ExtractedDocument.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el PDF está vacío o no contiene texto extraíble.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")

    pages_text = _extract_pages(pdf_path)

    if not any(pages_text):
        raise ValueError(
            "El PDF no contiene texto extraíble. "
            "Puede ser un PDF escaneado (imagen). Se necesitaría OCR."
        )

    raw_text = "\n\n".join(t for t in pages_text if t)
    title = _infer_title(pages_text)
    sections = clean_and_segment(raw_text)

    return ExtractedDocument(title=title, sections=sections, raw_text=raw_text, filename=pdf_path.stem)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _extract_pages(pdf_path: Path) -> list[str]:
    """Extrae el texto de cada página como lista de strings."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text.strip())
    return pages


def _infer_title(pages_text: list[str]) -> str:
    """
    Intenta deducir el título del documento a partir de la primera página.
    Usa la primera línea no vacía de la primera página como título.
    Si no hay nada, devuelve un título genérico.
    """
    if not pages_text:
        return "Documento sin título"

    first_page = pages_text[0]
    for line in first_page.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]  # recortamos si es demasiado largo

    return "Documento sin título"
