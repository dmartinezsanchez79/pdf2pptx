# pdf2pptx

Herramienta local para convertir documentos PDF en presentaciones PowerPoint y cuestionarios interactivos tipo test, utilizando modelos de lenguaje locales a través de Ollama.

## Descripción

pdf2pptx procesa un PDF, extrae su contenido y utiliza IA local para generar automáticamente:

- Una presentación `.pptx` estructurada con portada, índice, diapositivas de desarrollo y conclusiones.
- Un cuestionario tipo test interactivo con preguntas de opción múltiple basadas en el contenido del documento.

Todo el procesamiento ocurre de forma **local y offline**, sin enviar datos a servicios externos.

## Requisitos

- Python 3.10 o superior
- [Ollama](https://ollama.com) instalado y ejecutándose (`ollama serve`)
- Al menos un modelo descargado en Ollama (por ejemplo: `ollama pull llama3.1`)

## Instalación

```bash
# Clonar o descargar el proyecto
cd pdf2pptx

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / macOS

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
# Activar entorno virtual (si no está activo)
venv\Scripts\activate

# Lanzar la interfaz web
streamlit run app.py
```

Se abrirá automáticamente el navegador en `http://localhost:8501`.

### Pasos en la interfaz

1. Selecciona el modelo Ollama en el panel lateral.
2. Elige qué generar: solo presentación, solo quiz o ambos.
3. Sube el PDF.
4. Pulsa **Generar**.
5. Descarga el `.pptx` y/o responde el quiz en el navegador.

## Modelos compatibles

Cualquier modelo disponible en tu instancia local de Ollama. Recomendados:

| Modelo | Tamaño | Velocidad |
|---|---|---|
| `llama3.2` | 2 GB | Rápido |
| `mistral:7b` | 4.4 GB | Equilibrado |
| `llama3.1:8b` | 4.9 GB | Recomendado |
| `gemma2:9b` | 5.4 GB | Alta calidad |

## Estructura del proyecto

```
pdf2pptx/
├── app.py                      # Interfaz web (Streamlit)
├── requirements.txt
├── assets/
│   └── plantilla_universidad.pptx
├── config/
│   └── settings.py             # Configuración global
└── src/
    ├── domain/
    │   └── models.py           # Modelos de dominio
    ├── extraction/
    │   ├── pdf_reader.py       # Lectura del PDF
    │   └── text_cleaner.py     # Limpieza y segmentación
    ├── ai/
    │   ├── ollama_client.py    # Cliente Ollama con reintentos
    │   ├── prompt_builder.py   # Construcción de prompts
    │   └── exceptions.py       # Excepciones propias
    ├── generation/
    │   ├── presentation_service.py
    │   └── quiz_service.py
    ├── validation/
    │   ├── slide_validator.py
    │   └── quiz_validator.py
    └── rendering/
        └── pptx_renderer.py
```

## Configuración

Los parámetros ajustables se encuentran en `config/settings.py`:

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo por defecto |
| `CHUNK_SIZE` | `3000` | Caracteres por fragmento enviado al modelo |
| `MAX_BULLETS_PER_SLIDE` | `5` | Máximo de viñetas por diapositiva |
| `MAX_CONTENT_SLIDES` | `10` | Máximo de diapositivas de desarrollo |
| `QUIZ_MAX_QUESTIONS` | `15` | Máximo de preguntas del quiz |
