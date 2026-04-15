"""
Generador de informes y tablas resumen a partir de los resultados del benchmark.

Lee los JSONs individuales de cada ejecución y genera:
1. CSV resumen con todas las métricas objetivas (1 fila por ejecución)
2. CSV agregado por modelo (medias de todas las métricas)
3. Resumen en texto para incluir en la memoria del TFG
"""

import csv
import json
from pathlib import Path

from benchmark.config import RESULTS_DIR, REPORTS_DIR


# Métricas objetivas que van al CSV resumen
_METRIC_COLUMNS = [
    # Identificación
    "pdf_id", "model", "repetition",
    # Tiempos
    "total_time_seconds", "pptx_time_seconds", "quiz_time_seconds",
    # Modelo
    "llm_calls_total", "llm_retries_total", "json_success_rate",
    "llm_avg_call_seconds", "llm_total_time_seconds",
    # PPTX
    "pptx_total_slides", "pptx_content_slides", "pptx_avg_bullets_per_slide",
    "pptx_bullets_in_range_pct", "pptx_total_bullets", "pptx_avg_bullet_length",
    "pptx_index_matches_slides", "pptx_conclusion_bullets",
    # Quiz
    "quiz_questions_generated", "quiz_questions_valid", "quiz_pass_rate",
    "quiz_unique_topics", "quiz_topic_diversity",
    "quiz_avg_option_length_ratio", "quiz_has_explanation_rate",
    "quiz_avg_question_length", "quiz_avg_option_length",
    # Estado
    "status", "error",
]


def generate_summary_csv(output_path: Path | None = None) -> Path:
    """
    Lee todos los JSON de resultados y genera un CSV resumen.
    Una fila por ejecución (PDF×modelo×repetición).
    """
    if output_path is None:
        output_path = REPORTS_DIR / "benchmark_summary.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _load_all_results()

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_METRIC_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return output_path


def generate_model_averages_csv(output_path: Path | None = None) -> Path:
    """
    Genera un CSV con las métricas medias por modelo (agregando todos los PDFs).
    """
    if output_path is None:
        output_path = REPORTS_DIR / "model_averages.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _load_all_results()

    # Agrupar por modelo
    by_model: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("status") != "ok":
            continue
        model = row["model"]
        by_model.setdefault(model, []).append(row)

    # Métricas numéricas a promediar
    numeric_cols = [c for c in _METRIC_COLUMNS if c not in
                    ("pdf_id", "model", "repetition", "status", "error",
                     "pptx_index_matches_slides", "quiz_difficulty_distribution")]

    avg_rows = []
    for model, model_rows in sorted(by_model.items()):
        avg = {"model": model, "n_executions": len(model_rows)}
        for col in numeric_cols:
            values = []
            for r in model_rows:
                val = r.get(col)
                if val is not None and val != "":
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass
            avg[col] = round(sum(values) / len(values), 2) if values else ""
        # Index matches: porcentaje de True
        matches = [r.get("pptx_index_matches_slides") for r in model_rows]
        avg["pptx_index_matches_pct"] = round(
            sum(1 for m in matches if m) / len(matches) * 100, 1
        ) if matches else ""
        avg_rows.append(avg)

    avg_columns = ["model", "n_executions"] + numeric_cols + ["pptx_index_matches_pct"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=avg_columns, extrasaction="ignore")
        writer.writeheader()
        for row in avg_rows:
            writer.writerow(row)

    return output_path


def generate_text_summary() -> str:
    """Genera un resumen legible de los resultados para la memoria del TFG."""
    rows = _load_all_results()
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    failed = [r for r in rows if r.get("status") != "ok"]

    if not ok_rows:
        return "No hay resultados válidos."

    lines = [
        f"RESUMEN DEL BENCHMARK",
        f"{'=' * 50}",
        f"Ejecuciones totales: {len(rows)}",
        f"Ejecuciones exitosas: {len(ok_rows)}",
        f"Ejecuciones fallidas: {len(failed)}",
        f"Tasa de éxito: {len(ok_rows)/len(rows)*100:.1f}%",
        "",
    ]

    # Agrupar por modelo
    by_model: dict[str, list[dict]] = {}
    for row in ok_rows:
        by_model.setdefault(row["model"], []).append(row)

    for model, model_rows in sorted(by_model.items()):
        avg_time = _avg(model_rows, "total_time_seconds")
        avg_quiz = _avg(model_rows, "quiz_questions_valid")
        avg_slides = _avg(model_rows, "pptx_content_slides")
        avg_json = _avg(model_rows, "json_success_rate")

        lines.extend([
            f"\n--- {model} ---",
            f"  Tiempo medio: {avg_time:.0f}s",
            f"  Preguntas válidas (media): {avg_quiz:.1f}",
            f"  Slides de desarrollo (media): {avg_slides:.1f}",
            f"  JSON success rate: {avg_json:.1f}%",
        ])

    return "\n".join(lines)


def _load_all_results() -> list[dict]:
    """Carga todos los JSONs de resultados individuales."""
    results = []
    results_dir = RESULTS_DIR
    if not results_dir.exists():
        return results

    for json_file in sorted(results_dir.glob("result_*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            # Aplanar métricas anidadas
            flat = {}
            flat["pdf_id"] = data.get("pdf_id", "")
            flat["model"] = data.get("model", "")
            flat["repetition"] = data.get("repetition", 1)
            flat["status"] = data.get("status", "unknown")
            flat["error"] = data.get("error", "")
            flat["total_time_seconds"] = data.get("total_time_seconds", "")
            flat["pptx_time_seconds"] = data.get("pptx_time_seconds", "")
            flat["quiz_time_seconds"] = data.get("quiz_time_seconds", "")

            # Métricas del modelo
            for k, v in data.get("model_metrics", {}).items():
                flat[k] = v
            # Métricas PPTX
            for k, v in data.get("pptx_metrics", {}).items():
                flat[k] = v
            # Métricas Quiz
            for k, v in data.get("quiz_metrics", {}).items():
                if not isinstance(v, dict):  # excluir difficulty_distribution
                    flat[k] = v

            results.append(flat)
        except Exception:
            continue

    return results


def _avg(rows: list[dict], key: str) -> float:
    values = []
    for r in rows:
        val = r.get(key)
        if val is not None and val != "":
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                pass
    return sum(values) / len(values) if values else 0.0
