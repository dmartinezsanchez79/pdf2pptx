"""
Configuración del benchmark.

Define los modelos a comparar, los PDFs del dataset,
y los parámetros del experimento.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

BENCHMARK_DIR = Path(__file__).parent
DATASET_DIR = BENCHMARK_DIR / "dataset"
PDFS_DIR = DATASET_DIR / "pdfs"
RESULTS_DIR = BENCHMARK_DIR / "results"
REPORTS_DIR = BENCHMARK_DIR / "reports"

# ---------------------------------------------------------------------------
# Modelos a comparar
# ---------------------------------------------------------------------------

BENCHMARK_MODELS: list[str] = [
    "llama3.2:3b",
    "mistral:7b",
    "gemma2:9b",
    "qwen2.5:7b",
    "gemma3:4b",
]

# ---------------------------------------------------------------------------
# Catálogo de PDFs
# ---------------------------------------------------------------------------
# Se carga desde dataset/catalog.json — ver dataset/catalog.json para el formato.
CATALOG_FILE = DATASET_DIR / "catalog.json"

# ---------------------------------------------------------------------------
# Parámetros del experimento
# ---------------------------------------------------------------------------

# Número de repeticiones por combinación PDF×modelo (para medir varianza)
# 1 repetición es suficiente para un TFG salvo que quieras medir estabilidad
REPETITIONS: int = 1
