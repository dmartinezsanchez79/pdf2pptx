# Trazabilidad del proyecto — pdf2pptx

Documento de seguimiento de decisiones de diseño, arquitectura y desarrollo del TFG.

---

## 1. Descripción general

**Objetivo:** construir una herramienta local/offline que reciba un PDF y genere automáticamente una presentación PowerPoint y/o un cuestionario tipo test, usando modelos de lenguaje locales (Ollama).

**Contexto:** Trabajo de Fin de Grado de Ingeniería Informática.

**Restricciones principales:**
- Funcionamiento completamente local (sin APIs externas, sin envío de datos).
- Código modular, limpio y mantenible, defendible en tribunal académico.
- Independencia del modelo: compatible con llama3, mistral, gemma2, qwen, etc.

---

## 2. Arquitectura general

Se adoptó una arquitectura en capas con responsabilidad única por módulo:

```
PDF
 └─► Extracción (pdf_reader + text_cleaner)
       └─► ExtractedDocument
             └─► IA (ollama_client + prompt_builder)
                   └─► Validación (slide_validator / quiz_validator)
                         └─► Renderizado (pptx_renderer)
                               └─► Salida (.pptx / quiz en navegador)
```

### Capas y responsabilidades

| Capa | Módulos | Responsabilidad |
|---|---|---|
| Dominio | `models.py` | Tipos de datos compartidos entre capas |
| Extracción | `pdf_reader`, `text_cleaner` | Leer y limpiar el PDF |
| IA | `ollama_client`, `prompt_builder`, `exceptions` | Comunicación con el modelo |
| Generación | `presentation_service`, `quiz_service` | Orquestar el pipeline |
| Validación | `slide_validator`, `quiz_validator` | Corregir la salida del modelo |
| Renderizado | `pptx_renderer` | Escribir el archivo .pptx |
| Interfaz | `app.py` | Interfaz web con Streamlit |
| Config | `settings.py` | Parámetros centralizados |

---

## 3. Decisiones de diseño

### 3.1 Modelos de dominio en lugar de diccionarios

**Decisión:** usar `@dataclass` tipados (`Slide`, `Presentation`, `Question`, `Quiz`, etc.) como contrato interno entre capas.

**Justificación:** los diccionarios sueltos no documentan su estructura, no se validan en tiempo de análisis estático y dificultan el mantenimiento. Los dataclasses ofrecen autocompletado, tipado explícito y son legibles sin documentación adicional.

### 3.2 Patrón Map-Reduce sobre LLM

**Decisión:** dividir el texto del PDF en chunks solapados y procesar cada uno de forma independiente con el modelo, fusionando los resultados al final.

**Justificación:** los modelos locales tienen una ventana de contexto limitada (~4k-8k tokens útiles). Enviar un PDF completo de 30+ páginas desbordaría el contexto. El solapamiento entre chunks (`CHUNK_OVERLAP = 200` caracteres) evita perder ideas que caigan justo en el corte entre fragmentos.

**Parámetros:**
- `CHUNK_SIZE = 3000` caracteres por chunk
- `CHUNK_OVERLAP = 200` caracteres de solapamiento
- `PDF_MAX_CHUNKS = 12` chunks máximo por documento

### 3.3 La IA solo genera el contenido de desarrollo

**Decisión:** las diapositivas de portada, índice y conclusiones no las genera el modelo directamente a partir del texto crudo — las construye el código de forma determinista.

- **Portada:** usa el título inferido del PDF.
- **Índice:** se construye a partir de los títulos de las diapositivas de desarrollo ya generadas.
- **Conclusiones:** el modelo recibe los títulos del desarrollo y sintetiza los puntos clave.

**Justificación:** garantiza la estructura fija de la presentación sin depender de que el modelo respete un formato específico para slides estructurales. Reduce la probabilidad de fallos y simplifica la validación.

### 3.4 El modelo devuelve JSON estructurado

