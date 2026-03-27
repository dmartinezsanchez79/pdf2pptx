"""
Analizador global del documento — pipeline Map-Reduce.

Cubre el 100% del documento independientemente de su longitud:

  MAP    — divide el texto en chunks y extrae 1-3 temas por chunk.
  REDUCE — fusiona todos los temas en 4-8 secciones finales coherentes.

Después de obtener la estructura final, por cada sección se localiza
el fragmento del documento más relevante (sin llamada al modelo).
"""

from src.domain.models import DocumentStructure, ExtractedDocument, Section
from src.ai.ollama_client import OllamaClient
from src.ai.prompt_builder import build_chunk_topics_prompt, build_merge_sections_prompt
from src.extraction.text_cleaner import split_into_chunks
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, MAX_SECTIONS


def analyze(document: ExtractedDocument, client: OllamaClient) -> DocumentStructure:
    """
    Analiza el documento completo y devuelve su DocumentStructure.

    Pasos:
      1. MAP  — extrae temas de cada chunk del documento completo.
      2. REDUCE — fusiona todos los temas en secciones finales coherentes.
    """
    full_text = document.full_text()
    chunks = split_into_chunks(full_text)

    # Fase MAP
    raw_topics, language = _map_topics(chunks, document.title, client)

    if not raw_topics:
        return _fallback_structure(language)

    # Fase REDUCE
    structure = _reduce_sections(raw_topics, language, document.title, client)
    return structure


# ---------------------------------------------------------------------------
# Fase MAP — extraer temas chunk a chunk
# ---------------------------------------------------------------------------

def _map_topics(
    chunks: list[str],
    doc_title: str,
    client: OllamaClient,
) -> tuple[list[dict], str]:
    """
    Procesa cada chunk y acumula los temas encontrados.
    Devuelve (lista de dicts {title, key_points}, idioma detectado).
    """
    all_topics: list[dict] = []
    detected_language = "español"

    for chunk in chunks:
        topics, lang = _topics_from_chunk(chunk, doc_title, client)
        all_topics.extend(topics)
        # El idioma lo fija el primer chunk que lo detecte
        if lang and lang != "español" or detected_language == "español":
            detected_language = lang

    return all_topics, detected_language


def _topics_from_chunk(
    chunk: str,
    doc_title: str,
    client: OllamaClient,
) -> tuple[list[dict], str]:
    """Llama al modelo con un chunk y parsea los temas devueltos."""
    prompt = build_chunk_topics_prompt(chunk, doc_title)
    try:
        data = client.generate_json(prompt)
    except Exception:
        return [], "español"

    language = str(data.get("language", "español")).strip() or "español"
    raw_topics = data.get("topics", [])

    topics: list[dict] = []
    for item in raw_topics:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        key_points = [
            str(p).strip()
            for p in item.get("key_points", [])
            if str(p).strip()
        ]
        if title:
            topics.append({"title": title, "key_points": key_points})

    return topics, language


# ---------------------------------------------------------------------------
# Fase REDUCE — consolidar todos los temas en secciones finales
# ---------------------------------------------------------------------------

def _reduce_sections(
    raw_topics: list[dict],
    language: str,
    doc_title: str,
    client: OllamaClient,
) -> DocumentStructure:
    """
    Manda todos los temas al modelo para que los fusione en secciones coherentes.
    El texto enviado es muy compacto (solo títulos + key_points, no el documento).
    """
    topics_text = _format_topics(raw_topics)
    prompt = build_merge_sections_prompt(topics_text, doc_title)

    try:
        data = client.generate_json(prompt)
    except Exception:
        return _fallback_from_topics(raw_topics, language)

    detected_lang = str(data.get("language", language)).strip() or language
    raw_sections = data.get("sections", [])

    sections: list[Section] = []
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        key_points = [
            str(p).strip()
            for p in item.get("key_points", [])
            if str(p).strip()
        ]
        if title:
            sections.append(Section(title=title, key_points=key_points))

    if not sections:
        return _fallback_from_topics(raw_topics, detected_lang)

    return DocumentStructure(language=detected_lang, sections=sections)


def _format_topics(topics: list[dict]) -> str:
    """Serializa la lista de temas en texto compacto para el prompt de reduce."""
    lines: list[str] = []
    for i, t in enumerate(topics, 1):
        kp = ", ".join(t.get("key_points", []))
        lines.append(f"{i}. {t['title']}" + (f" [{kp}]" if kp else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------

def _fallback_structure(language: str = "español") -> DocumentStructure:
    return DocumentStructure(
        language=language,
        sections=[Section(title="Contenido principal", key_points=[])],
    )


def _fallback_from_topics(topics: list[dict], language: str) -> DocumentStructure:
    """Si el reduce falla, usa los temas en bruto sin fusionar (hasta MAX_SECTIONS)."""
    sections = [
        Section(title=t["title"], key_points=t.get("key_points", []))
        for t in topics[:MAX_SECTIONS]
    ]
    return DocumentStructure(language=language, sections=sections or [Section(title="Contenido principal", key_points=[])])


# ---------------------------------------------------------------------------
# Búsqueda de contexto relevante por sección
# ---------------------------------------------------------------------------

def find_relevant_context(section: Section, full_text: str) -> str:
    """
    Localiza el fragmento del documento más relevante para una sección.

    Divide el texto en ventanas deslizantes y puntúa cada una por cuántas
    palabras clave de la sección contiene. Devuelve la de mayor puntuación.
    """
    if not full_text.strip():
        return ""

    keywords = _extract_keywords(section)
    if not keywords:
        return full_text[:CHUNK_SIZE]

    windows = _sliding_windows(full_text)
    best = max(windows, key=lambda w: _score_window(w, keywords))
    return best


def _extract_keywords(section: Section) -> set[str]:
    tokens: set[str] = set()
    for text in [section.title] + section.key_points:
        for word in text.lower().split():
            clean = word.strip(".,;:()")
            if len(clean) >= 4:
                tokens.add(clean)
    return tokens


def _sliding_windows(text: str) -> list[str]:
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        windows.append(text[start:end])
        if end >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return windows or [text[:CHUNK_SIZE]]


def _score_window(window: str, keywords: set[str]) -> int:
    lower = window.lower()
    return sum(1 for kw in keywords if kw in lower)
