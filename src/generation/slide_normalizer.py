"""
Normalizador de slides post-IA.

Responsabilidad: garantizar que todas las diapositivas de desarrollo
cumplan los estándares de calidad mediante lógica de código pura,
sin depender únicamente del modelo.

Pipeline de normalización:
  1. Fusionar viñetas cortas dentro de cada slide.
  2. Enriquecer slides con pocas viñetas (llamada al modelo).
  3. Fusionar slides vecinas que siguen siendo pobres.
  4. Eliminar slides irrecuperables.
"""

from src.domain.models import Slide, SlideType
from src.ai.ollama_client import OllamaClient
from src.ai.prompt_builder import build_enrich_prompt
from config.settings import MIN_BULLETS_PER_SLIDE, MAX_BULLETS_PER_SLIDE, MIN_BULLET_WORDS


def normalize(
    slides: list[Slide],
    client: OllamaClient,
    doc_title: str,
    language: str,
) -> list[Slide]:
    """
    Aplica el pipeline completo de normalización a las diapositivas de desarrollo.

    Orden:
      1. Fusionar viñetas cortas dentro del mismo slide.
      2. Enriquecer slides con < MIN_BULLETS_PER_SLIDE viñetas.
      3. Fusionar slides vecinas que siguen siendo pobres.
      4. Filtrar slides vacías o irrecuperables.
    """
    slides = [_merge_short_bullets(s) for s in slides]
    slides = _enrich_thin_slides(slides, client, doc_title, language)
    slides = _merge_thin_neighbors(slides)
    slides = [s for s in slides if s.bullet_count() >= 2]
    return slides


# ---------------------------------------------------------------------------
# Paso 1 — Fusionar viñetas cortas dentro del mismo slide
# ---------------------------------------------------------------------------

def _merge_short_bullets(slide: Slide) -> Slide:
    """
    Fusiona viñetas consecutivas que son demasiado cortas (< MIN_BULLET_WORDS palabras)
    con la siguiente, para construir frases más completas.
    """
    if not slide.bullets:
        return slide

    merged: list[str] = []
    buffer = ""

    for bullet in slide.bullets:
        if _is_short(bullet) and buffer == "":
            buffer = bullet
        elif buffer:
            combined = f"{buffer}. {bullet}".replace(".. ", ". ")
            if _word_count(combined) <= 25:
                merged.append(combined)
            else:
                merged.append(buffer)
                merged.append(bullet)
            buffer = ""
        else:
            merged.append(bullet)

    if buffer:
        merged.append(buffer)

    # Respetar el máximo
    return Slide(
        slide_type=slide.slide_type,
        title=slide.title,
        bullets=merged[:MAX_BULLETS_PER_SLIDE],
    )


# ---------------------------------------------------------------------------
# Paso 2 — Enriquecer slides con pocas viñetas (llamada al modelo)
# ---------------------------------------------------------------------------

def _enrich_thin_slides(
    slides: list[Slide],
    client: OllamaClient,
    doc_title: str,
    language: str,
) -> list[Slide]:
    """
    Para cada slide con menos de MIN_BULLETS_PER_SLIDE viñetas,
    llama al modelo para añadir viñetas adicionales.
    """
    result: list[Slide] = []
    for slide in slides:
        if slide.bullet_count() < MIN_BULLETS_PER_SLIDE:
            enriched = _enrich(slide, client, doc_title, language)
            result.append(enriched)
        else:
            result.append(slide)
    return result


def _enrich(slide: Slide, client: OllamaClient, doc_title: str, language: str) -> Slide:
    """Intenta añadir viñetas a un slide pobre. Si falla, devuelve el slide original."""
    needed = MIN_BULLETS_PER_SLIDE - slide.bullet_count()
    prompt = build_enrich_prompt(slide.title, slide.bullets, needed, doc_title, language)
    try:
        data = client.generate_json(prompt)
        new_bullets = [
            b for b in data.get("bullets", [])
            if isinstance(b, str) and b.strip()
        ]
        combined = slide.bullets + new_bullets
        return Slide(
            slide_type=slide.slide_type,
            title=slide.title,
            bullets=combined[:MAX_BULLETS_PER_SLIDE],
        )
    except Exception:
        return slide


# ---------------------------------------------------------------------------
# Paso 3 — Fusionar slides vecinas que siguen siendo pobres
# ---------------------------------------------------------------------------

def _merge_thin_neighbors(slides: list[Slide]) -> list[Slide]:
    """
    Recorre la lista y fusiona pares consecutivos de slides pobres
    (ambas con < MIN_BULLETS_PER_SLIDE viñetas) si el resultado cabe en MAX_BULLETS_PER_SLIDE.
    """
    if len(slides) <= 1:
        return slides

    result: list[Slide] = []
    i = 0
    while i < len(slides):
        current = slides[i]
        if (
            i + 1 < len(slides)
            and current.bullet_count() < MIN_BULLETS_PER_SLIDE
            and slides[i + 1].bullet_count() < MIN_BULLETS_PER_SLIDE
            and current.bullet_count() + slides[i + 1].bullet_count() <= MAX_BULLETS_PER_SLIDE
        ):
            merged = Slide(
                slide_type=SlideType.CONTENT,
                title=current.title,
                bullets=current.bullets + slides[i + 1].bullets,
            )
            result.append(merged)
            i += 2
        else:
            result.append(current)
            i += 1

    return result


# ---------------------------------------------------------------------------
# Paso 4 — Dividir slides con demasiadas viñetas
# ---------------------------------------------------------------------------

def split_large_slides(slides: list[Slide]) -> list[Slide]:
    """
    Divide cualquier slide que supere MAX_BULLETS_PER_SLIDE viñetas en dos.

    La primera mitad conserva el título original; la segunda recibe el sufijo
    "(continuación)" para que el índice refleje ambas partes.
    """
    result: list[Slide] = []
    for slide in slides:
        if slide.bullet_count() <= MAX_BULLETS_PER_SLIDE:
            result.append(slide)
        else:
            mid = slide.bullet_count() // 2
            first = Slide(
                slide_type=slide.slide_type,
                title=slide.title,
                bullets=slide.bullets[:mid],
            )
            second = Slide(
                slide_type=slide.slide_type,
                title=f"{slide.title} (continuación)",
                bullets=slide.bullets[mid:MAX_BULLETS_PER_SLIDE * 2],
            )
            result.append(first)
            result.append(second)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_short(bullet: str) -> bool:
    return _word_count(bullet) < MIN_BULLET_WORDS


def _word_count(text: str) -> int:
    return len(text.split())