**Decisión:** todos los prompts instruyen explícitamente al modelo para que responda únicamente con JSON válido, con un esquema concreto incluido en el propio prompt.

**Justificación:** parsear texto libre es frágil. JSON es determinista, fácilmente validable y permite detectar errores de formato con precisión.

**Esquema para slides:**
```json
{
  "slides": [
    { "title": "...", "bullets": ["...", "..."] }
  ]
}
```

**Esquema para preguntas:**
```json
{
  "questions": [
    {
      "text": "...",
      "options": ["...", "...", "...", "..."],
      "correct_index": 0,
      "explanation": "..."
    }
  ]
}
```

### 3.5 Validación determinista post-IA

**Decisión:** tras recibir la respuesta del modelo, una capa de validación local corrige o descarta el contenido que no cumple las reglas antes de renderizarlo.

**Reglas para slides:**
- Título truncado a 80 caracteres si es necesario.
- Máximo 5 viñetas por diapositiva.
- Bullets vacíos eliminados.
- Bullets truncados a 120 caracteres.

**Reglas para preguntas:**
- Exactamente 4 opciones (se truncan si hay más, se descarta si hay menos).
- `correct_index` entre 0 y 3 (se descarta si es inválido).
- Texto de pregunta no vacío.
- Deduplicación por texto normalizado.

**Justificación:** la calidad no depende exclusivamente del modelo. La validación local actúa como red de seguridad independientemente del modelo usado.

### 3.6 Reintentos en el cliente Ollama

**Decisión:** si el modelo no devuelve JSON válido, el cliente reintenta hasta `OLLAMA_MAX_RETRIES = 3` veces con una pausa de 1 segundo entre intentos.

**Justificación:** los LLM locales ocasionalmente fallan el formato JSON en la primera respuesta. Los reintentos resuelven la mayoría de casos sin intervención del usuario. Si se agotan los reintentos, se lanza `MaxRetriesExceeded`.

### 3.7 Temperatura baja en el modelo

**Decisión:** `temperature = 0.3` en todas las llamadas al modelo.

**Justificación:** una temperatura baja produce respuestas más deterministas y con mejor adherencia al formato JSON requerido. Valores más altos aumentan la creatividad pero también la tasa de respuestas malformadas.

### 3.8 Plantilla de la universidad

**Decisión:** usar `assets/plantilla_universidad.pptx` como base para todas las presentaciones generadas.

**Implementación:**
- Se abre la plantilla con `python-pptx`.
- Se eliminan las diapositivas de ejemplo que trae la plantilla.
- Se añaden las nuevas usando los layouts correctos identificados mediante inspección:
  - Layout 0 (`TITLE`): portada.
  - Layout 2 (`TITLE_AND_BODY`): índice, desarrollo y conclusiones.

### 3.9 Interfaz web con Streamlit

**Decisión:** usar Streamlit como interfaz de usuario en lugar de una CLI.

**Justificación:** elimina los problemas de encoding en terminales Windows, proporciona una experiencia de usuario más accesible, permite descarga directa del .pptx y presenta el quiz con componentes visuales (radio buttons, métricas, colores).

**Funcionalidades de la interfaz:**
- Carga dinámica de modelos disponibles en Ollama.
- Selector de modo: pptx / quiz / ambos.
- Uploader de PDF.
- Spinner de progreso durante la generación.
- Botón de descarga del .pptx.
- Quiz interactivo con formulario, corrección inmediata y revisión detallada.

---

## 4. Fases de desarrollo

