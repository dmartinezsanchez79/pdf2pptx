"""
Métricas objetivas automatizadas para el quiz generado.

Trabaja en dos niveles:
1. Preguntas antes de validación (producción bruta del modelo)
2. Preguntas después de validación (quiz final)
"""

from src.domain.models import Quiz, Question


def compute_quiz_metrics(
    quiz_final: Quiz,
    questions_before_validation: int = 0,
) -> dict:
    """
    Calcula todas las métricas objetivas del quiz.
    Devuelve un dict plano listo para serializar a CSV/JSON.

    Args:
        quiz_final: Quiz ya validado (post validate_quiz).
        questions_before_validation: nº de preguntas antes de la validación.
            Si no se proporciona, se usa solo el quiz final.
    """
    questions = quiz_final.questions
    n_valid = len(questions)
    n_generated = questions_before_validation if questions_before_validation > 0 else n_valid

    # Tasa de supervivencia
    pass_rate = (n_valid / n_generated * 100) if n_generated > 0 else 0

    # Diversidad temática
    topics = [q.topic.strip().lower() for q in questions if q.topic.strip()]
    unique_topics = len(set(topics))
    topic_diversity = (unique_topics / n_valid) if n_valid > 0 else 0

    # Distribución de dificultad
    difficulties = [q.difficulty.strip().lower() for q in questions if q.difficulty.strip()]
    difficulty_dist = {}
    for d in difficulties:
        difficulty_dist[d] = difficulty_dist.get(d, 0) + 1

    # Balance de opciones (ratio max/min longitud)
    option_ratios = []
    for q in questions:
        lengths = [len(o) for o in q.options]
        if min(lengths) > 0:
            option_ratios.append(max(lengths) / min(lengths))
    avg_option_ratio = _safe_avg(option_ratios)

    # Explicaciones
    has_explanation = sum(1 for q in questions if len(q.explanation.strip()) >= 20)
    explanation_rate = (has_explanation / n_valid * 100) if n_valid > 0 else 0

    # Longitud media de preguntas
    avg_question_length = _safe_avg([len(q.text) for q in questions])

    # Longitud media de opciones
    all_option_lengths = [len(o) for q in questions for o in q.options]
    avg_option_length = _safe_avg(all_option_lengths)

    return {
        "quiz_questions_generated": n_generated,
        "quiz_questions_valid": n_valid,
        "quiz_pass_rate": round(pass_rate, 1),
        "quiz_unique_topics": unique_topics,
        "quiz_topic_diversity": round(topic_diversity, 2),
        "quiz_difficulty_distribution": difficulty_dist,
        "quiz_avg_option_length_ratio": round(avg_option_ratio, 2),
        "quiz_has_explanation_rate": round(explanation_rate, 1),
        "quiz_avg_question_length": round(avg_question_length, 1),
        "quiz_avg_option_length": round(avg_option_length, 1),
    }


def _safe_avg(values: list) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
