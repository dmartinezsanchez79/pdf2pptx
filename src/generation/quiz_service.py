"""
Servicio de generación del quiz.

Mismo patrón Map-Reduce que presentation_service:
  1. Divide el texto en chunks.
  2. Por cada chunk, llama al modelo para extraer preguntas.
  3. Valida y deduplica.
  4. Devuelve un Quiz con las preguntas resultantes.
"""

from src.domain.models import ExtractedDocument, Question, Quiz
from src.ai.ollama_client import OllamaClient
from src.ai.prompt_builder import build_quiz_prompt
from src.extraction.text_cleaner import split_into_chunks
from src.extraction.language_detector import detect_language
from src.validation.quiz_validator import validate_question, validate_quiz
from config.settings import QUIZ_MAX_QUESTIONS


class QuizService:

    def __init__(self, client: OllamaClient) -> None:
        self._client = client

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
        chunks = split_into_chunks(document.full_text())
        all_questions: list[Question] = []

        for chunk in chunks:
            if len(all_questions) >= QUIZ_MAX_QUESTIONS:
                break
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

        raw_questions = data.get("questions", [])
        questions: list[Question] = []

        for item in raw_questions:
            q = _parse_question(item)
            if q is None:
                continue
            validated = validate_question(q)
            if validated is not None:
                questions.append(validated)

        return questions


# ---------------------------------------------------------------------------
# Helper de parseo
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
        options=options,
        correct_index=correct_index,
        explanation=explanation,
    )
