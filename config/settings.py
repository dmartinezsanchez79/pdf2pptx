"""
Configuración global del proyecto.
Todos los valores ajustables están centralizados aquí.
"""

# --- Modelo Ollama ---
OLLAMA_MODEL: str = "llama3.1:8b"
OLLAMA_HOST: str = "http://localhost:11434"
OLLAMA_TIMEOUT: int = 120          # segundos
OLLAMA_MAX_RETRIES: int = 3

# --- Límites de contenido ---
MAX_BULLETS_PER_SLIDE: int = 5     # máximo de viñetas por diapositiva
MIN_BULLETS_PER_SLIDE: int = 4     # mínimo deseable (slides con menos se enriquecen o fusionan)
MIN_BULLET_WORDS: int = 6          # palabras mínimas por viñeta (viñetas más cortas se fusionan)
MAX_TITLE_LENGTH: int = 80         # caracteres
MAX_BULLET_LENGTH: int = 100       # caracteres (~15 palabras, garantiza que cabe en el slide)
MAX_CONTENT_SLIDES: int = 10       # diapositivas de desarrollo (sin contar portada/índice/conclusión)

# --- Quiz ---
QUIZ_OPTIONS_PER_QUESTION: int = 4
QUIZ_MIN_QUESTIONS: int = 5
QUIZ_MAX_QUESTIONS: int = 15

# --- Análisis de estructura del documento ---
MIN_SECTIONS: int = 4              # mínimo de secciones temáticas a identificar
MAX_SECTIONS: int = 8              # máximo de secciones temáticas a identificar

# --- Extracción de PDF y chunking ---
# El texto del PDF se divide en fragmentos para no superar la ventana de contexto
# del modelo. Cada chunk se procesa por separado (patrón Map-Reduce sobre LLM).
CHUNK_SIZE: int = 3_000            # caracteres por chunk enviado al modelo
CHUNK_OVERLAP: int = 200           # solapamiento entre chunks para no perder contexto en los cortes
PDF_MAX_CHUNKS: int = 15           # máximo de chunks a procesar (cubre PDFs de ~55 páginas)

# --- Visión (tablas e imágenes) ---
VISION_MODEL: str = "llava-llama3:8b"  # modelo multimodal para describir imágenes
VISION_MIN_IMAGE_WIDTH: int = 150      # ignorar imágenes más pequeñas (logos, iconos decorativos)
VISION_MIN_IMAGE_HEIGHT: int = 150

# --- Plantilla PPTX ---
TEMPLATE_PATH: str = "assets/plantilla_universidad.pptx"

# Índice del layout de contenido (inspeccionado con python-pptx)
# La portada usa el slide real de la plantilla, no un layout
LAYOUT_CONTENT: int = 2      # TITLE_AND_BODY — índice, desarrollo y conclusiones (TITLE idx=0, BODY idx=1)

