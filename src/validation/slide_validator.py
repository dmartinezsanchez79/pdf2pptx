"""
Validación determinista de slides post-IA.

La IA puede devolver títulos demasiado largos, demasiados bullets,
bullets vacíos, etc. Esta capa corrige todo eso sin volver a llamar al modelo.

Principio: preferir corrección local sobre reintento al modelo.
"""

from src.domain.models import Slide, SlideType
from config.settings import MAX_BULLETS_PER_SLIDE, MIN_BULLETS_PER_SLIDE, MIN_BULLET_WORDS, MAX_TITLE_LENGTH, MAX_BULLET_LENGTH


def validate_slide(slide: Slide) -> Slide:
    """Corrige un slide individual para que cumpla todas las restricciones."""
    title = _fix_title(slide.title)
    bullets = _fix_bullets(slide.bullets)
    return Slide(slide_type=slide.slide_type, title=title, bullets=bullets)


# ---------------------------------------------------------------------------
# Construcción de slides fijos (portada, índice, conclusión)
# Estos no los genera la IA: los construimos nosotros con datos del documento.
# ---------------------------------------------------------------------------

def build_cover(pdf_filename: str = "") -> Slide:
    """
    La portada siempre usa título fijo y subtítulo con el nombre del PDF.
    El subtítulo se guarda en bullets[0] para que el renderer lo coloque
    en el placeholder SUBTÍTULO de la plantilla.
    """
    subtitle = f"Presentación generada a partir de {pdf_filename}" if pdf_filename else "Presentación generada automáticamente"
    return Slide(
        slide_type=SlideType.COVER,
        title="Resumen del documento",
        bullets=[subtitle],
    )


def build_index(content_slides: list[Slide]) -> Slide:
    """El índice lista los títulos de las diapositivas de desarrollo."""
    bullets = [_fix_bullet(s.title) for s in content_slides]
    return Slide(
        slide_type=SlideType.INDEX,
        title="Índice",
        bullets=bullets[:MAX_BULLETS_PER_SLIDE],
    )


def build_conclusion(bullets: list[str]) -> Slide:
    return Slide(
        slide_type=SlideType.CONCLUSION,
        title="Conclusiones",
        bullets=_fix_bullets(bullets),
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _fix_title(title: str) -> str:
    """Trunca el título si es demasiado largo y elimina saltos de línea."""
    title = title.replace("\n", " ").strip()
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH - 1].rstrip() + "…"
    return title or "Sin título"


def _fix_bullet(bullet: str) -> str:
    """
    Limpia un bullet y garantiza que sea una frase completa.

    Si supera MAX_BULLET_LENGTH:
      1. Busca el último signo de puntuación final (. ! ?) dentro del límite.
         Si lo encuentra y la frase resultante tiene al menos 6 palabras → la usa.
      2. Si no hay signo de puntuación → devuelve "" para que sea filtrado.
         Preferimos eliminar la viñeta antes que mostrar una frase cortada.
    """
    bullet = bullet.replace("\n", " ").strip()
    if len(bullet) <= MAX_BULLET_LENGTH:
        return bullet

    window = bullet[:MAX_BULLET_LENGTH]
    for punct in (".", "!", "?"):
        pos = window.rfind(punct)
        if pos > 0:
            candidate = bullet[:pos + 1].strip()
            if len(candidate.split()) >= 6:
                return candidate

    # Sin frase completa dentro del límite: descartar
    return ""


def _fix_bullets(bullets: list[str]) -> list[str]:
    """Filtra bullets inválidos, garantiza frases completas y respeta el máximo por slide."""
    result = []
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        if _is_placeholder(b):
            continue
        fixed = _fix_bullet(b)
        if fixed:
            result.append(fixed)
    return result[:MAX_BULLETS_PER_SLIDE]


def _is_placeholder(bullet: str) -> bool:
    """Detecta bullets que son placeholders del modelo, no contenido real."""
    normalized = bullet.strip().lower().replace(" ", "")
    # Variantes de "..." que el modelo copia del ejemplo del prompt
    if set(normalized) <= {".", "…", " "}:
        return True
    # Muy corto para ser una frase real (menos de MIN_BULLET_WORDS palabras)
    if len(bullet.split()) < MIN_BULLET_WORDS:
        return True
    return False
