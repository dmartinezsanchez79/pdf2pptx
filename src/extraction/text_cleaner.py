"""
Limpieza y segmentación del texto extraído del PDF.

Responsabilidades:
  1. Limpiar ruido tipográfico (cabeceras repetidas, pies de página, guiones de corte de línea...).
  2. Segmentar el texto en DocumentSection cuando se detectan encabezados.
  3. Dividir el texto en chunks del tamaño adecuado para la ventana de contexto del modelo.
"""

import re

from src.domain.models import DocumentSection
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, PDF_MAX_CHUNKS


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def clean_and_segment(raw_text: str) -> list[DocumentSection]:
    """Limpia el texto y lo divide en secciones lógicas."""
    cleaned = _clean(raw_text)
    return _segment(cleaned)


def clean_for_quiz(raw_text: str) -> str:
    """
    Limpieza agresiva específica para el quiz.
    Elimina metadatos, URLs, contenido editorial y ruido que no tiene
    valor pedagógico y que contaminaría las preguntas generadas.
    No se usa en el pipeline PPTX para no perder contexto de las secciones.
    """
    text = _clean(raw_text)
    text = _remove_urls(text)
    text = _remove_metadata_lines(text)
    text = _remove_noise_lines(text)
    return text.strip()


def split_into_chunks(text: str) -> list[str]:
    """
    Divide el texto en fragmentos solapados aptos para la ventana de contexto del modelo.
    Respeta PDF_MAX_CHUNKS para no procesar documentos enormes indefinidamente.

    Estrategia: cortar preferiblemente en saltos de párrafo (\n\n)
    para no romper ideas a mitad.
    """
    if not text.strip():
        return []

    chunks: list[str] = []
    start = 0

    while start < len(text) and len(chunks) < PDF_MAX_CHUNKS:
        end = start + CHUNK_SIZE

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Intentar cortar en el último doble salto de línea antes de `end`
        cut = text.rfind("\n\n", start, end)
        if cut == -1 or cut <= start:
            # Si no hay párrafo, cortar en el último espacio
            cut = text.rfind(" ", start, end)
        if cut == -1 or cut <= start:
            cut = end  # forzar corte duro si no hay separador

        chunks.append(text[start:cut].strip())
        start = cut - CHUNK_OVERLAP  # retroceder el solapamiento

    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    text = _remove_hyphenation(text)
    text = _normalize_whitespace(text)
    text = _remove_repeated_headers(text)
    text = _remove_page_numbers(text)
    return text.strip()


def _remove_hyphenation(text: str) -> str:
    """Une palabras partidas con guión al final de línea: 'infor-\nmación' → 'información'."""
    return re.sub(r"-\n(\w)", r"\1", text)


def _normalize_whitespace(text: str) -> str:
    """Colapsa espacios múltiples en uno. Preserva los saltos de párrafo (\n\n)."""
    # Primero protegemos los párrafos
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Colapsar espacios dentro de línea
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _remove_repeated_headers(text: str) -> str:
    """
    Elimina líneas que se repiten más de 3 veces a lo largo del documento
    (síntoma típico de cabeceras/pies de página repetidos en cada página).
    """
    lines = text.splitlines()
    from collections import Counter
    counts = Counter(line.strip() for line in lines if line.strip())
    repeated = {line for line, n in counts.items() if n > 3 and len(line) < 120}
    filtered = [line for line in lines if line.strip() not in repeated]
    return "\n".join(filtered)


def _remove_page_numbers(text: str) -> str:
    """Elimina líneas que solo contienen un número (número de página)."""
    return re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# Limpieza agresiva para quiz
# ---------------------------------------------------------------------------

