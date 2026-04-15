"""
Generador de plantillas para evaluación manual.

Crea archivos CSV pre-rellenados con las columnas necesarias para que
el evaluador humano solo tenga que asignar puntuaciones.
"""

import csv
from pathlib import Path

from benchmark.evaluation.rubrics import ALL_RUBRICS


def generate_manual_eval_csv(
    output_path: Path,
    executions: list[dict],
) -> Path:
    """
    Genera un CSV con una fila por ejecución (PDF×modelo) y columnas
    para cada criterio subjetivo.

    Args:
        output_path: ruta del CSV a crear.
        executions: lista de dicts con al menos {pdf_id, model}.

    Returns:
        Path al CSV creado.
    """
    rubric_names = [r["name"] for r in ALL_RUBRICS]

    fieldnames = [
        "pdf_id",
        "model",
        *rubric_names,
        "quiz_answer_correctness_pct",
        "notes",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ex in executions:
            row = {
                "pdf_id": ex["pdf_id"],
                "model": ex["model"],
                **{name: "" for name in rubric_names},
                "quiz_answer_correctness_pct": "",
                "notes": "",
            }
            writer.writerow(row)

    return output_path


def generate_rubric_reference(output_path: Path) -> Path:
    """
    Genera un archivo de texto con todas las rúbricas como referencia
    para el evaluador humano.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["RÚBRICAS DE EVALUACIÓN — REFERENCIA", "=" * 50, ""]

    for rubric in ALL_RUBRICS:
        lines.append(f"### {rubric['name']}")
        lines.append(f"{rubric['description']}")
        lines.append("")
        for level, desc in rubric["scale"].items():
            lines.append(f"  {level} — {desc}")
        lines.append("")
        lines.append("-" * 40)
        lines.append("")

    lines.extend([
        "### quiz_answer_correctness_pct",
        "Porcentaje de preguntas cuya respuesta marcada como correcta",
        "realmente lo es. Revisa cada pregunta del quiz y cuenta.",
        "Ejemplo: 12 de 14 correctas → 85.7%",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
