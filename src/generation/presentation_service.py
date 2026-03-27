"""
Servicio de generación de la presentación.

Pipeline de 4 fases:
  1. Análisis global  — una sola llamada al modelo identifica el idioma y las secciones
                        temáticas del documento con sus conceptos clave.
  2. Búsqueda de contexto — para cada sección se localiza el fragmento del
                        documento más relevante (sin llamada al modelo).
  3. Generación de slides — una llamada al modelo por sección, con sus
                        conceptos clave y el contexto localizado.
  4. Optimización post-IA — normalización determinista (fusionar viñetas cortas,
                        enriquecer slides pobres, dividir slides excesivas).

Resultado final: portada → índice → desarrollo → conclusión.
"""

from src.domain.models import ExtractedDocument, Presentation, Slide, SlideType
from src.ai.ollama_client import OllamaClient
from src.ai.prompt_builder import build_section_content_prompt, build_conclusion_prompt
from src.generation.document_analyzer import analyze, find_relevant_context
from src.generation.slide_normalizer import normalize, split_large_slides
from src.validation.slide_validator import (
    validate_slide, build_cover, build_index, build_conclusion,
)
from config.settings import MAX_CONTENT_SLIDES


class PresentationService:

    def __init__(self, client: OllamaClient) -> None:
        self._client = client

    def generate(self, document: ExtractedDocument) -> Presentation:
        """Genera una Presentation completa a partir de un ExtractedDocument."""

        # --- Fase 1: análisis global del documento ---
        structure = analyze(document, self._client)
        language = structure.language
        full_text = document.full_text()

        # --- Fases 2 y 3: contexto + generación por sección ---
        raw_slides: list[Slide] = []
        for section in structure.sections:
            context = find_relevant_context(section, full_text)
            slide = self._slide_from_section(section.title, section.key_points, context, document.title, language)
            if slide is not None:
                raw_slides.append(slide)

        # --- Fase 4: optimización post-IA ---
        slides = normalize(raw_slides, self._client, document.title, language)
        slides = split_large_slides(slides)
        slides = slides[:MAX_CONTENT_SLIDES]

        # --- Conclusión ---
        conclusion_slide = self._generate_conclusion(slides, document.title, language)

        # --- Ensamblado final ---
        cover = build_cover(document.filename or document.title)
        index = build_index(slides)  # construido DESPUÉS de la normalización
        all_slides = [cover, index, *slides, conclusion_slide]
        return Presentation(title=document.title, slides=all_slides)

    # ------------------------------------------------------------------
    # Fase 3 — Generación de slide por sección
    # ------------------------------------------------------------------

    def _slide_from_section(
        self,
        section_title: str,
        key_points: list[str],
        context: str,
        doc_title: str,
        language: str,
    ) -> Slide | None:
        """Llama al modelo para generar las viñetas de una sección concreta."""
        prompt = build_section_content_prompt(
            section_title, key_points, context, doc_title, language
        )
        try:
            data = self._client.generate_json(prompt)
        except Exception:
            return None

        bullets = [
            b for b in data.get("bullets", [])
            if isinstance(b, str) and b.strip()
        ]
        if not bullets:
            return None

        slide = Slide(
            slide_type=SlideType.CONTENT,
            title=section_title,
            bullets=bullets,
        )
        return validate_slide(slide)

    # ------------------------------------------------------------------
    # Conclusiones
    # ------------------------------------------------------------------

    def _generate_conclusion(
        self, content_slides: list[Slide], doc_title: str, language: str
    ) -> Slide:
        titles = [s.title for s in content_slides]
        prompt = build_conclusion_prompt(titles, doc_title, language)
        try:
            data = self._client.generate_json(prompt)
            bullets = [b for b in data.get("bullets", []) if isinstance(b, str) and b.strip()]
        except Exception:
            bullets = []

        if not bullets:
            bullets = ["Consulta el documento original para más detalles."]

        return build_conclusion(bullets)