def _remove_urls(text: str) -> str:
    """Elimina URLs, direcciones web y correos electrónicos."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    return text


def _remove_metadata_lines(text: str) -> str:
    """
    Elimina líneas que contienen metadatos editoriales sin valor pedagógico:
    ISBN, precios, derechos de autor, editoriales, números de depósito legal,
    bios de autor, citas de contraportada.
    """
    _META_PATTERNS = [
        r'ISBN[\s\-:]?\d',
        r'©|Copyright|All rights reserved|Todos los derechos reservados',
        r'Primera edición|Segunda edición|[\w\s]+ edición.*\d{4}',
        r'Impreso en|Printed in',
        r'Depósito legal|D\.L\.',
        r'\$\s*\d+|\€\s*\d+|\bprecio\b',
        r'\beditorial\b.{0,40}\bS\.?A\.?\b',
        r'Reservados todos los derechos',
        r'queda prohibida la reproducción',
        r'\bcoautor\b|\bautor de\b|\bautora de\b',       # bios de autor
        r'\bha impartido\b|\bha publicado\b|\bha escrito\b',  # bio estilo CV
        r'\bconferenci(ante|as)\b|\bseminarios?\b.{0,30}\bpaíses?\b',  # bio de ponente
        r'\w+_FIN\b',                                    # artefactos de exportadores PDF (nombrearchivo_FIN)
        r'^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$',            # fechas aisladas
    ]
    lines = text.splitlines()
    filtered = [
        line for line in lines
        if not any(re.search(p, line.strip(), re.IGNORECASE) for p in _META_PATTERNS)
    ]
    return '\n'.join(filtered)


def _remove_noise_lines(text: str) -> str:
    """
    Elimina líneas que son claramente ruido:
    solo números, teléfonos, líneas de 1-2 palabras aisladas,
    líneas que son solo puntuación o símbolos, entradas de índice/sumario.
    """
    _NOISE_PATTERNS = [
        r'^[\d\s\.\-\(\)\/\+]+$',               # solo números y símbolos
        r'^tel[éefono]*[\s\.:]+[\d\s\-\+\(\)]+', # teléfonos
        r'^fax[\s\.:]+[\d\s\-\+\(\)]+',          # fax
        r'^\s*https?://',                         # URL como línea
        r'^\s*www\.',                             # web como línea
        r'^[•·\-–—\*]+\s*$',                     # solo viñetas o guiones
        r'[\.\s]{4,}\d{1,4}\s*$',               # entrada de índice: "Capítulo . . . . 42"
        r'^\d+(\.\d+)*\s+.{5,60}[\.\s]{4,}\d+\s*$',  # "1. Título . . . . 15"
    ]
    lines = text.splitlines()
    filtered = [
        line for line in lines
        if not any(re.search(p, line.strip(), re.IGNORECASE) for p in _NOISE_PATTERNS)
    ]
    return '\n'.join(filtered)


# ---------------------------------------------------------------------------
# Segmentación
# ---------------------------------------------------------------------------

def _segment(text: str) -> list[DocumentSection]:
    """
    Divide el texto en DocumentSection.
    Detecta encabezados como líneas cortas en mayúsculas o seguidas de \n\n
    con la heurística de que son cortas y no terminan en punto.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if not paragraphs:
        return [DocumentSection(heading=None, body=text.strip())]

    sections: list[DocumentSection] = []
    current_heading: str | None = None
    current_body_parts: list[str] = []

    for para in paragraphs:
        if _is_heading(para):
            if current_body_parts:
                sections.append(DocumentSection(
                    heading=current_heading,
                    body="\n\n".join(current_body_parts),
                ))
            current_heading = para
            current_body_parts = []
        else:
            current_body_parts.append(para)

    # Último bloque pendiente
    if current_body_parts:
        sections.append(DocumentSection(
            heading=current_heading,
            body="\n\n".join(current_body_parts),
        ))

    return sections if sections else [DocumentSection(heading=None, body=text)]


def _is_heading(para: str) -> bool:
    """
    Heurística para detectar si un párrafo es un encabezado:
      - Una sola línea.
      - Menos de 80 caracteres.
      - No termina en punto.
      - Empieza por mayúscula o número de sección (ej. "1.", "2.1").
    """
    lines = para.splitlines()
    if len(lines) != 1:
        return False

    text = para.strip()
    if len(text) > 80:
        return False
    if text.endswith("."):
        return False

    starts_with_capital = text[0].isupper() if text else False
    starts_with_section_number = bool(re.match(r"^\d+(\.\d+)*[\s\.]", text))

    return starts_with_capital or starts_with_section_number
