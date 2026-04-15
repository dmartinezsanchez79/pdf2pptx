"""
Lectura del PDF.

Responsabilidad única: abrir el archivo, extraer el texto por páginas
y devolver un ExtractedDocument con el texto bruto y las secciones detectadas.
No limpia ni segmenta: eso lo hace text_cleaner.
"""

import re
from pathlib import Path

import pdfplumber

from src.domain.models import ExtractedDocument
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

    pages_text = extract_pages(pdf_path)

    if not any(pages_text):
        raise ValueError(
            "El PDF no contiene texto extraíble. "
            "Puede ser un PDF escaneado (imagen). Se necesitaría OCR."
        )

    raw_text = "\n\n".join(t for t in pages_text if t)
    title = _title_from_filename(pdf_path.stem)
    sections = clean_and_segment(raw_text)

    return ExtractedDocument(title=title, sections=sections, raw_text=raw_text, filename=pdf_path.stem)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def extract_pages(pdf_path: Path) -> list[str]:
    """Extrae el texto de cada página, incluyendo tablas formateadas como markdown."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            tables_md = _extract_tables_as_markdown(page)
            page_content = text.strip()
            if tables_md:
                page_content = (page_content + "\n\n" + tables_md).strip()
            pages.append(page_content)
    return pages


def _extract_tables_as_markdown(page) -> str:
    """
    Extrae todas las tablas de una página y las convierte a formato markdown.
    Ignora tablas vacías o con una sola celda.
    """
    tables = page.extract_tables() or []
    md_blocks: list[str] = []

    for table in tables:
        if not table or len(table) < 2:
            continue
        # Limpiar celdas nulas
        cleaned = [
            [cell.strip() if cell else "" for cell in row]
            for row in table
        ]
        header = cleaned[0]
        rows = cleaned[1:]
        if not any(header) or not rows:
            continue

        # Construir tabla markdown
        sep = "| " + " | ".join("---" for _ in header) + " |"
        header_line = "| " + " | ".join(header) + " |"
        row_lines = ["| " + " | ".join(row) + " |" for row in rows]
        md_blocks.append("\n".join([header_line, sep] + row_lines))

    return "\n\n".join(md_blocks)


def _title_from_filename(stem: str) -> str:
    """
    Genera el título a partir del nombre del archivo (sin extensión).

    Inserta espacios antes de cada mayúscula en nombres CamelCase
    (e.g. "InteligenciaArtificial" → "Inteligencia Artificial")
    y reemplaza guiones bajos/guiones por espacios.
    """
    # Separar CamelCase
    title = re.sub(r'(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])', ' ', stem)
    # Reemplazar guiones y guiones bajos por espacios
    title = title.replace('_', ' ').replace('-', ' ')
    return title.strip() or "Documento sin título"
