"""
Interfaz principal — generación de PPTX y/o quiz a partir de un PDF.

Flujo:
  1. El usuario sube un PDF.
  2. Elige modelo Ollama y modo (pptx / quiz / ambos).
  3. Pulsa "Generar".
  4. Descarga el .pptx y/o abre quiz_app.py para responder el quiz.
"""

import json
import tempfile
from pathlib import Path

import ollama
import streamlit as st

from config.settings import OLLAMA_MODEL
from src.extraction.pdf_reader import read_pdf
from src.ai.ollama_client import OllamaClient
from src.ai.exceptions import OllamaConnectionError, MaxRetriesExceeded
from src.generation.presentation_service import PresentationService
from src.generation.quiz_service import QuizService
from src.rendering.pptx_renderer import render
from src.domain.models import Quiz
from src.validation.quiz_validator import has_enough_questions

QUIZ_FILE = Path("quiz_data/quiz.json")


# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="pdf2pptx",
    page_icon="📄",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def _fetch_models() -> list[str]:
    try:
        response = ollama.list()
        return [m.model for m in response.models if m.model]
    except Exception:
        return [OLLAMA_MODEL]


def _read_uploaded_pdf(uploaded_file) -> tuple:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)
    try:
        document = read_pdf(tmp_path)
        # Sobreescribir el filename con el nombre real del PDF subido por el usuario,
        # no el nombre del fichero temporal generado por el sistema.
        document.filename = Path(uploaded_file.name).stem
        return document, None
    except Exception as e:
        return None, str(e)
    finally:
        tmp_path.unlink(missing_ok=True)


def _generate_pptx(client: OllamaClient, document) -> tuple:
    try:
        service = PresentationService(client)
        presentation = service.generate(document)
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        render(presentation, tmp_path)
        data = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        return data, presentation, None
    except OllamaConnectionError as e:
        return None, None, f"Ollama no disponible: {e}"
    except MaxRetriesExceeded as e:
        return None, None, f"El modelo no generó respuestas válidas: {e}"
    except Exception as e:
        return None, None, f"Error inesperado: {e}"


def _generate_and_save_quiz(client: OllamaClient, document, pdf_name: str, model: str) -> tuple:
    try:
        service = QuizService(client)
        quiz = service.generate(document)
        _save_quiz(quiz, pdf_name, model)
        return quiz, None
    except OllamaConnectionError as e:
        return None, f"Ollama no disponible: {e}"
    except MaxRetriesExceeded as e:
        return None, f"El modelo no generó respuestas válidas: {e}"
    except Exception as e:
        return None, f"Error inesperado: {e}"


def _save_quiz(quiz: Quiz, pdf_name: str, model: str) -> None:
    """Serializa el quiz a JSON para que quiz_app.py pueda cargarlo."""
    QUIZ_FILE.parent.mkdir(exist_ok=True)
    data = {
        "title": quiz.title,
        "pdf_name": pdf_name,
        "model": model,
        "questions": [
            {
                "text": q.text,
                "options": q.options,
                "correct_index": q.correct_index,
                "explanation": q.explanation,
            }
            for q in quiz.questions
        ],
    }
    QUIZ_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

st.title("📄 pdf2pptx")
st.caption("Convierte un PDF en presentación PowerPoint y/o quiz interactivo usando IA local.")
st.markdown("---")

with st.sidebar:
    st.header("Configuración")

    available_models = _fetch_models()
    default_idx = available_models.index(OLLAMA_MODEL) if OLLAMA_MODEL in available_models else 0
    selected_model = st.selectbox(
        "Modelo Ollama",
        options=available_models,
        index=default_idx,
        help="Modelos disponibles en tu instancia local de Ollama.",
    )

    mode = st.radio(
        "Generar",
        options=["pptx", "quiz", "ambos"],
        index=2,
        help="Elige qué quieres generar a partir del PDF.",
    )

    st.markdown("---")
    st.caption("Asegúrate de que Ollama esté corriendo antes de generar.")

uploaded = st.file_uploader(
    "Sube tu PDF",
    type=["pdf"],
    help="El contenido del PDF se enviará al modelo en fragmentos.",
)

if uploaded:
    st.success(f"PDF cargado: **{uploaded.name}**")

generate = st.button("Generar", type="primary", disabled=uploaded is None)

# ---------------------------------------------------------------------------
# Pipeline de generación
# ---------------------------------------------------------------------------

if generate and uploaded:
    client = OllamaClient(model=selected_model)

    with st.spinner("Leyendo PDF..."):
        document, error = _read_uploaded_pdf(uploaded)

    if error:
        st.error(f"Error al leer el PDF: {error}")
        st.stop()

    st.info(
        f"**{document.title}** — {len(document.sections)} secciones, "
        f"{len(document.raw_text):,} caracteres"
    )

    generate_pptx = mode in ("pptx", "ambos")
    generate_quiz  = mode in ("quiz", "ambos")

    # PPTX
    if generate_pptx:
        with st.spinner(f"Generando presentación con **{selected_model}**... (puede tardar varios minutos)"):
            pptx_bytes, presentation, error = _generate_pptx(client, document)

        if error:
            st.error(f"Error al generar la presentación: {error}")
        else:
            st.success(
                f"Presentación generada: {presentation.slide_count()} diapositivas "
                f"({len(presentation.content_slides())} de desarrollo)"
            )
            pdf_stem = Path(uploaded.name).stem
            model_slug = selected_model.replace(":", "-").replace("/", "-")
            st.download_button(
                label="Descargar presentación (.pptx)",
                data=pptx_bytes,
                file_name=f"{pdf_stem}_{model_slug}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
            )

    # Quiz
    if generate_quiz:
        with st.spinner(f"Generando quiz con **{selected_model}**... (puede tardar varios minutos)"):
            quiz, error = _generate_and_save_quiz(client, document, uploaded.name, selected_model)

        if error:
            st.error(f"Error al generar el quiz: {error}")
        elif not has_enough_questions(quiz):
            st.warning(
                f"Solo se generaron {quiz.question_count()} preguntas válidas. "
                "El documento puede ser demasiado corto."
            )
        else:
            st.success(f"Quiz generado: {quiz.question_count()} preguntas.")
            st.info(
                "Para realizar el quiz abre una nueva terminal y ejecuta:\n\n"
                "```\nstreamlit run quiz_app.py\n```"
            )
