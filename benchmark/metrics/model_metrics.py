"""
Recolector de métricas de rendimiento del modelo durante la ejecución.

Se inyecta como wrapper del OllamaClient para capturar:
- Número de llamadas al modelo
- Número de reintentos
- Tiempo por llamada
- Tasa de éxito de JSON
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ModelMetrics:
    """Métricas acumuladas de las llamadas al modelo durante una ejecución."""
    llm_calls: int = 0
    llm_retries: int = 0
    llm_call_times: list[float] = field(default_factory=list)

    def record_call(self, duration: float) -> None:
        self.llm_calls += 1
        self.llm_call_times.append(duration)

    def avg_call_time(self) -> float:
        if not self.llm_call_times:
            return 0.0
        return sum(self.llm_call_times) / len(self.llm_call_times)

    def total_llm_time(self) -> float:
        return sum(self.llm_call_times)

    def json_success_rate(self) -> float:
        total_attempts = self.llm_calls + self.llm_retries
        if total_attempts == 0:
            return 0.0
        return self.llm_calls / total_attempts * 100

    def to_dict(self) -> dict:
        return {
            "llm_calls_total": self.llm_calls,
            "llm_retries_total": self.llm_retries,
            "llm_avg_call_seconds": round(self.avg_call_time(), 2),
            "llm_total_time_seconds": round(self.total_llm_time(), 2),
            "json_success_rate": round(self.json_success_rate(), 1),
        }


class InstrumentedClient:
    """
    Wrapper del OllamaClient que captura métricas de cada llamada.
    Pásalo como client al PresentationService / QuizService.

    Lee los contadores de reintentos directamente del client real
    (OllamaClient.total_calls / total_retries) para obtener datos fieles.
    """

    def __init__(self, real_client, metrics: ModelMetrics) -> None:
        self._real = real_client
        self._metrics = metrics
        # Exponer atributos necesarios del client real
        self.model = real_client.model

    def generate_json(self, prompt: str) -> dict:
        retries_before = self._real.total_retries
        start = time.perf_counter()
        try:
            result = self._real.generate_json(prompt)
            duration = time.perf_counter() - start
            retries_used = self._real.total_retries - retries_before
            self._metrics.record_call(duration)
            self._metrics.llm_retries += retries_used
            return result
        except Exception:
            duration = time.perf_counter() - start
            retries_used = self._real.total_retries - retries_before
            self._metrics.llm_retries += retries_used
            raise

    def describe_image(self, image_bytes: bytes) -> str:
        """Delega a LLaVA — no se cuenta en métricas del modelo de texto."""
        return self._real.describe_image(image_bytes)
