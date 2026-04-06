"""
Constructor de prompts para los modelos de IA.

Cada función construye un prompt para una tarea concreta del pipeline.
Todos los prompts reciben el idioma del documento para garantizar
que la salida esté en el mismo idioma que el PDF.
"""

from config.settings import (
    MAX_BULLETS_PER_SLIDE, MIN_BULLETS_PER_SLIDE,
    MIN_SECTIONS, MAX_SECTIONS,
    QUIZ_OPTIONS_PER_QUESTION,
)


# ---------------------------------------------------------------------------
# Fase 1 — Análisis Map-Reduce del documento
# ---------------------------------------------------------------------------

def build_chunk_topics_prompt(chunk: str, doc_title: str) -> str:
    """
    Fase MAP: extrae 1-3 temas del fragmento recibido.
    Respuesta muy corta — no genera viñetas, solo títulos y conceptos clave.

    Respuesta esperada:
    {
      "language": "español",
      "topics": [
        { "title": "...", "key_points": ["...", "..."] }
      ]
    }
    """
    return f"""Eres un experto en análisis de documentos académicos.

Lee el siguiente fragmento e identifica los temas principales que trata.

TAREA:
1. Detecta el idioma del fragmento.
2. Identifica entre 1 y 3 temas distintos que aparezcan en el texto.
3. Para cada tema: un título corto (máximo 6 palabras) y 2-4 conceptos clave.

REGLAS:
- Devuelve ÚNICAMENTE JSON válido, sin texto adicional.
- Solo incluye temas que realmente aparezcan en el fragmento.
- Los conceptos clave son ideas concretas del texto, no palabras sueltas.
- Si el fragmento no tiene contenido relevante: {{"language": "español", "topics": []}}

DOCUMENTO: {doc_title}

FRAGMENTO:
{chunk}

RESPUESTA (solo JSON):
{{
  "language": "español",
  "topics": [
    {{
      "title": "...",
      "key_points": ["...", "..."]
    }}
  ]
}}"""


def build_merge_sections_prompt(topics_text: str, doc_title: str) -> str:
    """
    Fase REDUCE: recibe todos los temas extraídos de todos los chunks y los
    fusiona en una estructura final coherente de 4-8 secciones.

    Respuesta esperada:
    {
      "language": "español",
      "sections": [
        { "title": "...", "key_points": ["...", "...", "..."] }
      ]
    }
    """
    return f"""Eres un experto en síntesis de documentos académicos.

A continuación tienes todos los temas identificados en un documento, extraídos fragmento a fragmento.
Tu tarea es consolidarlos en una estructura final coherente.

TAREA:
1. Identifica el idioma predominante.
2. Fusiona temas duplicados o muy similares en uno solo.
3. Agrupa temas relacionados si hay demasiados.
4. Devuelve entre {MIN_SECTIONS} y {MAX_SECTIONS} secciones finales que cubran todo el documento.
5. Para cada sección: título descriptivo (máximo 8 palabras) y 3-5 conceptos clave combinados.

REGLAS:
- Devuelve ÚNICAMENTE JSON válido.
- Las secciones deben cubrir el documento de forma equilibrada.
- Mantén el orden temático lógico (no cronológico por fragmento).
- No inventes temas que no estén en la lista de entrada.

DOCUMENTO: {doc_title}

TEMAS EXTRAÍDOS:
{topics_text}

RESPUESTA (solo JSON):
{{
  "language": "español",
  "sections": [
    {{
      "title": "...",
      "key_points": ["...", "...", "..."]
    }}
  ]
}}"""


# ---------------------------------------------------------------------------
# Fase 3 — Generación de contenido por sección
# ---------------------------------------------------------------------------

