"""
Orquestador principal del benchmark.

Ejecuta todos los modelos sobre todos los PDFs del catálogo,
recoge métricas objetivas, genera JSONs de resultados y prepara
los prompts para la evaluación subjetiva con IA externa.

Uso:
    python -m benchmark.run_benchmark
    python -m benchmark.run_benchmark --models gemma3:4b mistral:7b
    python -m benchmark.run_benchmark --pdfs pdf_01 pdf_02
    python -m benchmark.run_benchmark --models gemma3:4b --pdfs pdf_01

Si no se especifican filtros, ejecuta todas las combinaciones del catálogo.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Asegurar que el directorio raíz del proyecto está en el path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.config import (
    BENCHMARK_MODELS, CATALOG_FILE, RESULTS_DIR, REPORTS_DIR,
    PDFS_DIR, REPETITIONS,
)
from benchmark.metrics.model_metrics import ModelMetrics, InstrumentedClient
from benchmark.metrics.pptx_metrics import compute_pptx_metrics
from benchmark.metrics.quiz_metrics import compute_quiz_metrics
from benchmark.evaluation.ai_evaluator import generate_pptx_eval_prompt, generate_quiz_eval_prompt
from benchmark.evaluation.manual_template import (
    generate_manual_eval_csv, generate_rubric_reference,
)
from benchmark.reports.generate_report import (
    generate_summary_csv, generate_model_averages_csv, generate_text_summary,
)

from src.extraction.pdf_reader import read_pdf
from src.extraction.image_describer import enrich_with_vision
from src.ai.ollama_client import OllamaClient
from src.generation.presentation_service import PresentationService
from src.generation.quiz_service import QuizService
from src.rendering.pptx_renderer import render


def load_catalog() -> list[dict]:
    """Carga el catálogo de PDFs."""
    if not CATALOG_FILE.exists():
        print(f"ERROR: No se encuentra el catálogo en {CATALOG_FILE}")
        sys.exit(1)
    data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    return data["pdfs"]


def run_single(pdf_entry: dict, model: str, repetition: int = 1) -> dict:
    """
    Ejecuta una combinación PDF×modelo y devuelve todas las métricas.

    Returns:
        Dict con todas las métricas (serializable a JSON).
    """
    pdf_id = pdf_entry["id"]
    pdf_path = PDFS_DIR / pdf_entry["filename"]

    result = {
        "pdf_id": pdf_id,
        "model": model,
        "repetition": repetition,
        "pdf_filename": pdf_entry["filename"],
        "pdf_type": pdf_entry.get("type", ""),
        "pdf_language": pdf_entry.get("language", ""),
        "status": "pending",
        "error": "",
    }

    if not pdf_path.exists():
        result["status"] = "error"
        result["error"] = f"PDF no encontrado: {pdf_path}"
        return result

    print(f"\n{'='*60}")
    print(f"  {pdf_id} × {model} (rep {repetition})")
    print(f"{'='*60}")

    # Crear cliente instrumentado
    metrics = ModelMetrics()
    real_client = OllamaClient(model=model)
    client = InstrumentedClient(real_client, metrics)

    total_start = time.perf_counter()

    # --- Fase 1: Extracción ---
    print("  [1/4] Extrayendo PDF...")
    try:
        document = read_pdf(pdf_path)
        document.filename = pdf_path.stem
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Error extrayendo PDF: {e}"
        return result

    # --- Fase 1b: Enriquecimiento con visión (opcional) ---
    print("  [1b/4] Analizando imágenes...")
    try:
        document, n_images = enrich_with_vision(document, pdf_path, client)
        result["images_described"] = n_images
    except Exception:
        result["images_described"] = 0

    pdf_excerpt = document.raw_text[:3000]  # Para prompts de evaluación

    # --- Fase 2: Generación PPTX ---
    print(f"  [2/4] Generando PPTX con {model}...")
    pptx_start = time.perf_counter()
    presentation = None
    try:
        service = PresentationService(client)
        presentation = service.generate(document)
        pptx_time = time.perf_counter() - pptx_start
        result["pptx_time_seconds"] = round(pptx_time, 2)

        # Guardar el PPTX generado
        pptx_output = RESULTS_DIR / f"{pdf_id}_{_slug(model)}_rep{repetition}.pptx"
        render(presentation, pptx_output)

        # Métricas PPTX
        result["pptx_metrics"] = compute_pptx_metrics(presentation)
        print(f"       → {presentation.slide_count()} slides en {pptx_time:.0f}s")

    except Exception as e:
        result["pptx_time_seconds"] = round(time.perf_counter() - pptx_start, 2)
        result["pptx_metrics"] = {}
        result["pptx_error"] = str(e)
        print(f"       → ERROR: {e}")

    # --- Fase 3: Generación Quiz ---
    print(f"  [3/4] Generando quiz con {model}...")
    quiz_start = time.perf_counter()
    quiz = None
    try:
        quiz_service = QuizService(client)
        quiz = quiz_service.generate(document)
        quiz_time = time.perf_counter() - quiz_start
        result["quiz_time_seconds"] = round(quiz_time, 2)

        # Métricas quiz (con conteo pre-validación del servicio)
        result["quiz_metrics"] = compute_quiz_metrics(
            quiz, questions_before_validation=quiz_service.questions_before_validation
        )

        # Guardar quiz como JSON
        quiz_output = RESULTS_DIR / f"{pdf_id}_{_slug(model)}_rep{repetition}_quiz.json"
        _save_quiz_json(quiz, quiz_output, pdf_entry["filename"], model)

        print(f"       → {quiz.question_count()} preguntas en {quiz_time:.0f}s")

    except Exception as e:
        result["quiz_time_seconds"] = round(time.perf_counter() - quiz_start, 2)
        result["quiz_metrics"] = {}
        result["quiz_error"] = str(e)
        print(f"       → ERROR: {e}")

    # --- Métricas del modelo ---
    total_time = time.perf_counter() - total_start
    result["total_time_seconds"] = round(total_time, 2)
    result["model_metrics"] = metrics.to_dict()
    result["status"] = "ok"

    print(f"  [4/4] Completado en {total_time:.0f}s "
          f"({metrics.llm_calls} llamadas, {metrics.llm_retries} reintentos)")

    # --- Generar prompts de evaluación para IA externa ---
    eval_dir = RESULTS_DIR / "eval_prompts"
    eval_dir.mkdir(exist_ok=True)

    if presentation:
        prompt = generate_pptx_eval_prompt(presentation, pdf_excerpt, model, pdf_id)
        (eval_dir / f"{pdf_id}_{_slug(model)}_pptx_eval.txt").write_text(
            prompt, encoding="utf-8"
        )

    if quiz:
        prompt = generate_quiz_eval_prompt(quiz, pdf_excerpt, model, pdf_id)
        (eval_dir / f"{pdf_id}_{_slug(model)}_quiz_eval.txt").write_text(
            prompt, encoding="utf-8"
        )

    return result


def run_benchmark(models: list[str] | None = None, pdf_ids: list[str] | None = None):
    """Ejecuta el benchmark completo o un subconjunto filtrado."""
    catalog = load_catalog()

    if pdf_ids:
        catalog = [p for p in catalog if p["id"] in pdf_ids]
    if not catalog:
        print("ERROR: No hay PDFs en el catálogo (o el filtro no encontró ninguno).")
        return

    target_models = models or BENCHMARK_MODELS
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    total = len(catalog) * len(target_models) * REPETITIONS
    print(f"\nBENCHMARK: {len(catalog)} PDFs × {len(target_models)} modelos"
          f" × {REPETITIONS} rep = {total} ejecuciones\n")
    print(f"Modelos: {', '.join(target_models)}")
    print(f"PDFs: {', '.join(p['id'] for p in catalog)}")
    print(f"Resultados en: {RESULTS_DIR}")

    all_results = []
    executions = []
    completed = 0

    for pdf_entry in catalog:
        for model in target_models:
            for rep in range(1, REPETITIONS + 1):
                completed += 1
                print(f"\n[{completed}/{total}]", end="")

                result = run_single(pdf_entry, model, rep)

                # Guardar resultado individual
                result_file = RESULTS_DIR / f"result_{pdf_entry['id']}_{_slug(model)}_rep{rep}.json"
                result_file.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                all_results.append(result)
                executions.append({"pdf_id": pdf_entry["id"], "model": model})

    # --- Post-procesado ---
    print(f"\n{'='*60}")
    print("GENERANDO INFORMES...")
    print(f"{'='*60}")

    # CSV resumen
    summary_path = generate_summary_csv()
    print(f"  CSV resumen: {summary_path}")

    # CSV medias por modelo
    averages_path = generate_model_averages_csv()
    print(f"  CSV medias:  {averages_path}")

    # Resumen textual
    text_summary = generate_text_summary()
    summary_txt = REPORTS_DIR / "benchmark_summary.txt"
    summary_txt.write_text(text_summary, encoding="utf-8")
    print(f"  Resumen TXT: {summary_txt}")
    print(f"\n{text_summary}")

    # Plantillas de evaluación manual (incluye TODAS las ejecuciones acumuladas)
    all_executions = [
        {"pdf_id": r["pdf_id"], "model": r["model"]}
        for r in _load_all_results_for_manual()
    ]
    manual_csv = generate_manual_eval_csv(
        REPORTS_DIR / "manual_evaluation.csv", all_executions
    )
    print(f"  CSV evaluación manual: {manual_csv}")

    rubric_ref = generate_rubric_reference(
        REPORTS_DIR / "rubric_reference.txt"
    )
    print(f"  Referencia rúbricas:   {rubric_ref}")

    # Resumen de errores
    errors = [r for r in all_results if r["status"] != "ok"]
    if errors:
        print(f"\n  ERRORES ({len(errors)}):")
        for e in errors:
            print(f"    - {e['pdf_id']} × {e['model']}: {e['error']}")

    ok = sum(1 for r in all_results if r["status"] == "ok")
    print(f"\nBENCHMARK COMPLETADO: {ok}/{total} exitosas")


def _load_all_results_for_manual() -> list[dict]:
    """Lee todos los JSONs de resultados para construir la plantilla manual acumulada."""
    results = []
    for json_file in sorted(RESULTS_DIR.glob("result_*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            continue
    return results


def _slug(model: str) -> str:
    """Convierte un nombre de modelo en un slug para nombres de archivo."""
    return model.replace(":", "-").replace("/", "-")


def _save_quiz_json(quiz, path: Path, pdf_name: str, model: str) -> None:
    """Guarda el quiz en formato JSON."""
    data = {
        "title": quiz.title,
        "pdf_name": pdf_name,
        "model": model,
        "question_count": quiz.question_count(),
        "questions": [
            {
                "text": q.text,
                "options": q.options,
                "correct_index": q.correct_index,
                "explanation": q.explanation,
                "topic": q.topic,
                "difficulty": q.difficulty,
            }
            for q in quiz.questions
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta el benchmark de pdf2pptx sobre modelos locales."
    )
    parser.add_argument(
        "--models", nargs="+", default=None,
        help="Modelos a ejecutar (por defecto: todos los de config.py)"
    )
    parser.add_argument(
        "--pdfs", nargs="+", default=None,
        help="IDs de PDFs a procesar (por defecto: todos los del catálogo)"
    )
    args = parser.parse_args()
    run_benchmark(models=args.models, pdf_ids=args.pdfs)


if __name__ == "__main__":
    main()
