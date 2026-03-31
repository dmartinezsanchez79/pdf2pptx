"""
Modelos de dominio del proyecto.

Estos dataclasses son el contrato interno entre todas las capas.
Ninguna capa intercambia dicts sueltos: todo pasa por estos tipos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# ---------------------------------------------------------------------------
# Documento extraído del PDF
# ---------------------------------------------------------------------------

@dataclass
class DocumentSection:
    """Fragmento lógico del documento (capítulo, sección, párrafo relevante)."""
    heading: str | None
    body: str

    def is_empty(self) -> bool:
        return not self.body.strip()


@dataclass
class ExtractedDocument:
    """Resultado completo de leer y limpiar un PDF."""
    title: str
    sections: list[DocumentSection]
    raw_text: str
    filename: str = ""              # nombre del archivo PDF (sin extensión)

    def full_text(self) -> str:
        """Texto completo reconstruido a partir de las secciones."""
        parts: list[str] = []
        for section in self.sections:
            if section.heading:
                parts.append(section.heading)
            parts.append(section.body)
        return "\n\n".join(parts)

    def is_empty(self) -> bool:
        return not self.raw_text.strip()


# ---------------------------------------------------------------------------
# Estructura intermedia del documento (fase de análisis)
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """Sección temática identificada por el modelo en la fase de análisis."""
    title: str
    key_points: list[str]   # conceptos clave que debe cubrir la diapositiva


@dataclass
class DocumentStructure:
    """Estructura global del documento detectada antes de generar slides."""
    language: str
    sections: list[Section]

    def section_count(self) -> int:
        return len(self.sections)


# ---------------------------------------------------------------------------
# Presentación PPTX
# ---------------------------------------------------------------------------

class SlideType(Enum):
    COVER = auto()
    INDEX = auto()
    CONTENT = auto()
    CONCLUSION = auto()


@dataclass
class Slide:
    """Representa una diapositiva individual."""
    slide_type: SlideType
    title: str
    bullets: list[str] = field(default_factory=list)

    def bullet_count(self) -> int:
        return len(self.bullets)


@dataclass
class Presentation:
    """Colección ordenada de diapositivas que forman la presentación."""
    title: str
    slides: list[Slide] = field(default_factory=list)

    def cover(self) -> Slide | None:
        return next((s for s in self.slides if s.slide_type == SlideType.COVER), None)

    def index(self) -> Slide | None:
        return next((s for s in self.slides if s.slide_type == SlideType.INDEX), None)

    def content_slides(self) -> list[Slide]:
        return [s for s in self.slides if s.slide_type == SlideType.CONTENT]

    def conclusion(self) -> Slide | None:
        return next((s for s in self.slides if s.slide_type == SlideType.CONCLUSION), None)

    def slide_count(self) -> int:
        return len(self.slides)


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

@dataclass
class Question:
    """Pregunta de opción múltiple con exactamente 4 opciones."""
    text: str
    options: list[str]          # siempre 4 elementos
    correct_index: int          # 0-3
    explanation: str = ""
    topic: str = ""             # tema o concepto que evalúa (opcional)
    difficulty: str = ""        # "fácil" | "media" | "difícil" (opcional)

    def correct_option(self) -> str:
        return self.options[self.correct_index]

    def is_valid(self) -> bool:
        return (
            len(self.options) == 4
            and 0 <= self.correct_index <= 3
            and bool(self.text.strip())
            and all(bool(o.strip()) for o in self.options)
        )


@dataclass
class Quiz:
    """Colección de preguntas que forman el cuestionario."""
    title: str
    questions: list[Question] = field(default_factory=list)

    def question_count(self) -> int:
        return len(self.questions)


# ---------------------------------------------------------------------------
# Resultado del quiz (sesión de respuestas)
# ---------------------------------------------------------------------------

@dataclass
class QuestionResult:
    """Resultado de una pregunta respondida por el usuario."""
    question: Question
    chosen_index: int

    def is_correct(self) -> bool:
        return self.chosen_index == self.question.correct_index


@dataclass
class QuizResult:
    """Resultado completo de una sesión de quiz."""
    quiz: Quiz
    results: list[QuestionResult] = field(default_factory=list)

    def correct_count(self) -> int:
        return sum(1 for r in self.results if r.is_correct())

    def wrong_count(self) -> int:
        return len(self.results) - self.correct_count()

    def score_percent(self) -> float:
        if not self.results:
            return 0.0
        return round(self.correct_count() / len(self.results) * 100, 1)