def build_section_content_prompt(
    section_title: str,
    key_points: list[str],
    context: str,
    doc_title: str,
    language: str,
) -> str:
    """
    Genera 4-5 viñetas completas para una sección concreta del documento.
    Recibe el título, los conceptos clave identificados en el análisis
    y el texto relevante del documento como contexto.

    Respuesta esperada:
    { "bullets": ["...", "...", "...", "..."] }
    """
    key_points_text = "\n".join(f"- {p}" for p in key_points)
    return f"""Eres un experto en comunicación académica.

Genera el contenido completo para una diapositiva de presentación sobre el tema indicado.

IDIOMA OBLIGATORIO: responde en {language}. Todas las viñetas en {language}.

TAREA:
Escribe exactamente {MIN_BULLETS_PER_SLIDE} o {MAX_BULLETS_PER_SLIDE} viñetas sobre "{section_title}".

CONCEPTOS QUE DEBEN CUBRIRSE:
{key_points_text}

REGLAS ESTRICTAS:
- Devuelve ÚNICAMENTE JSON válido.
- Genera entre {MIN_BULLETS_PER_SLIDE} y {MAX_BULLETS_PER_SLIDE} viñetas. NUNCA menos de {MIN_BULLETS_PER_SLIDE}.
- Cada viñeta: frase completa con sujeto y predicado, entre 10 y 15 palabras MÁXIMO.
- Cada viñeta DEBE terminar con punto.
- Las viñetas deben explicar, argumentar o contextualizar — no solo nombrar.
- Usa el texto de contexto como fuente principal. No inventes datos.
- No repitas la misma idea con distintas palabras.
- PROHIBIDO escribir "..." o texto de ejemplo. Cada elemento debe ser una frase real y completa.
- Evita viñetas triviales como "Este tema es importante" o "Existen varios tipos".

DOCUMENTO: {doc_title}

TEXTO DE CONTEXTO:
{context}

EJEMPLO DE FORMATO CORRECTO (sustituye por frases reales sobre el tema):
{{
  "bullets": [
    "El aprendizaje supervisado entrena modelos usando datos etiquetados para predecir resultados.",
    "Las redes neuronales profundas permiten extraer características complejas de forma automática."
  ]
}}"""


# ---------------------------------------------------------------------------
# Conclusiones
# ---------------------------------------------------------------------------

def build_conclusion_prompt(slides_titles: list[str], doc_title: str, language: str) -> str:
    titles_text = "\n".join(f"- {t}" for t in slides_titles)
    return f"""Eres un experto en síntesis académica.

A partir de los temas tratados, redacta entre {MIN_BULLETS_PER_SLIDE} y {MAX_BULLETS_PER_SLIDE}
conclusiones que sinteticen los aprendizajes clave de la presentación.

IDIOMA OBLIGATORIO: responde en {language}.

REGLAS:
- Devuelve ÚNICAMENTE JSON válido.
- Cada conclusión: frase completa argumentativa, entre 10 y 15 palabras MÁXIMO.
- Cada conclusión DEBE terminar con punto.
- No repitas los títulos literalmente: sintetiza el aprendizaje.
- Las conclusiones deben aportar valor, no ser redundantes.
- PROHIBIDO escribir "..." o texto de ejemplo. Cada elemento debe ser una frase real.

DOCUMENTO: {doc_title}
TEMAS TRATADOS:
{titles_text}

EJEMPLO DE FORMATO CORRECTO (sustituye por conclusiones reales):
{{
  "bullets": [
    "La inteligencia artificial transforma sectores productivos al automatizar tareas repetitivas.",
    "El aprendizaje profundo ha superado a los humanos en tareas específicas de reconocimiento."
  ]
}}"""


# ---------------------------------------------------------------------------
# Enriquecimiento de slides con pocas viñetas
# ---------------------------------------------------------------------------

def build_enrich_prompt(
    title: str,
    existing_bullets: list[str],
    needed: int,
    doc_title: str,
    language: str,
) -> str:
    bullets_text = "\n".join(f"- {b}" for b in existing_bullets)
    return f"""Eres un experto en comunicación académica.

La siguiente diapositiva necesita más viñetas. Añade exactamente {needed} viñeta(s) nueva(s).

IDIOMA OBLIGATORIO: responde en {language}.

REGLAS:
- Devuelve ÚNICAMENTE JSON válido.
- Cada viñeta nueva: frase completa, entre 10 y 15 palabras MÁXIMO.
- Cada viñeta DEBE terminar con punto.
- No repitas ni parafrasees las viñetas existentes.
- Mantén coherencia temática con el título.
- PROHIBIDO escribir "..." o texto de ejemplo. Cada elemento debe ser una frase real.

DOCUMENTO: {doc_title}
TÍTULO: {title}
VIÑETAS EXISTENTES:
{bullets_text}

EJEMPLO DE FORMATO CORRECTO (sustituye por frases reales sobre el tema):
{{
  "bullets": [
    "Los algoritmos de clasificación identifican patrones en datos para asignar categorías.",
    "El procesamiento del lenguaje natural permite a las máquinas comprender texto humano."
  ]
}}"""


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