| Fase | Contenido | Resultado |
|---|---|---|
| 0 | Entorno, estructura de directorios, `requirements.txt`, `settings.py` | Base del proyecto |
| 1 | `src/domain/models.py` | 9 dataclasses tipados |
| 2 | `pdf_reader.py`, `text_cleaner.py` | Extracción y chunking |
| 3 | `ollama_client.py`, `prompt_builder.py`, `exceptions.py` | Cliente IA con reintentos |
| 4 | `presentation_service.py` | Generación PPTX por Map-Reduce |
| 5 | `slide_validator.py` | Validación determinista de slides |
| 6 | `pptx_renderer.py` | Escritura del archivo .pptx con plantilla |
| 7 | `quiz_service.py` | Generación de quiz por Map-Reduce |
| 8 | `quiz_validator.py` | Validación determinista de preguntas |
| 9 | `app.py` | Interfaz web con Streamlit |

---

## 5. Dependencias principales

| Librería | Versión mínima | Uso |
|---|---|---|
| `pdfplumber` | 0.10.0 | Extracción de texto de PDFs |
| `python-pptx` | 0.6.23 | Generación de archivos .pptx |
| `ollama` | 0.3.0 | Cliente Python para Ollama |
| `streamlit` | 1.35.0 | Interfaz web |

---

## 6. Parámetros de configuración (`config/settings.py`)

| Parámetro | Valor | Descripción |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo por defecto |
| `OLLAMA_HOST` | `http://localhost:11434` | URL del servidor Ollama |
| `OLLAMA_TIMEOUT` | `120` s | Timeout por llamada al modelo |
| `OLLAMA_MAX_RETRIES` | `3` | Reintentos si el JSON es inválido |
| `MAX_BULLETS_PER_SLIDE` | `5` | Máximo de viñetas por diapositiva |
| `MAX_TITLE_LENGTH` | `80` | Caracteres máximos en un título |
| `MAX_BULLET_LENGTH` | `120` | Caracteres máximos en una viñeta |
| `MAX_CONTENT_SLIDES` | `10` | Máximo de diapositivas de desarrollo |
| `CHUNK_SIZE` | `3000` | Caracteres por chunk enviado al modelo |
| `CHUNK_OVERLAP` | `200` | Solapamiento entre chunks |
| `PDF_MAX_CHUNKS` | `12` | Chunks máximos a procesar por documento |
| `QUIZ_OPTIONS_PER_QUESTION` | `4` | Opciones por pregunta |
| `QUIZ_MIN_QUESTIONS` | `5` | Mínimo de preguntas para considerar el quiz válido |
| `QUIZ_MAX_QUESTIONS` | `15` | Máximo de preguntas generadas |
| `LAYOUT_TITLE` | `0` | Índice del layout de portada en la plantilla |
| `LAYOUT_CONTENT` | `2` | Índice del layout de contenido en la plantilla |

---

## 7. Estructura de archivos final

```
pdf2pptx/
├── app.py                              # Interfaz web Streamlit
├── requirements.txt                    # Dependencias del proyecto
├── README.md                           # Guía de instalación y uso
├── TRACEABILITY.md                     # Este documento
├── assets/
│   └── plantilla_universidad.pptx      # Plantilla institucional
├── config/
│   └── settings.py                     # Configuración centralizada
├── venv/                               # Entorno virtual (no versionar)
└── src/
    ├── domain/
    │   └── models.py                   # Dataclasses de dominio
    ├── extraction/
    │   ├── pdf_reader.py               # Lectura del PDF
    │   └── text_cleaner.py             # Limpieza, segmentación y chunking
    ├── ai/
    │   ├── exceptions.py               # Excepciones propias de la capa IA
    │   ├── ollama_client.py            # Cliente Ollama con reintentos y parseo JSON
    │   └── prompt_builder.py           # Construcción de prompts por tarea
    ├── generation/
    │   ├── presentation_service.py     # Orquestación Map-Reduce para PPTX
    │   └── quiz_service.py             # Orquestación Map-Reduce para quiz
    ├── validation/
    │   ├── slide_validator.py          # Validación y corrección de slides
    │   └── quiz_validator.py           # Validación y corrección de preguntas
    └── rendering/
        └── pptx_renderer.py            # Escritura del .pptx con la plantilla
```
