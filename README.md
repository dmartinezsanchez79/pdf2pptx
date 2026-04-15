# pdf2pptx

Herramienta local y offline para convertir documentos PDF en presentaciones PowerPoint estructuradas y cuestionarios interactivos tipo test, usando modelos de lenguaje locales a través de Ollama.

Proyecto desarrollado como Trabajo de Fin de Grado de Ingeniería Informática.

---

## Características principales

- Genera presentaciones `.pptx` con portada, índice, diapositivas de desarrollo y conclusiones.
- Genera cuestionarios tipo test con preguntas de opción múltiple, distractores plausibles y explicaciones.
- Extrae y convierte tablas del PDF a formato markdown para preservar su estructura.
- Describe imágenes embebidas mediante un modelo multimodal local (LLaVA), insertando las descripciones en el lugar correcto del documento.
- Funciona completamente **offline** — ningún dato sale de la máquina.
- Compatible con cualquier modelo disponible en Ollama (llama3, mistral, gemma2, gemma3, qwen2.5...).
- Detecta automáticamente el idioma del documento y genera todo en ese idioma.
- Interfaz web con Streamlit — sin instalación de cliente, sin terminal visible para el usuario.

---

## Requisitos

- Python 3.10 o superior
- [Ollama](https://ollama.com) instalado y ejecutándose (`ollama serve`)
- Al menos un modelo de texto descargado, por ejemplo:
  ```bash
  ollama pull gemma3:4b
  ollama pull mistral:7b
  ollama pull gemma2:9b
  ```
- Para descripción de imágenes (opcional pero recomendado):
  ```bash
  ollama pull llava-llama3:8b
  ```
- GPU Nvidia recomendada para velocidad aceptable (CPU funciona pero es lento)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/pdf2pptx.git
cd pdf2pptx

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno virtual
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / macOS

# 4. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso

### Generación de presentación y/o quiz

```bash
venv\Scripts\activate
streamlit run app.py
```

Se abre automáticamente en `http://localhost:8501`.

1. Selecciona el modelo Ollama en el panel lateral.
2. Elige el modo: solo PPTX, solo quiz, o ambos.
3. Sube el PDF.
4. Pulsa **Generar**.
5. Descarga el `.pptx` generado.

### Quiz interactivo

Una vez generado el quiz desde `app.py`, ábrelo en una segunda terminal:

```bash
streamlit run quiz_app.py
```

Flujo del quiz:
- Pantalla de inicio con número de preguntas y botón Comenzar.
- Una pregunta por pantalla con barra de progreso y contador.
- Navegación Anterior / Siguiente / Finalizar.
- Pantalla de resultados con puntuación, revisión completa y explicaciones.

---

## Modelos recomendados

| Modelo | VRAM | Calidad | Velocidad (RTX 3060) |
|---|---|---|---|
| `llama3.2:3b` | ~2.5 GB | Baja | Rápido |
| `gemma3:4b` | ~3 GB | **Muy alta** | **Rápido** |
| `mistral:7b` | ~5 GB | Media | Lento |
| `qwen2.5:7b` | ~5 GB | Media | **Muy rápido** |
| `gemma2:9b` | ~6 GB | Alta | Medio |

Según el benchmark realizado (5 PDFs × 5 modelos, 25 ejecuciones, ver [`TRACEABILITY.md`](TRACEABILITY.md) §11):
- **Mejor calidad global:** `gemma3:4b` (13.8 preguntas válidas de media, 8.8 slides de desarrollo, 99.3% JSON success rate).
- **Mejor relación calidad/tiempo:** `gemma3:4b` (235 s de media para PPTX + quiz).
- **Peor relación calidad/tiempo:** `mistral:7b` (358 s y solo 7.6 preguntas válidas).
- **Menor fiabilidad:** `llama3.2:3b` (71.8% JSON success rate, requiere muchos reintentos).

Para descripción de imágenes se usa siempre `llava-llama3:8b` independientemente del modelo de texto seleccionado.

---

## Tiempos estimados (RTX 3060, modo "ambos")

| Tamaño PDF | Imágenes | Tiempo aprox. |
|---|---|---|
| ~10.000 chars (~8 páginas) | 0 | 2-3 min |
| ~20.000 chars (~15 páginas) | 0 | 4-5 min |
| ~30.000 chars (~25 páginas) | 0 | 7-9 min |
| ~50.000 chars (~40 páginas) | 0 | 10-13 min |
| Cualquier tamaño | +1 imagen | +20-40 s/imagen |

---

## Estructura del proyecto

```
pdf2pptx/
├── app.py                          # Interfaz principal — generación PPTX y quiz
├── quiz_app.py                     # Interfaz del quiz interactivo (app separada)
├── debug_extraction.py             # Script de depuración de extracción (desarrollo)
├── requirements.txt
├── assets/
│   └── plantilla_universidad.pptx  # Plantilla institucional UCAM
├── config/
│   └── settings.py                 # Todos los parámetros ajustables
├── quiz_data/
│   └── quiz.json                   # Quiz generado (se sobreescribe en cada generación)
└── src/
    ├── domain/
    │   └── models.py               # Dataclasses: Slide, Presentation, Question, Quiz...
    ├── extraction/
    │   ├── pdf_reader.py           # Lectura de texto y tablas del PDF con pdfplumber
    │   ├── image_describer.py      # Extracción y descripción de imágenes con LLaVA
    │   ├── text_cleaner.py         # Limpieza, segmentación, chunking y clean_for_quiz
    │   └── language_detector.py    # Detección de idioma por frecuencia de stopwords
    ├── ai/
    │   ├── ollama_client.py        # Cliente Ollama con reintentos y parseo JSON
    │   ├── prompt_builder.py       # Construcción de todos los prompts del sistema
    │   └── exceptions.py           # OllamaConnectionError, MaxRetriesExceeded
    ├── generation/
    │   ├── document_analyzer.py    # Análisis Map-Reduce del documento (fases 1 y 2)
    │   ├── presentation_service.py # Pipeline PPTX de 4 fases
    │   ├── slide_normalizer.py     # Normalización post-IA de slides
    │   └── quiz_service.py         # Pipeline del quiz Map-Reduce
    ├── validation/
    │   ├── slide_validator.py      # Validación determinista de slides
    │   └── quiz_validator.py       # Validación fuerte de preguntas
    └── rendering/
        └── pptx_renderer.py        # Escritura del .pptx con la plantilla
├── benchmark/
│   ├── run_benchmark.py            # Orquestador: N PDFs × M modelos
│   ├── config.py                   # Configuración del experimento
│   ├── metrics/                    # Métricas automatizadas (PPTX, quiz, modelo)
│   ├── evaluation/                 # Rúbricas, prompts IA externa, plantillas
│   ├── reports/                    # CSVs y resúmenes generados
│   ├── results/                    # Outputs de cada ejecución
│   └── dataset/                    # Catálogo y PDFs de test
```

---

## Parámetros de configuración (`config/settings.py`)

| Parámetro | Valor | Descripción |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo de texto por defecto |
| `VISION_MODEL` | `llava-llama3:8b` | Modelo multimodal para descripción de imágenes |
| `OLLAMA_TIMEOUT` | `120` s | Timeout por llamada |
| `OLLAMA_MAX_RETRIES` | `3` | Reintentos si el JSON es inválido |
| `CHUNK_SIZE` | `3000` | Caracteres por chunk |
| `CHUNK_OVERLAP` | `200` | Solapamiento entre chunks |
| `PDF_MAX_CHUNKS` | `15` | Chunks máximos (~42.000 chars cubiertos al 100%) |
| `MIN_SECTIONS` | `4` | Mínimo de secciones en el análisis |
| `MAX_SECTIONS` | `8` | Máximo de secciones en el análisis |
| `MAX_BULLETS_PER_SLIDE` | `5` | Viñetas máximas por diapositiva |
| `MIN_BULLETS_PER_SLIDE` | `4` | Viñetas mínimas (se enriquece si hay menos) |
| `MAX_BULLET_LENGTH` | `100` | Caracteres máximos por viñeta |
| `MAX_CONTENT_SLIDES` | `10` | Diapositivas de desarrollo máximas |
| `QUIZ_MAX_QUESTIONS` | `15` | Preguntas máximas del quiz |

---

## Benchmark y comparación de modelos

El proyecto incluye un sistema de benchmark automatizado para comparar modelos:

```bash
# Benchmark completo (5 PDFs × 5 modelos = 25 ejecuciones)
python -m benchmark.run_benchmark

# Subconjunto filtrado
python -m benchmark.run_benchmark --models gemma3:4b mistral:7b --pdfs pdf_01 pdf_02
```

Genera automáticamente:
- Métricas objetivas de PPTX, quiz y rendimiento del modelo
- PPTX y quiz de cada ejecución para revisión
- Prompts estandarizados para evaluación con IA externa (ChatGPT/Gemini)
- CSVs resumen y plantillas de evaluación manual

Ver `TRACEABILITY.md` sección 11 para la metodología completa.

---

## Limitaciones conocidas

- Solo procesa PDFs con texto digital seleccionable. Los PDFs escaneados no son compatibles.
- La descripción de imágenes requiere que `llava-llama3:8b` esté disponible en Ollama. Si no está instalado, las imágenes se omiten sin error.
- PDFs de más de ~42.000 caracteres se procesan parcialmente (últimas páginas ignoradas). Ajustable con `PDF_MAX_CHUNKS`.
- La calidad del resultado depende del modelo usado y de la claridad del PDF de entrada.

---

## Líneas de trabajo futuro

- Soporte OCR para PDFs escaneados (`pytesseract` + `pdf2image`).

- Exportación del quiz a otros formatos (Moodle XML, Anki).
- Inclusión de imágenes descritas directamente en las diapositivas PPTX.
