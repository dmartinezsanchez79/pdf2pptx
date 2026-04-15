"""
Generador de prompts para evaluación asistida por IA externa (ChatGPT/Gemini).

Genera prompts estandarizados listos para copiar-pegar en una IA comercial.
Los prompts incluyen las rúbricas, el contenido a evaluar y el formato de respuesta esperado.

Uso:
  1. run_benchmark.py genera los artefactos (PPTX data + Quiz data).
  2. Este módulo genera archivos .txt con los prompts de evaluación.
  3. El evaluador (tú) copia cada prompt en ChatGPT/Gemini y recoge la puntuación.
  4. Las puntuaciones se registran en el CSV de evaluación manual.
"""

from src.domain.models import Presentation, Quiz
from benchmark.evaluation.rubrics import (
    PPTX_RELEVANCE_RUBRIC,
    PPTX_COHERENCE_RUBRIC,
    QUIZ_PEDAGOGICAL_RUBRIC,
    QUIZ_DISTRACTOR_RUBRIC,
    format_rubric_for_prompt,
)


def generate_pptx_eval_prompt(
    presentation: Presentation,
    pdf_excerpt: str,
    model_name: str,
    pdf_id: str,
) -> str:
    """
    Genera el prompt para que una IA externa evalúe la calidad del PPTX.

    El evaluador recibe el PDF original como adjunto, por lo que no se
    incluye extracto de texto. Solo se envían las viñetas generadas y
    las rúbricas de evaluación.
    """
    # Construir el contenido del PPTX
    slides_text = ""
    for i, slide in enumerate(presentation.content_slides(), 1):
        bullets = "\n".join(f"  - {b}" for b in slide.bullets)
        slides_text += f"\nDiapositiva {i}: {slide.title}\n{bullets}\n"

    relevance_rubric = format_rubric_for_prompt(PPTX_RELEVANCE_RUBRIC)
    coherence_rubric = format_rubric_for_prompt(PPTX_COHERENCE_RUBRIC)

    return f"""Eres un evaluador académico experto. Debes evaluar la calidad de una presentación generada automáticamente por un modelo de IA local ({model_name}) a partir del documento PDF adjunto.

TAREA: usa el PDF adjunto como referencia y evalúa la presentación según las 2 rúbricas proporcionadas.

PRESENTACIÓN GENERADA ({pdf_id}, modelo {model_name}):
{slides_text}

RÚBRICAS DE EVALUACIÓN:

{relevance_rubric}

{coherence_rubric}

FORMATO DE RESPUESTA (responde SOLO con este JSON):
{{
  "pptx_content_relevance": <1-5>,
  "pptx_coherence": <1-5>,
  "justification_relevance": "<1-2 frases justificando la puntuación>",
  "justification_coherence": "<1-2 frases justificando la puntuación>"
}}"""


def generate_quiz_eval_prompt(
    quiz: Quiz,
    pdf_excerpt: str,
    model_name: str,
    pdf_id: str,
) -> str:
    """
    Genera el prompt para que una IA externa evalúe la calidad del quiz.

    El evaluador recibe el PDF original como adjunto para verificar
    la corrección de las respuestas.
    """
    # Construir el contenido del quiz
    quiz_text = ""
    for i, q in enumerate(quiz.questions, 1):
        options = "\n".join(
            f"    {'→' if j == q.correct_index else ' '} {chr(65+j)}) {o}"
            for j, o in enumerate(q.options)
        )
        quiz_text += f"\n{i}. {q.text}\n{options}\n   Explicación: {q.explanation}\n"

    pedagogical_rubric = format_rubric_for_prompt(QUIZ_PEDAGOGICAL_RUBRIC)
    distractor_rubric = format_rubric_for_prompt(QUIZ_DISTRACTOR_RUBRIC)

    return f"""Eres un evaluador académico experto en diseño de evaluaciones. Debes evaluar la calidad de un quiz generado automáticamente por un modelo de IA local ({model_name}) a partir del documento PDF adjunto.

TAREA: usa el PDF adjunto como referencia. Evalúa el quiz según las 2 rúbricas proporcionadas.
Además, revisa cada pregunta y marca si la respuesta indicada como correcta (→) realmente lo es.

QUIZ GENERADO ({pdf_id}, modelo {model_name}):
{quiz_text}

RÚBRICAS DE EVALUACIÓN:

{pedagogical_rubric}

{distractor_rubric}

FORMATO DE RESPUESTA (responde SOLO con este JSON):
{{
  "quiz_pedagogical_quality": <1-5>,
  "quiz_distractor_plausibility": <1-5>,
  "justification_pedagogical": "<1-2 frases>",
  "justification_distractor": "<1-2 frases>",
  "answer_correctness": [
    {{"question": 1, "marked_correct": true/false, "note": ""}},
    ...
  ]
}}"""