def build_quiz_prompt(chunk: str, doc_title: str, language: str) -> str:
    return f"""Eres un profesor experto en evaluación académica universitaria con amplia experiencia en diseño de tests de opción múltiple.

IDIOMA OBLIGATORIO: todas las preguntas, opciones y explicaciones en {language}.

PRE-FILTRO OBLIGATORIO:
Si el fragmento es principalmente portada, índice, tabla de contenidos, bibliografía,
agradecimientos, prólogo, metadatos editoriales o texto sin conceptos educativos:
→ devuelve exactamente: {{"questions": []}}

TAREA: genera entre 1 y 3 preguntas de test de alta calidad sobre el fragmento.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIPOS DE PREGUNTA PERMITIDOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Definición: ¿qué es X? / ¿cómo se define X?
✓ Relación: ¿cómo se relaciona X con Y? / ¿qué causa X?
✓ Aplicación: ¿en qué situación se usa X? / ¿para qué sirve X?
✓ Comparación: ¿en qué se diferencia X de Y?
✓ Consecuencia: ¿qué ocurre cuando X? / ¿cuál es el efecto de X?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROHIBICIONES ABSOLUTAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ Preguntar sobre: autor, nombre del libro, editorial, año, ISBN, precio, página.
✗ Preguntar datos que no aparezcan en el fragmento.
✗ Preguntas con respuesta obvia que no requieran comprensión real.
✗ Preguntas ambiguas o con más de una respuesta posiblemente correcta.
✗ Preguntas que se respondan leyendo literalmente una frase sin entender nada.
✗ Preguntas del tipo "¿cuál ES UNA de las..." o "¿cuál PUEDE SER..." — siempre una única respuesta inequívoca.
✗ Si el fragmento menciona varias aplicaciones/ventajas/usos de algo, NO preguntes "¿cuál es una aplicación de X?" porque varias opciones podrían ser correctas. En ese caso formula la pregunta de forma que solo una sea válida.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS PARA LAS OPCIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Exactamente {QUIZ_OPTIONS_PER_QUESTION} opciones por pregunta.
• Solo 1 correcta, inequívoca y sin lugar a debate.
• Los 3 distractores DEBEN seguir estas estrategias pedagógicas:
    - Distractor 1: error conceptual común (confunde el concepto con otro relacionado).
    - Distractor 2: verdadero en otro contexto pero incorrecto aquí.
    - Distractor 3: parcialmente correcto pero incompleto o con un detalle erróneo.
• Longitud equilibrada: ninguna opción debe ser claramente más larga o más corta que las demás.
• Estructura gramatical idéntica en las 4 opciones (todas frases nominales, o todas verbales).
• PROHIBIDO: "todas las anteriores", "ninguna de las anteriores", "no se menciona en el texto",
  opciones de una sola palabra, opciones absurdas o descartables a simple vista.
• La opción correcta NO debe ser siempre la más larga ni la más específica.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTOCOMPROBACIÓN ANTES DE RESPONDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Antes de generar el JSON, verifica mentalmente:
1. ¿Podría un estudiante que entiende el tema descartar los 3 distractores con seguridad?
2. ¿Podría algún distractor considerarse también correcto? Si es así, cámbialo.
3. ¿Las 4 opciones tienen longitud y estructura similares?
4. ¿La explicación justifica por qué la correcta es la única válida?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPLICACIÓN OBLIGATORIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Entre 20 y 50 palabras.
• Cita o parafrasea el fragmento que justifica la respuesta correcta.
• Explica brevemente por qué los distractores son incorrectos.

DOCUMENTO: {doc_title}

FRAGMENTO:
{chunk}

FORMATO JSON (sustituye los ejemplos por preguntas reales sobre el fragmento):
{{
  "questions": [
    {{
      "text": "¿Cuál es la principal ventaja del aprendizaje no supervisado frente al supervisado?",
      "options": [
        "No requiere datos etiquetados previamente, por lo que funciona sin intervención humana.",
        "Utiliza datos etiquetados para categorizar información nueva con mayor precisión.",
        "Necesita que un experto valide cada resultado antes de aplicarlo en producción.",
        "Solo puede aplicarse cuando el conjunto de datos contiene menos de mil registros."
      ],
      "correct_index": 0,
      "explanation": "El aprendizaje no supervisado descubre patrones sin necesidad de ejemplos etiquetados. Las otras opciones describen características del supervisado, de la validación manual y de una limitación inventada, respectivamente.",
      "topic": "Aprendizaje automático",
      "difficulty": "media"
    }}
  ]
}}"""
