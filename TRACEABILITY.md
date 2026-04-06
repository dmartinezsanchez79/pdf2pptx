# Trazabilidad del proyecto — pdf2pptx

Documento de seguimiento de decisiones de diseño, arquitectura, pipeline y desarrollo del TFG.
Última actualización: abril 2026.

---

## 1. Descripción general

**Objetivo:** construir una herramienta local y offline que reciba un PDF y genere automáticamente una presentación PowerPoint estructurada y/o un cuestionario tipo test, usando modelos de lenguaje locales (Ollama).

**Contexto:** Trabajo de Fin de Grado de Ingeniería Informática — UCAM.

**Restricciones de diseño:**
- Funcionamiento completamente offline. Ningún dato sale de la máquina del usuario.
- IA siempre local vía Ollama. Nunca APIs externas (OpenAI, Anthropic, etc.).
- Código modular, limpio y defendible en tribunal académico.
- Independencia del modelo: funciona con llama3, mistral, gemma2, qwen2.5, etc.
- El mismo modelo seleccionado se usa para todas las llamadas del pipeline de texto; el modelo de visión (LLaVA) se configura por separado.

---

## 2. Arquitectura general

```
PDF
 └─► Extracción + limpieza
       ├─► Texto por página (pdfplumber)
       ├─► Tablas → markdown (pdfplumber.extract_tables)
       └─► Imágenes → descripción en español (pymupdf + llava-llama3:8b)
             └─► ExtractedDocument (raw_text enriquecido)
                   ├─► Pipeline PPTX (4 fases)
                   │     ├─► Análisis Map-Reduce → DocumentStructure
                   │     ├─► Búsqueda de contexto por sección
                   │     ├─► Generación de slides por sección
                   │     ├─► Normalización post-IA
                   │     └─► Renderizado con plantilla → .pptx
                   └─► Pipeline Quiz (Map-Reduce)
                         ├─► Limpieza agresiva del texto
                         ├─► Filtro de chunks pedagógicamente válidos
                         ├─► Generación de preguntas por chunk
                         ├─► Validación fuerte
                         └─► quiz.json → quiz_app.py
```

### Capas y responsabilidades

| Capa | Módulos | Responsabilidad |
|---|---|---|
| Dominio | `models.py` | Tipos de datos compartidos entre capas |
| Extracción | `pdf_reader`, `image_describer`, `text_cleaner`, `language_detector` | Leer, limpiar, enriquecer y segmentar el PDF |
| IA | `ollama_client`, `prompt_builder`, `exceptions` | Comunicación con el modelo local |
| Análisis | `document_analyzer` | Análisis global del documento (Map-Reduce) |
| Generación | `presentation_service`, `slide_normalizer`, `quiz_service` | Orquestar los pipelines |
| Validación | `slide_validator`, `quiz_validator` | Garantizar calidad de la salida |
| Renderizado | `pptx_renderer` | Escribir el archivo .pptx con plantilla |
| Interfaz | `app.py`, `quiz_app.py` | Interfaces web con Streamlit |
| Config | `settings.py` | Parámetros centralizados y ajustables |

---

## 3. Pipeline PPTX — 4 fases

### Fase 1 — Análisis Map-Reduce del documento

**Problema resuelto:** el pipeline antiguo procesaba el documento chunk a chunk sin visión global, generando slides duplicados, sin coherencia temática y sin cubrir todo el documento.

**Solución:** análisis en dos pasos antes de generar ningún slide.

**MAP** — 1 llamada por chunk:
- El texto completo se divide en chunks de 3.000 chars.
- Cada chunk se manda al modelo con `build_chunk_topics_prompt()`.
- El modelo devuelve 1-3 temas con título y conceptos clave.
- Resultado: lista de temas en bruto (con duplicados).

