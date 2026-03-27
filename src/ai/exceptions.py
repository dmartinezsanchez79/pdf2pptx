"""Excepciones propias de la capa de IA."""


class OllamaConnectionError(Exception):
    """No se pudo conectar con el servidor Ollama."""


class OllamaResponseError(Exception):
    """El modelo respondió pero el contenido no es válido o parseable."""


class MaxRetriesExceeded(Exception):
    """Se agotaron los reintentos sin obtener una respuesta válida."""
