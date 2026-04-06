"""
Enriquecimiento del documento con descripciones de imágenes.

Responsabilidad única: extraer imágenes del PDF con pymupdf, filtrar las
relevantes por tamaño y añadir sus descripciones al texto del documento
en la página donde aparecen, no al final del documento.
La descripción visual la genera OllamaClient.describe_image() con LLaVA.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # pymupdf

from config.settings import VISION_MIN_IMAGE_WIDTH, VISION_MIN_IMAGE_HEIGHT
from src.domain.models import ExtractedDocument
from src.ai.ollama_client import OllamaClient
from src.extraction.pdf_reader import extract_pages


def enrich_with_vision(
    document: ExtractedDocument,
    pdf_path: str | Path,
    client: OllamaClient,
) -> tuple[ExtractedDocument, int]:
    """
    Extrae las imágenes del PDF, las describe con el modelo de visión y
    las inserta en el raw_text en la página donde aparecen.

    Returns:
        (document_enriquecido, numero_imagenes_descritas)
        El documento devuelto es el mismo objeto modificado in-place.
    """
    pdf_path = Path(pdf_path)
    descriptions_by_page = _extract_descriptions_by_page(pdf_path, client)

    if not descriptions_by_page:
        return document, 0

    # Reconstruir raw_text insertando las descripciones en su página
    pages_text = extract_pages(pdf_path)
    enriched: list[str] = []
    for i, page_text in enumerate(pages_text):
        if page_text:
            enriched.append(page_text)
        for j, desc in enumerate(descriptions_by_page.get(i, [])):
            enriched.append(f"[Imagen página {i + 1}]: {desc}")

    document.raw_text = "\n\n".join(enriched)

    total = sum(len(descs) for descs in descriptions_by_page.values())
    return document, total


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _extract_descriptions_by_page(
    pdf_path: Path,
    client: OllamaClient,
) -> dict[int, list[str]]:
    """
    Devuelve un dict {índice_página: [descripción, ...]} con las imágenes
    que superan el umbral de tamaño. Deduplica imágenes repetidas entre páginas
    (mismo xref = misma imagen, ej. logos de cabecera).
    """
    result: dict[int, list[str]] = {}
    seen_xrefs: set[int] = set()

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return result

    for page_idx, page in enumerate(doc):
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                base_image = doc.extract_image(xref)
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                if width < VISION_MIN_IMAGE_WIDTH or height < VISION_MIN_IMAGE_HEIGHT:
                    continue
                image_bytes = base_image["image"]
                description = client.describe_image(image_bytes)
                if description:
                    result.setdefault(page_idx, []).append(description)
            except Exception:
                continue

    doc.close()
    return result