**REDUCE** — 1 llamada:
- Se mandan todos los temas al modelo (solo títulos + conceptos, ~2.000 chars).
- El modelo los fusiona y consolida en 4-8 secciones finales coherentes.
- También detecta el idioma del documento.
- Resultado: `DocumentStructure(language, sections[])`.

**Ventaja clave:** el REDUCE recibe solo los temas (texto compacto), no el documento completo. Cabe perfectamente en contexto aunque el PDF sea largo.

### Fase 2 — Búsqueda de contexto por sección (sin IA)

Para cada sección identificada en el análisis:
- Se extraen palabras clave del título y conceptos clave (palabras de ≥4 chars).
- Se generan ventanas deslizantes de 3.000 chars sobre el texto completo.
- Se puntúa cada ventana por cuántas palabras clave contiene.
- Se devuelve la ventana con mayor puntuación como contexto de esa sección.

**Decisión:** esta fase no usa el modelo. Es búsqueda determinista por frecuencia de palabras clave. Ahorra llamadas y es reproducible.

### Fase 3 — Generación de slides por sección

- 1 llamada al modelo por sección (4-8 llamadas típicamente).
- Cada llamada recibe: título de la sección + conceptos clave + contexto localizado.
- El modelo genera 4-5 viñetas completas en el idioma detectado.
- Cada viñeta pasa por `validate_slide()` antes de usarse.

### Fase 4 — Normalización post-IA

Aplicada en orden sobre todos los slides:
1. **Fusionar viñetas cortas** — viñetas con <6 palabras se fusionan con la siguiente.
2. **Enriquecer slides pobres** — slides con <4 viñetas reciben una llamada extra al modelo.
3. **Fusionar slides vecinas pobres** — dos slides consecutivos pobres se fusionan si caben juntos.
4. **Dividir slides excesivos** — slides con >5 viñetas se parten en dos.
5. **Cap** — máximo `MAX_CONTENT_SLIDES` slides de desarrollo.

### Ensamblado final

```
Portada ("Resumen del documento") → Índice → Slides de desarrollo → Conclusión
```
- El índice se construye DESPUÉS de la normalización, sobre los títulos reales finales.
- El índice contiene exactamente los mismos títulos que aparecerán en las diapositivas.
- La portada tiene siempre título fijo y subtítulo con el nombre del PDF original.

---

## 4. Pipeline Quiz — Map-Reduce

### Preprocesado específico para quiz

Antes de chunking, se aplica `clean_for_quiz()` — limpieza más agresiva que la del PPTX:
- Elimina URLs, emails, direcciones web.
- Elimina líneas con ISBN, precios, copyright, depósito legal.
- Elimina líneas de bios de autor (coautor, ha impartido, seminarios, conferenciante).
- Elimina líneas que son solo números, teléfonos, fax.
- Elimina artefactos de exportadores PDF (patrón `NombreArchivo_FIN`).

**Justificación:** el quiz necesita texto con valor pedagógico puro. El PPTX puede tolerar algo de ruido porque los prompts de slides son más robustos, pero el quiz generaría preguntas triviales o corruptas con texto sucio.

### Filtro de chunks (`_is_quiz_worthy`)

Antes de mandar un chunk al modelo, se verifica:
- Mínimo 40 palabras.
- Longitud media de línea ≥30 chars (rechaza índices, tablas de contenidos, portadas).
- Densidad de entradas TOC ≤25% (líneas que terminan en número de página).
- Densidad de líneas biográficas <2 (rechaza contraportadas y bios de autores).

**Justificación:** evita gastar una llamada al modelo en fragmentos que no contienen conceptos educativos.

### Generación

- 1 llamada por chunk válido.
- El modelo genera 1-3 preguntas por chunk.
- Se para al llegar a `QUIZ_MAX_QUESTIONS`.
- El prompt incluye estrategias explícitas para los 3 distractores: error conceptual común / verdadero en otro contexto / parcialmente correcto con detalle erróneo.
- El prompt incluye una sección de autocomprobación que el modelo debe ejecutar antes de responder.

### Validación fuerte

Se descartan preguntas si:
- Texto de pregunta <25 chars.
- Pregunta sobre autor, ISBN, año, editorial, página — detección por regex (`_TRIVIAL_PATTERNS`).
- Preguntas biográficas (`¿quién es/fue`, `¿qué hizo [persona]`).
- Preguntas autorreferenciales sobre el propio documento/libro.
- Contiene URLs, placeholders `"..."` o encoding roto.
- Alguna opción <8 chars o >200 chars.
- Alguna opción contiene frases prohibidas ("todas las anteriores", etc.).
- La opción más larga es >3x la más corta (respuesta correcta obvia por longitud).
- Las opciones empiezan todas con la misma palabra (indicio de títulos de capítulo).
- ≥3 opciones tienen <5 palabras (opciones tipo etiqueta, no distractores reales).
- Explicación <20 chars.
- Solapamiento de palabras con otra pregunta >60% (duplicado semántico).

---

## 5. Extracción enriquecida

### 5.1 Tablas

`pdf_reader.py` extrae las tablas de cada página con `pdfplumber.extract_tables()` y las convierte a formato markdown (`| col | col |`). El markdown se añade al texto de la página antes de pasarlo al pipeline.

**Justificación:** `extract_text()` mezcla las columnas de las tablas produciendo texto ilegible. El formato markdown preserva la estructura y el modelo lo entiende correctamente.

**Filtros aplicados:** se ignoran tablas vacías o de una sola fila (cabeceras sin datos).

### 5.2 Imágenes (visión multimodal)

`image_describer.py` usa `pymupdf` (fitz) para extraer imágenes por página. Cada imagen se convierte a base64 y se envía a `llava-llama3:8b` con una instrucción en español. La descripción resultante se inserta en el texto en la posición de la página donde aparece la imagen, con el formato `[Imagen página N]: descripción`.

**Deduplicación:** se rastrean los `xref` de pymupdf para evitar describir el mismo recurso (logo, marca de agua) más de una vez aunque aparezca en varias páginas.

**Degradación elegante:** si LLaVA no está disponible o la llamada falla, la imagen se omite silenciosamente sin interrumpir el pipeline.

---

## 6. Decisiones de diseño

### 6.1 Modelos de dominio tipados

**Decisión:** usar `@dataclass` tipados como contrato interno entre capas. Nunca diccionarios sueltos entre módulos.

**Modelos principales:**
- `ExtractedDocument` — resultado de leer el PDF
- `DocumentStructure` + `Section` — resultado del análisis
- `Slide` + `Presentation` — modelo de la presentación
- `Question` + `Quiz` — modelo del cuestionario
- `QuestionResult` + `QuizResult` — resultados de una sesión de quiz

**Justificación:** los dataclasses ofrecen tipado explícito, autocompletado, legibilidad sin documentación adicional y detección de errores en tiempo de análisis estático.

### 6.2 El modelo siempre devuelve JSON

**Decisión:** todos los prompts instruyen al modelo para responder únicamente con JSON válido con esquema concreto incluido en el prompt.

**Justificación:** parsear texto libre es frágil e impredecible. JSON es determinista y validable. Si el modelo devuelve JSON malformado, `ollama_client.py` reintenta hasta 3 veces.

### 6.3 Separación estricta IA / validación determinista

**Decisión:** la IA genera contenido, la validación local lo corrige o descarta. Nunca se muestra al usuario output directo del modelo sin pasar por validación.

**Justificación:** la calidad no puede depender exclusivamente del modelo. La capa de validación actúa como red de seguridad independiente del modelo usado, lo que facilita la comparación entre modelos.

### 6.4 Detección de idioma sin dependencias externas

**Decisión:** `language_detector.py` detecta el idioma por frecuencia de stopwords características de cada idioma (español, inglés, portugués, francés, alemán, italiano).

**Justificación:** evita dependencias externas como `langdetect` o `langid`. Funciona offline y es suficientemente preciso para los idiomas más comunes en documentos académicos.

### 6.5 Temperatura baja en el modelo

**Decisión:** `temperature = 0.3` en todas las llamadas.

**Justificación:** produce respuestas más deterministas y con mejor adherencia al formato JSON. Valores altos aumentan creatividad pero también la tasa de JSON malformados.

### 6.6 Portada con título fijo

**Decisión:** la portada siempre muestra "Resumen del documento" como título y "Presentación generada a partir de {nombre_pdf}" como subtítulo.

**Justificación:** el título inferido del PDF suele ser la primera línea del texto, que puede ser el nombre del autor, un encabezado de página o texto parcial. Un título fijo garantiza coherencia visual. El nombre del PDF se propaga desde `uploaded_file.name` para mostrar el nombre real, no el nombre del fichero temporal que crea Streamlit.

### 6.7 Viñetas garantizadas completas

**Decisión:** si una viñeta supera `MAX_BULLET_LENGTH` (100 chars), se busca el último signo de puntuación dentro del límite. Si lo hay → se corta ahí (frase completa). Si no → se descarta la viñeta entera.

**Justificación:** nunca mostrar una frase cortada a mitad. Preferimos menos viñetas a viñetas ininteligibles. El enriquecimiento de slides compensa las viñetas descartadas.

### 6.8 Streamlit como interfaz

**Decisión:** interfaz web con Streamlit en lugar de CLI.

**Justificación:** elimina problemas de encoding en terminales Windows, permite subir PDFs con caracteres especiales en el nombre, proporciona descarga directa del .pptx y componentes visuales para el quiz. Para una aplicación de datos/IA es el estándar en prototipado académico y profesional.

**Consideración de escalado:** en un entorno de producción real se separaría en FastAPI (backend) + React (frontend). Streamlit es la decisión correcta para el alcance de un TFG.

### 6.9 Quiz como aplicación Streamlit separada

**Decisión:** el quiz corre en `quiz_app.py` (puerto 8502) separado de la generación en `app.py` (puerto 8501). El estado se comparte mediante `quiz_data/quiz.json`.

**Justificación:** el quiz tiene un ciclo de vida diferente a la generación. Separarlo permite que el usuario genere una vez y responda el quiz múltiples veces sin necesidad de regenerar.

### 6.10 Modelo de visión separado del modelo de texto

**Decisión:** `VISION_MODEL` en `settings.py` es independiente de `OLLAMA_MODEL`. El usuario selecciona el modelo de texto en la UI; el modelo de visión es fijo (`llava-llama3:8b`).

**Justificación:** los modelos multimodales (LLaVA) son una familia diferente a los modelos de texto. No todos los modelos de texto soportan visión. Separar la configuración evita errores y permite que el pipeline de texto y el de visión evolucionen independientemente.

---

## 7. Cobertura del documento

Con `CHUNK_SIZE=3000`, `CHUNK_OVERLAP=200`, `PDF_MAX_CHUNKS=15`:

- Cobertura total garantizada: **~42.000 caracteres (~30 páginas)**.
- PDFs más largos se procesan parcialmente (las últimas páginas se ignoran).
- Ajustable subiendo `PDF_MAX_CHUNKS` en `settings.py`.

| PDF | Chunks | Cobertura |
|---|---|---|
| <42.000 chars | ≤15 | 100% |
| 50.000 chars | 15 (cap) | ~84% |
| 60.000 chars | 15 (cap) | ~70% |

---

## 8. Llamadas al modelo por documento

Para un PDF de ~20.000 chars (7 chunks), modo "ambos", sin imágenes:

