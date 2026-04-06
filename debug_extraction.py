"""
Script de diagnóstico — extracción de texto, tablas e imágenes.

Uso:
    python debug_extraction.py ruta/al/archivo.pdf
"""

import sys
import io
from pathlib import Path

# Forzar UTF-8 en la salida de la terminal (necesario en Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.extraction.pdf_reader import read_pdf
from src.extraction.image_describer import enrich_with_vision
from src.ai.ollama_client import OllamaClient


def main():
    if len(sys.argv) < 2:
        print("Uso: python debug_extraction.py ruta/al/archivo.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"ERROR: No se encuentra el archivo: {pdf_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"PDF: {pdf_path.name}")
    print(f"{'='*60}\n")

    # 1. Leer PDF (texto + tablas)
    print(">>> Paso 1: Leyendo texto y tablas...")
    document = read_pdf(pdf_path)
    print(f"    Título inferido : {document.title}")
    print(f"    Secciones       : {len(document.sections)}")
    print(f"    Caracteres totales (texto + tablas): {len(document.raw_text):,}")

    # Detectar si hay tablas en el texto (aparecen como líneas con |)
    table_lines = [l for l in document.raw_text.splitlines() if l.startswith("|")]
    print(f"    Líneas de tabla detectadas: {len(table_lines)}")

    # 2. Enriquecer con visión (imágenes)
    print("\n>>> Paso 2: Describiendo imágenes con LLaVA...")
    client = OllamaClient()
    document, n_images = enrich_with_vision(document, pdf_path, client)
    print(f"    Imágenes descritas: {n_images}")

    # 3. Mostrar el texto completo enriquecido
    print(f"\n{'='*60}")
    print("TEXTO COMPLETO EXTRAÍDO (texto + tablas + imágenes):")
    print(f"{'='*60}\n")
    print(document.raw_text)

    print(f"\n{'='*60}")
    print(f"TOTAL: {len(document.raw_text):,} caracteres")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
