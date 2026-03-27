"""
Validación determinista de preguntas de quiz post-IA.

Corrige lo que se puede corregir localmente.
Descarta las preguntas irrecuperables en lugar de dejar datos corruptos.
"""

from src.domain.models import Question, Quiz
from config.settings import QUIZ_OPTIONS_PER_QUESTION, QUIZ_MIN_QUESTIONS, QUIZ_MAX_QUESTIONS


def validate_question(q: Question) -> Question | None:
    """
    Valida y corrige una pregunta.
    Devuelve None si la pregunta no es recuperable.
    """
    text = q.text.strip()
    if not text:
        return None

    options = _fix_options(q.options)
    if options is None:
        return None

    correct_index = q.correct_index
    if not (0 <= correct_index < QUIZ_OPTIONS_PER_QUESTION):
        return None

    explanation = q.explanation.strip() if q.explanation else ""

    return Question(
        text=text,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
    )


def validate_quiz(quiz: Quiz) -> Quiz:
    """
    Valida todas las preguntas del quiz.
    Descarta las inválidas y respeta el máximo de preguntas.
    """
    valid: list[Question] = []
    for q in quiz.questions:
        fixed = validate_question(q)
        if fixed is not None:
            valid.append(fixed)

    deduplicated = _deduplicate(valid)
    return Quiz(title=quiz.title, questions=deduplicated[:QUIZ_MAX_QUESTIONS])


def has_enough_questions(quiz: Quiz) -> bool:
    return quiz.question_count() >= QUIZ_MIN_QUESTIONS


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _fix_options(options: list) -> list[str] | None:
    """
    Limpia la lista de opciones.
    Devuelve None si no se pueden obtener exactamente 4 opciones válidas.
    """
    if not isinstance(options, list):
        return None

    cleaned = [str(o).strip() for o in options if str(o).strip()]

    if len(cleaned) < QUIZ_OPTIONS_PER_QUESTION:
        return None

    return cleaned[:QUIZ_OPTIONS_PER_QUESTION]


def _deduplicate(questions: list[Question]) -> list[Question]:
    """Elimina preguntas con texto idéntico (normalizado)."""
    seen: set[str] = set()
    unique: list[Question] = []
    for q in questions:
        key = " ".join(q.text.lower().split())
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique
