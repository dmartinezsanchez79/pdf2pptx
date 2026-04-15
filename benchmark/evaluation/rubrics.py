"""
Rúbricas de evaluación subjetiva.

Define las escalas y criterios para la evaluación manual y asistida por IA.
Cada rúbrica tiene 5 niveles (1-5) con descriptores concretos.
"""


PPTX_RELEVANCE_RUBRIC = {
    "name": "pptx_content_relevance",
    "description": "¿Las viñetas son relevantes al tema de la sección?",
    "scale": {
        1: "Ninguna viñeta está relacionada con el tema de la sección.",
        2: "Menos de la mitad de las viñetas son relevantes; hay contenido inventado o de otra sección.",
        3: "La mayoría de viñetas son relevantes pero hay alguna genérica o fuera de tema.",
        4: "Todas las viñetas son relevantes, aunque alguna podría ser más específica.",
        5: "Todas las viñetas son directamente relevantes y específicas del tema.",
    },
}

PPTX_COHERENCE_RUBRIC = {
    "name": "pptx_coherence",
    "description": "¿Las viñetas forman un discurso lógico y bien ordenado?",
    "scale": {
        1: "Las viñetas son incoherentes, se contradicen o no tienen orden lógico.",
        2: "Hay cierta conexión pero el orden es confuso y hay ideas sueltas.",
        3: "Las viñetas tienen coherencia general pero alguna rompe el flujo.",
        4: "Buen flujo lógico, las ideas se suceden naturalmente.",
        5: "Las viñetas forman un argumento claro y bien estructurado.",
    },
}

PPTX_COMPLETENESS_RUBRIC = {
    "name": "pptx_completeness",
    "description": "¿Se cubren los conceptos clave del PDF en la presentación?",
    "scale": {
        1: "La presentación omite los conceptos principales del documento.",
        2: "Se cubren algunos conceptos pero faltan temas importantes.",
        3: "Se cubren los conceptos principales pero faltan detalles relevantes.",
        4: "Buena cobertura, solo faltan aspectos menores.",
        5: "Cobertura completa de todos los conceptos clave del documento.",
    },
}

QUIZ_PEDAGOGICAL_RUBRIC = {
    "name": "quiz_pedagogical_quality",
    "description": "¿Las preguntas evalúan comprensión real del contenido?",
    "scale": {
        1: "Preguntas triviales o que se responden sin entender el tema.",
        2: "Algunas preguntas requieren comprensión pero la mayoría son superficiales.",
        3: "Las preguntas evalúan comprensión general pero no profundizan en conceptos.",
        4: "Buenas preguntas que requieren entender el material para responder correctamente.",
        5: "Preguntas excelentes que evalúan comprensión, aplicación y relación de conceptos.",
    },
}

QUIZ_DISTRACTOR_RUBRIC = {
    "name": "quiz_distractor_plausibility",
    "description": "¿Los distractores (opciones incorrectas) son creíbles?",
    "scale": {
        1: "Distractores absurdos o descartables a simple vista sin conocer el tema.",
        2: "Algunos distractores son plausibles pero la mayoría son obvios.",
        3: "Los distractores son razonables pero un estudiante atento los descarta fácilmente.",
        4: "Distractores plausibles que requieren comprensión real para descartarlos.",
        5: "Distractores excelentes: cada uno representa un error conceptual realista.",
    },
}


ALL_RUBRICS = [
    PPTX_RELEVANCE_RUBRIC,
    PPTX_COHERENCE_RUBRIC,
    PPTX_COMPLETENESS_RUBRIC,
    QUIZ_PEDAGOGICAL_RUBRIC,
    QUIZ_DISTRACTOR_RUBRIC,
]


def format_rubric_for_prompt(rubric: dict) -> str:
    """Formatea una rúbrica como texto para incluir en un prompt de evaluación."""
    lines = [f"CRITERIO: {rubric['description']}", "ESCALA:"]
    for level, desc in rubric["scale"].items():
        lines.append(f"  {level} — {desc}")
    return "\n".join(lines)
