"""
Cliente de comunicación con Ollama.

Responsabilidades:
  - Enviar prompts al modelo local y devolver la respuesta.
  - Extraer y parsear el JSON de la respuesta (con reintentos).
  - Aislar al resto del proyecto de la librería `ollama`.

No construye prompts: eso lo hace prompt_builder.
No interpreta el contenido: eso lo hacen los servicios de generación.
"""

from __future__ import annotations

import json
import re
import time

import ollama

import base64

from config.settings import OLLAMA_MODEL, OLLAMA_HOST, OLLAMA_TIMEOUT, OLLAMA_MAX_RETRIES, VISION_MODEL
from src.ai.exceptions import OllamaConnectionError, OllamaResponseError, MaxRetriesExceeded


class OllamaClient:
    """Wrapper sobre la librería ollama con reintentos y extracción de JSON."""

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        host: str = OLLAMA_HOST,
        timeout: int = OLLAMA_TIMEOUT,
        max_retries: int = OLLAMA_MAX_RETRIES,
    ) -> None:
        self.model = model
        self.max_retries = max_retries
        self._client = ollama.Client(host=host, timeout=timeout)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generate_json(self, prompt: str) -> dict:
        """
        Envía el prompt al modelo y devuelve el JSON parseado.

        Reintenta hasta `max_retries` veces si la respuesta no es JSON válido.
        Raises MaxRetriesExceeded si ningún intento tiene éxito.
        """
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                raw = self._call_model(prompt)
                return self._parse_json(raw)
            except OllamaConnectionError:
                raise  # No tiene sentido reintentar si Ollama no está corriendo
            except OllamaResponseError as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1)  # pausa breve antes de reintentar

        raise MaxRetriesExceeded(
            f"No se obtuvo JSON válido tras {self.max_retries} intentos. "
            f"Último error: {last_error}"
        )

    def describe_image(self, image_bytes: bytes) -> str:
        """
        Envía una imagen al modelo de visión (LLaVA) y devuelve una descripción textual.
        Usa VISION_MODEL independientemente del modelo de texto seleccionado.
        Devuelve cadena vacía si falla para no interrumpir el pipeline.
        """
        prompt = (
            "Describe detalladamente el contenido de esta imagen en español. "
            "Si es un diagrama, gráfica o tabla: explica qué muestra y qué conclusiones se extraen. "
            "Si es una fotografía: describe los elementos principales. "
            "Responde siempre en español, independientemente del idioma de la imagen. "
            "Responde solo con la descripción, sin introducción ni comentarios adicionales."
        )
        try:
            response = self._client.generate(
                model=VISION_MODEL,
                prompt=prompt,
                images=[base64.b64encode(image_bytes).decode()],
                options={"temperature": 0.2},
            )
            return response.response.strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _call_model(self, prompt: str) -> str:
        """Llama a Ollama y devuelve el texto de la respuesta."""
        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": 0.3},  # baja temperatura → más determinista
            )
            return response.response.strip()
        except ollama.ResponseError as e:
            raise OllamaConnectionError(
                f"Error al comunicarse con Ollama (¿está corriendo?): {e}"
            ) from e
        except Exception as e:
            raise OllamaConnectionError(f"Error inesperado con Ollama: {e}") from e

    def _parse_json(self, raw: str) -> dict:
        """
        Extrae y parsea el JSON de la respuesta del modelo.

        Los LLM a veces envuelven el JSON en bloques ```json ... ```.
        Esta función lo maneja extrayendo solo el bloque JSON.
        """
        # Intento directo
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Buscar bloque ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Buscar el primer { ... } del texto
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise OllamaResponseError(
            f"La respuesta del modelo no contiene JSON válido.\n"
            f"Respuesta recibida:\n{raw[:500]}"
        )
