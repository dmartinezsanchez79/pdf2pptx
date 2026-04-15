"""
Servicio de generación del quiz.

Patrón Map-Reduce:
  1. Limpieza agresiva del texto (elimina metadatos, URLs, ruido editorial).
  2. División en chunks.
  3. Filtrado: solo se procesan chunks con suficiente sustancia pedagógica.
  4. Por cada chunk válido, llamada al modelo para extraer preguntas.
  5. Validación, deduplicación y límite de preguntas.
"""

import re

from src.domain.models import ExtractedDocument, Question, Quiz
from src.ai.ollama_client import OllamaClient
from src.ai.prompt_builder import build_quiz_prompt
from src.extraction.text_cleaner import split_into_chunks, clean_for_quiz
from src.extraction.language_detector import detect_language
from src.validation.quiz_validator import validate_question, validate_quiz
from config.settings import QUIZ_MAX_QUESTIONS

# Un chunk debe tener al menos estas palabras para ser procesado
_MIN_CHUNK_WORDS = 40
# Longitud media de línea mínima (chunks con muchas líneas cortas = índice/portada)
_MIN_AVG_LINE_LENGTH = 30


class QuizService:

    def __init__(self, client: OllamaClient) -> None:
        self._client = client
        # Contadores para benchmark (no afectan lógica)
        self.questions_before_validation: int = 0

    def generate(self, document: ExtractedDocument) -> Quiz:
        """Genera un Quiz completo a partir de un ExtractedDocument."""
        language = detect_language(document.raw_text)
        questions = self._generate_questions(document, language)
        quiz = Quiz(title=document.title, questions=questions)
        return validate_quiz(quiz)

    # ------------------------------------------------------------------
    # Generación de preguntas (Map-Reduce)
    # ------------------------------------------------------------------

    def _generate_questions(self, document: ExtractedDocument, language: str) -> list[Question]:
        clean_text = clean_for_quiz(document.full_text())
        chunks = split_into_chunks(clean_text)
        all_questions: list[Question] = []

        for chunk in chunks:
            if len(all_questions) >= QUIZ_MAX_QUESTIONS:
                break
            if not _is_quiz_worthy(chunk):
                continue
            questions = self._questions_from_chunk(chunk, document.title, language)
            all_questions.extend(questions)

        return all_questions

    def _questions_from_chunk(self, chunk: str, doc_title: str, language: str) -> list[Question]:
        """Llama al modelo con un chunk y parsea las preguntas devueltas."""
        prompt = build_quiz_prompt(chunk, doc_title, language)
        try:
            data = self._client.generate_json(prompt)
        except Exception:
            return []

        questions: list[Question] = []
        for item in data.get("questions", []):
            q = _parse_question(item)
            if q is None:
                continue
            self.questions_before_validation += 1
            validated = validate_question(q)
            if validated is not None:
                questions.append(validated)

        return questions


# ---------------------------------------------------------------------------
# Filtro de calidad del chunk
# ---------------------------------------------------------------------------

def _is_quiz_worthy(chunk: str) -> bool:
    """
    Descarta chunks que no tienen sustancia pedagógica:
    - Demasiado cortos (portada, índice de una sola entrada).
    - Líneas muy cortas en promedio (tabla de contenidos, listas de datos).
    - Alta densidad de entradas de índice (líneas que terminan en número de página).
    - Alta densidad de nombres propios sin contenido conceptual (contraportada/bio).
    """
    words = chunk.split()
    if len(words) < _MIN_CHUNK_WORDS:
        return False

    lines = [l.strip() for l in chunk.splitlines() if l.strip()]
    if not lines:
        return False

    avg_line_len = sum(len(l) for l in lines) / len(lines)
    if avg_line_len < _MIN_AVG_LINE_LENGTH:
        return False

    # Rechazar si >25% de líneas parecen entradas de índice (terminan en número de página)
    toc_lines = sum(1 for l in lines if re.search(r'[\.\s]{3,}\d{1,4}\s*$', l))
    if toc_lines / len(lines) > 0.25:
        return False

    # Rechazar si el chunk contiene principalmente frases de contraportada/bio
    # (menciones a libros ajenos, premios, países visitados como ponente)
    back_cover_hits = sum(1 for l in lines if re.search(
        r'\bautor(a)? de\b|\bcoautor\b|\bha impartido\b|\bseminarios?\b|\bconferenci',
        l, re.IGNORECASE
    ))
    if back_cover_hits >= 2:
        return False

    return True


# ---------------------------------------------------------------------------
# Parseo del output del modelo
# ---------------------------------------------------------------------------

def _parse_question(item: dict) -> Question | None:
    """Construye una Question desde un dict raw del modelo. Devuelve None si falta algo."""
    if not isinstance(item, dict):
        return None

    text = str(item.get("text", "")).strip()
    options = item.get("options", [])
    correct_index = item.get("correct_index")
    explanation = str(item.get("explanation", "")).strip()

    if not text or not isinstance(options, list) or correct_index is None:
        return None

    try:
        correct_index = int(correct_index)
    except (ValueError, TypeError):
        return None

    return Question(
        text=text,
        options=[str(o).strip() for o in options],
        correct_index=correct_index,
        explanation=explanation,
        topic=str(item.get("topic", "")).strip(),
        difficulty=str(item.get("difficulty", "")).strip(),
    )
