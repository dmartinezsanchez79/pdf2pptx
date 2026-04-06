"""
Quiz interactivo — flujo pregunta a pregunta.

Estados:
  start       → pantalla de bienvenida con nº de preguntas y botón Comenzar
  in_progress → una pregunta por pantalla con barra de progreso
  finished    → resumen de resultados y revisión completa

Ejecutar con:
    streamlit run quiz_app.py
"""

import json
from pathlib import Path

import streamlit as st

from src.domain.models import Question, Quiz, QuestionResult, QuizResult

QUIZ_FILE = Path("quiz_data/quiz.json")
LABELS = ["A", "B", "C", "D"]
DIFFICULTY_LABEL = {"fácil": "🟢", "media": "🟡", "difícil": "🔴", "": ""}

st.set_page_config(
    page_title="Quiz interactivo",
    page_icon="🧠",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Carga del quiz
# ---------------------------------------------------------------------------

def _load_quiz() -> tuple[Quiz | None, dict]:
    if not QUIZ_FILE.exists():
        return None, {}
    data = json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    questions = [
        Question(
            text=q["text"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q.get("explanation", ""),
            topic=q.get("topic", ""),
            difficulty=q.get("difficulty", ""),
        )
        for q in data["questions"]
    ]
    quiz = Quiz(title=data["title"], questions=questions)
    meta = {"pdf_name": data.get("pdf_name", ""), "model": data.get("model", "")}
    return quiz, meta


# ---------------------------------------------------------------------------
# Gestión del estado de sesión
# ---------------------------------------------------------------------------

def _init_state(quiz: Quiz) -> None:
    if "quiz_state" not in st.session_state:
        st.session_state.quiz_state = "start"
        st.session_state.current_q = 0
        st.session_state.answers = [-1] * quiz.question_count()


def _reset_state() -> None:
    for key in ["quiz_state", "current_q", "answers"]:
        st.session_state.pop(key, None)
    st.rerun()


# ---------------------------------------------------------------------------
# Pantalla: inicio
# ---------------------------------------------------------------------------

def _render_start(quiz: Quiz, meta: dict) -> None:
    st.markdown("## 🧠 Quiz interactivo")

    pdf_name = meta.get("pdf_name", "")
    model_name = meta.get("model", "")

    if pdf_name:
        st.caption(f"📄 {pdf_name}  |  🤖 {model_name}")
        st.markdown(f"### Quiz generado a partir de **{pdf_name}**")
    else:
        st.markdown("### Quiz interactivo")

    st.markdown("---")

    col1, col2 = st.columns(2)
    col1.metric("Preguntas", quiz.question_count())
    col2.metric("Tipo", "Opción múltiple")

    st.markdown("")
    if st.button("Comenzar quiz", type="primary", use_container_width=True):
        st.session_state.quiz_state = "in_progress"
        st.rerun()


# ---------------------------------------------------------------------------
# Pantalla: pregunta actual
# ---------------------------------------------------------------------------

def _render_question(quiz: Quiz) -> None:
    idx = st.session_state.current_q
    total = quiz.question_count()
    q = quiz.questions[idx]

    # Cabecera con progreso
    progress_val = idx / total
    st.progress(progress_val)

    col_num, col_topic = st.columns([1, 3])
    col_num.markdown(f"**Pregunta {idx + 1} / {total}**")
    if q.topic:
        col_topic.caption(f"📌 {q.topic}")
    if q.difficulty:
        st.caption(f"{DIFFICULTY_LABEL.get(q.difficulty, '')} Dificultad: {q.difficulty}")

    st.markdown("---")
    st.markdown(f"### {q.text}")
    st.markdown("")

    # Opciones — radio con etiquetas A/B/C/D
    option_labels = [f"{LABELS[i]})  {opt}" for i, opt in enumerate(q.options)]

    # Recuperar selección previa si ya respondió esta pregunta
    prev_answer = st.session_state.answers[idx]
    prev_index = prev_answer if prev_answer >= 0 else None

    choice = st.radio(
        label="Elige una opción:",
        options=range(len(option_labels)),
        format_func=lambda i: option_labels[i],
        index=prev_index,
        key=f"radio_{idx}",
        label_visibility="collapsed",
    )

    st.markdown("")

    # Botones de navegación
    col_prev, col_spacer, col_next = st.columns([1, 2, 1])

    with col_prev:
        if idx > 0:
            if st.button("← Anterior", use_container_width=True):
                st.session_state.answers[idx] = choice if choice is not None else -1
                st.session_state.current_q -= 1
                st.rerun()

    with col_next:
        is_last = idx == total - 1
        label = "Finalizar ✓" if is_last else "Siguiente →"
        if st.button(label, type="primary", use_container_width=True):
            st.session_state.answers[idx] = choice if choice is not None else -1
            if is_last:
                st.session_state.quiz_state = "finished"
            else:
                st.session_state.current_q += 1
            st.rerun()


# ---------------------------------------------------------------------------
# Pantalla: resultados finales
# ---------------------------------------------------------------------------

def _render_results(quiz: Quiz) -> None:
    answers = st.session_state.answers

    results = [
        QuestionResult(question=q, chosen_index=max(answers[i], 0))
        for i, q in enumerate(quiz.questions)
    ]
    quiz_result = QuizResult(quiz=quiz, results=results)

    pct = quiz_result.score_percent()
    correct = quiz_result.correct_count()
    wrong = quiz_result.wrong_count()
    unanswered = sum(1 for a in answers if a < 0)

    st.markdown("## Resultados")
    st.progress(pct / 100)
    st.markdown("")

    col1, col2, col3 = st.columns(3)
    col1.metric("Puntuación", f"{pct}%")
    col2.metric("Correctas", correct)
    col3.metric("Incorrectas", wrong)

    if unanswered:
        st.warning(f"{unanswered} pregunta(s) sin responder — contadas como incorrectas.")

    if pct >= 80:
        st.success(f"🟢 Excelente — {pct}%")
    elif pct >= 60:
        st.info(f"🔵 Bien — {pct}%")
    elif pct >= 40:
        st.warning(f"🟡 Aprobado — {pct}%")
    else:
        st.error(f"🔴 Repasa el material — {pct}%")

    st.markdown("---")
    st.markdown("### Revisión de respuestas")
    st.markdown("")

    for i, qr in enumerate(results, start=1):
        q = qr.question
        chosen_label = LABELS[qr.chosen_index]
        correct_label = LABELS[q.correct_index]

        with st.container():
            header = f"**{i}. {q.text}**"
            if q.topic:
                header += f"  \n*{q.topic}*"

            if qr.is_correct():
                st.success(
                    f"{header}  \n"
                    f"✅ {chosen_label}) {q.options[qr.chosen_index]}"
                )
            else:
                chosen_text = q.options[qr.chosen_index] if qr.chosen_index >= 0 else "Sin responder"
                st.error(
                    f"{header}  \n"
                    f"❌ Tu respuesta: {chosen_label}) {chosen_text}  \n"
                    f"✅ Correcta: {correct_label}) {q.correct_option()}"
                )

            if q.explanation:
                st.caption(f"💡 {q.explanation}")

            st.markdown("")

    st.markdown("---")
    if st.button("🔄 Reiniciar quiz", use_container_width=True):
        _reset_state()


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

quiz, meta = _load_quiz()

if quiz is None:
    st.title("🧠 Quiz interactivo")
    st.warning(
        "No hay ningún quiz generado todavía.\n\n"
        "Abre **app.py**, sube un PDF y genera el quiz primero."
    )
    st.stop()

_init_state(quiz)

state = st.session_state.quiz_state

if state == "start":
    _render_start(quiz, meta)
elif state == "in_progress":
    _render_question(quiz)
elif state == "finished":
    _render_results(quiz)
