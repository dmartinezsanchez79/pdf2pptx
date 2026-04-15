"""
Métricas objetivas automatizadas para la presentación PPTX generada.

Recibe un objeto Presentation (dominio) y extrae todas las métricas
sin necesidad de abrir el .pptx — trabaja sobre el modelo intermedio.
"""

from src.domain.models import Presentation, SlideType


def compute_pptx_metrics(presentation: Presentation) -> dict:
    """
    Calcula todas las métricas objetivas del PPTX.
    Devuelve un dict plano listo para serializar a CSV/JSON.
    """
    content_slides = presentation.content_slides()
    index_slide = presentation.index()
    conclusion = presentation.conclusion()

    # Conteos básicos
    total_slides = presentation.slide_count()
    n_content = len(content_slides)

    # Viñetas por slide
    bullet_counts = [s.bullet_count() for s in content_slides]
    avg_bullets = _safe_avg(bullet_counts)
    bullets_in_range = sum(1 for c in bullet_counts if 4 <= c <= 5)
    bullets_in_range_pct = (bullets_in_range / n_content * 100) if n_content else 0

    # Longitud de viñetas
    all_bullets = [b for s in content_slides for b in s.bullets]
    bullet_lengths = [len(b) for b in all_bullets]
    avg_bullet_length = _safe_avg(bullet_lengths)

    # Coherencia índice ↔ slides
    index_matches = _check_index_matches(index_slide, content_slides)

    # Conclusión
    conclusion_bullets = conclusion.bullet_count() if conclusion else 0

    return {
        "pptx_total_slides": total_slides,
        "pptx_content_slides": n_content,
        "pptx_avg_bullets_per_slide": round(avg_bullets, 2),
        "pptx_bullets_in_range_pct": round(bullets_in_range_pct, 1),
        "pptx_total_bullets": len(all_bullets),
        "pptx_avg_bullet_length": round(avg_bullet_length, 1),
        "pptx_index_matches_slides": index_matches,
        "pptx_conclusion_bullets": conclusion_bullets,
    }


def _check_index_matches(index_slide, content_slides) -> bool:
    """Verifica que las viñetas del índice coincidan con los títulos de desarrollo."""
    if index_slide is None:
        return False
    index_titles = set(b.strip() for b in index_slide.bullets)
    content_titles = set(s.title.strip() for s in content_slides)
    return index_titles == content_titles


def _safe_avg(values: list) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
