"""
Validación determinista de preguntas de quiz post-IA.

Descarta preguntas irrecuperables y garantiza que solo pasan preguntas
con valor pedagógico real: bien formuladas, con distractores plausibles
y sin contenido trivial o corrupto.
"""

import re

from src.domain.models import Question, Quiz
from config.settings import QUIZ_OPTIONS_PER_QUESTION, QUIZ_MIN_QUESTIONS, QUIZ_MAX_QUESTIONS

# ---------------------------------------------------------------------------
# Umbrales de calidad
# ---------------------------------------------------------------------------

_MIN_QUESTION_CHARS = 25    # texto mínimo de la pregunta
_MIN_OPTION_CHARS = 8       # longitud mínima de cada opción
_MIN_EXPLANATION_CHARS = 20 # explicación mínima
_MAX_OPTION_LENGTH_RATIO = 3.0  # la opción más larga no puede ser 3x la más corta

# Patrones que delatan preguntas triviales o sobre metadatos
_TRIVIAL_PATTERNS = [
    r'\bautor(es)?\b',
    r'\btítulo del (libro|documento|texto|capítulo)\b',
    r'\baño de publicación\b|\bfecha de publicación\b|\bfecha de edición\b',
    r'\bISBN\b',
    r'\beditorial\b.{0,30}\bpublicó\b',
    r'\bnúmero de (página|capítulo|edición)\b',
    r'\bprólogo\b|\bagradecimiento\b',
    r'\bcuántas páginas\b|\bcuántos capítulos\b',
]

# Frases prohibidas en cualquier opción
_BANNED_OPTION_PHRASES = {
    "todas las anteriores",
    "ninguna de las anteriores",
    "no se menciona",
    "all of the above",
    "none of the above",
    "todas las opciones",
    "ninguna de las opciones",
    "todas son correctas",
    "ninguna es correcta",
}

# Patrones de contenido corrupto en preguntas u opciones
_CORRUPT_PATTERNS = [
    r'https?://',
    r'www\.\S+',
    r'\bISBN[\s\-:]?\d',
    r'[^\x00-\xFF]{3,}',    # muchos caracteres no-ASCII seguidos (encoding roto)
    r'\?\?\?|\.\.\.',        # placeholders del modelo
]


def validate_question(q: Question) -> Question | None:
    """
    Valida y corrige una pregunta.
    Devuelve None si no es recuperable.
    """
    text = q.text.strip()
    if len(text) < _MIN_QUESTION_CHARS:
        return None
    if _is_trivial(text):
        return None
    if _has_corrupt_content(text):
        return None

    options = _fix_options(q.options)
    if options is None:
        return None

    correct_index = q.correct_index
    if not (0 <= correct_index < QUIZ_OPTIONS_PER_QUESTION):
        return None

    explanation = q.explanation.strip() if q.explanation else ""
    if len(explanation) < _MIN_EXPLANATION_CHARS:
        return None
    if _has_corrupt_content(explanation):
        return None

    return Question(
        text=text,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
        topic=q.topic.strip() if q.topic else "",
        difficulty=q.difficulty.strip() if q.difficulty else "",
    )


def validate_quiz(quiz: Quiz) -> Quiz:
    """Valida todas las preguntas, deduplica y respeta el máximo."""
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
# Validaciones específicas
# ---------------------------------------------------------------------------

def _is_trivial(question_text: str) -> bool:
    """Detecta preguntas sobre metadatos o información editorial sin valor pedagógico."""
    text_lower = question_text.lower()
    return any(re.search(p, text_lower) for p in _TRIVIAL_PATTERNS)


def _has_corrupt_content(text: str) -> bool:
    """Detecta URLs, ISBN, placeholders o encoding roto en el texto."""
    return any(re.search(p, text, re.IGNORECASE) for p in _CORRUPT_PATTERNS)


def _fix_options(options: list) -> list[str] | None:
    """
    Limpia y valida las opciones.
    Descarta si:
    - No hay exactamente 4 opciones válidas.
    - Alguna es demasiado corta.
    - Alguna es una frase prohibida (trampa/comodín).
    - Las longitudes están muy desbalanceadas (delata que la correcta es obvia).
    - Alguna contiene contenido corrupto.
    """
    if not isinstance(options, list):
        return None

    cleaned = [str(o).strip() for o in options if str(o).strip()]
    if len(cleaned) < QUIZ_OPTIONS_PER_QUESTION:
        return None

    cleaned = cleaned[:QUIZ_OPTIONS_PER_QUESTION]

    for opt in cleaned:
        if len(opt) < _MIN_OPTION_CHARS:
            return None
        if _is_banned_option(opt):
            return None
        if _has_corrupt_content(opt):
            return None

    if _options_too_unbalanced(cleaned):
        return None

    return cleaned


def _is_banned_option(option: str) -> bool:
    normalized = option.lower().strip()
    return any(phrase in normalized for phrase in _BANNED_OPTION_PHRASES)


def _options_too_unbalanced(options: list[str]) -> bool:
    """
    Devuelve True si una opción es mucho más larga que las demás.
    Esto suele delatar que la respuesta correcta es la más completa/larga,
    haciéndola obvia sin necesidad de entender el contenido.
    """
    lengths = [len(o) for o in options]
    if min(lengths) == 0:
        return True
    return max(lengths) / min(lengths) > _MAX_OPTION_LENGTH_RATIO


# ---------------------------------------------------------------------------
# Deduplicación por solapamiento semántico
# ---------------------------------------------------------------------------

def _deduplicate(questions: list[Question]) -> list[Question]:
    """
    Elimina preguntas duplicadas o muy similares.
    Compara por solapamiento de palabras significativas (>3 letras).
    Umbral: >60% de solapamiento = duplicado.
    """
    unique: list[Question] = []
    unique_words: list[set[str]] = []

    for q in questions:
        words = _significant_words(q.text)
        if not _is_near_duplicate(words, unique_words):
            unique.append(q)
            unique_words.append(words)

    return unique


def _significant_words(text: str) -> set[str]:
    return {w.lower() for w in text.split() if len(w) > 3}


def _is_near_duplicate(words: set[str], existing: list[set[str]], threshold: float = 0.6) -> bool:
    for other in existing:
        if not words or not other:
            continue
        overlap = len(words & other) / min(len(words), len(other))
        if overlap >= threshold:
            return True
    return False
