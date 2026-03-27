"""
Aplicación independiente del quiz interactivo.

Carga el quiz generado por app.py (guardado en quiz_data/quiz.json)
y permite responderlo con corrección inmediata y revisión final.

Ejecutar con:
    streamlit run quiz_app.py
"""

import json
from pathlib import Path

import streamlit as st

from src.domain.models import Question, Quiz, QuestionResult, QuizResult

QUIZ_FILE = Path("quiz_data/quiz.json")
LABELS = ["A", "B", "C", "D"]

# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Quiz interactivo",
    page_icon="🧠",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Carga del quiz
# ---------------------------------------------------------------------------

def _load_quiz() -> Quiz | None:
    if not QUIZ_FILE.exists():
        return None
    data = json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    questions = [
        Question(
            text=q["text"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q.get("explanation", ""),
        )
        for q in data["questions"]
    ]
    return Quiz(title=data["title"], questions=questions)


def _quiz_meta() -> dict:
    if not QUIZ_FILE.exists():
        return {}
    data = json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    return {"pdf_name": data.get("pdf_name", ""), "model": data.get("model", "")}


# ---------------------------------------------------------------------------
# Pantalla principal
# ---------------------------------------------------------------------------

st.title("🧠 Quiz interactivo")

quiz = _load_quiz()

if quiz is None:
    st.warning(
        "No hay ningún quiz generado todavía.\n\n"
        "Abre **app.py**, sube un PDF y genera el quiz primero."
    )
    st.stop()

meta = _quiz_meta()
st.caption(f"📄 {meta.get('pdf_name', '')}  |  🤖 {meta.get('model', '')}")
st.markdown(f"### {quiz.title}")
st.markdown(f"{quiz.question_count()} preguntas — Selecciona una opción por pregunta y pulsa **Enviar respuestas**")
st.markdown("---")

# ---------------------------------------------------------------------------
# Formulario del quiz
# ---------------------------------------------------------------------------

with st.form("quiz_form"):
    answers: list[str | None] = []

    for i, q in enumerate(quiz.questions, start=1):
        st.markdown(f"**Pregunta {i}.** {q.text}")
        options = [f"{LABELS[j]}) {opt}" for j, opt in enumerate(q.options)]
        choice = st.radio(
            label=f"pregunta_{i}",
            options=options,
            index=None,
            label_visibility="collapsed",
            key=f"q_{i}",
        )
        answers.append(choice)
        st.markdown("")

    submitted = st.form_submit_button("Enviar respuestas", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

if submitted:
    results: list[QuestionResult] = []
    for q, choice in zip(quiz.questions, answers):
        if choice is None:
            chosen_index = -1   # sin responder
        else:
            label = choice[0]
            chosen_index = LABELS.index(label) if label in LABELS else 0
        results.append(QuestionResult(question=q, chosen_index=max(chosen_index, 0)))

    unanswered = sum(1 for c in answers if c is None)
    if unanswered:
        st.warning(f"{unanswered} pregunta(s) sin responder — cuentan como incorrectas.")

    quiz_result = QuizResult(quiz=quiz, results=results)
    pct = quiz_result.score_percent()

    st.markdown("---")
    st.subheader("Resultado")

    col1, col2, col3 = st.columns(3)
    col1.metric("Puntuación", f"{pct}%")
    col2.metric("Correctas", quiz_result.correct_count())
    col3.metric("Incorrectas", quiz_result.wrong_count())

    if pct >= 80:
        st.success(f"🟢 {pct}% — Excelente")
    elif pct >= 50:
        st.warning(f"🟡 {pct}% — Aprobado")
    else:
        st.error(f"🔴 {pct}% — Repasa el material")

    st.markdown("---")
    st.subheader("Revisión de respuestas")

    for i, qr in enumerate(results, start=1):
        q = qr.question
        chosen_label = LABELS[qr.chosen_index]
        correct_label = LABELS[q.correct_index]

        if qr.is_correct():
            st.success(
                f"**{i}. {q.text}**  \n"
                f"✅ {chosen_label}) {q.options[qr.chosen_index]}"
            )
        else:
            st.error(
                f"**{i}. {q.text}**  \n"
                f"❌ Tu respuesta: {chosen_label}) {q.options[qr.chosen_index]}  \n"
                f"✅ Correcta: {correct_label}) {q.correct_option()}"
            )

        if q.explanation:
            st.caption(f"💡 {q.explanation}")