| Fase | Llamadas | Para qué |
|---|---|---|
| MAP análisis | 7 | Extraer temas de cada chunk |
| REDUCE estructura | 1 | Consolidar secciones finales |
| Generación slides | 5-8 | Una por sección |
| Enriquecimiento | 0-3 | Slides con pocas viñetas |
| Conclusión | 1 | Síntesis final |
| Quiz (chunks válidos) | 5-7 | 1-3 preguntas por chunk |
| **Total (texto)** | **~19-27** | |
| Descripción imágenes | N | 1 llamada a LLaVA por imagen única |

---

## 9. Limitaciones conocidas

| Limitación | Causa | Estado |
|---|---|---|
| PDFs escaneados no soportados | `extract_text()` devuelve vacío | Pendiente (OCR futuro) |
| Solo imágenes de mapa de bits | pymupdf no extrae gráficos vectoriales | Aceptado |
| Descripción de imágenes requiere LLaVA instalado | Modelo de visión separado | Degradación elegante si no está |
| PDFs largos procesados parcialmente | `PDF_MAX_CHUNKS` limita el procesado | Ajustable en settings.py |
| Calidad variable según modelo | Diferencias entre LLMs | Objetivo de comparación del TFG |

---

## 10. Fases de desarrollo

| Fase | Contenido |
|---|---|
| 0 | Entorno, estructura de directorios, `requirements.txt`, `settings.py` |
| 1 | Modelos de dominio (`models.py`) — 11 dataclasses tipados |
| 2 | Extracción del PDF (`pdf_reader.py`, `text_cleaner.py`) |
| 3 | Cliente IA (`ollama_client.py`, `prompt_builder.py`, `exceptions.py`) |
| 4 | Pipeline PPTX Map-Reduce simple (versión inicial) |
| 5 | Validación determinista de slides (`slide_validator.py`) |
| 6 | Renderizado con plantilla universitaria (`pptx_renderer.py`) |
| 7 | Pipeline quiz Map-Reduce (`quiz_service.py`, `quiz_validator.py`) |
| 8 | Interfaz web Streamlit (`app.py`) |
| 9 | Detección de idioma (`language_detector.py`) |
| 10 | Normalización post-IA de slides (`slide_normalizer.py`) |
| 11 | Rediseño pipeline PPTX a 4 fases (`document_analyzer.py`) |
| 12 | Análisis Map-Reduce completo (cobertura 100% del documento) |
| 13 | Mejoras de calidad PPTX: portada fija, viñetas completas, prompts estrictos |
| 14 | Quiz independiente pregunta a pregunta (`quiz_app.py`) |
| 15 | Mejoras de calidad quiz: `clean_for_quiz`, filtro chunks, validación fuerte |
| 16 | Extracción de tablas como markdown (`pdfplumber.extract_tables`) |
| 17 | Descripción de imágenes con LLaVA (`image_describer.py`, pymupdf) |
| 18 | Fix índice PPTX: títulos exactos y completos sin truncar |
| 19 | Mejoras avanzadas de calidad del quiz: filtro TOC/bio, distractores tipificados, autocomprobación en prompt, validación de longitud de opciones |

---

## 11. Dependencias principales

| Librería | Versión mínima | Uso |
|---|---|---|
| `pdfplumber` | 0.10.0 | Extracción de texto y tablas de PDFs |
| `pymupdf` | 1.23.0 | Extracción de imágenes de PDFs |
| `python-pptx` | 0.6.23 | Generación y escritura de archivos .pptx |
| `ollama` | 0.3.0 | Cliente Python para Ollama (texto y visión) |
| `streamlit` | 1.35.0 | Interfaces web |

---

## 12. Métricas del proyecto

- **Líneas de código totales:** ~3.100
- **Líneas de código puro:** ~2.000 (65%)
- **Líneas de comentarios/docstrings:** ~400 (13%)
- **Líneas en blanco:** ~700 (22%)
- **Ficheros Python:** 18 (sin contar `__init__.py`)
- **Ficheros de lógica de negocio** (`src/`): 14
