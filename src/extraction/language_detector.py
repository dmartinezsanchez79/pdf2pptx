"""
Detección de idioma del documento.

Usa frecuencia de palabras vacías (stopwords) sobre una muestra del texto.
No requiere librerías externas.

Devuelve el nombre del idioma en español (ej. "español", "inglés")
para usarlo directamente en los prompts.
"""

# Stopwords representativas por idioma
_STOPWORDS: dict[str, set[str]] = {
    "español": {
        "el", "la", "los", "las", "de", "del", "que", "en", "y", "a",
        "se", "por", "un", "una", "con", "para", "es", "son", "lo",
        "su", "sus", "pero", "como", "este", "esta", "también", "más",
        "hay", "ser", "está", "han", "fue", "al", "le", "si", "sobre",
        "entre", "cuando", "muy", "sin", "hasta", "desde", "nos", "ya",
    },
    "inglés": {
        "the", "of", "and", "to", "in", "is", "it", "that", "was",
        "for", "on", "are", "as", "with", "his", "they", "be", "at",
        "this", "from", "or", "an", "have", "not", "by", "but", "we",
        "you", "all", "were", "when", "there", "their", "what", "which",
        "its", "been", "who", "more", "can", "has", "would", "about",
    },
    "portugués": {
        "de", "a", "o", "que", "e", "do", "da", "em", "um", "para",
        "com", "uma", "os", "no", "se", "na", "por", "mais", "as",
        "dos", "como", "mas", "foi", "ao", "ele", "das", "tem", "sua",
        "sua", "ou", "quando", "muito", "nos", "já", "também", "só",
    },
    "francés": {
        "le", "la", "les", "de", "du", "des", "et", "en", "un", "une",
        "est", "que", "qui", "dans", "il", "je", "pas", "sur", "par",
        "au", "ou", "ce", "son", "se", "pour", "plus", "on", "nous",
        "vous", "leur", "tout", "cette", "avec", "aussi", "mais",
    },
    "alemán": {
        "der", "die", "das", "und", "ist", "in", "den", "von", "zu",
        "mit", "sich", "des", "auf", "ein", "eine", "im", "auch", "als",
        "nicht", "an", "werden", "dem", "nach", "noch", "bei", "dass",
        "sie", "man", "wie", "oder", "aber", "durch", "zum", "kann",
    },
    "italiano": {
        "il", "di", "che", "la", "in", "un", "è", "per", "si", "con",
        "una", "del", "da", "non", "le", "al", "lo", "dei", "ma", "ho",
        "come", "sulla", "gli", "ci", "sono", "quando", "anche", "più",
        "suo", "sulla", "delle", "questo", "dalla", "nel", "alla",
    },
}

# Muestra de texto a analizar (primeros N caracteres)
_SAMPLE_SIZE = 3_000


def detect_language(text: str) -> str:
    """
    Detecta el idioma predominante del texto.

    Returns:
        Nombre del idioma en español (ej: "español", "inglés", "francés").
        Por defecto "español" si no se puede determinar con confianza.
    """
    sample = text[:_SAMPLE_SIZE].lower()
    words = set(sample.split())

    scores = {
        lang: len(words & stopwords)
        for lang, stopwords in _STOPWORDS.items()
    }

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    # Si la puntuación es demasiado baja, no hay confianza suficiente
    if best_score < 3:
        return "español"

    return best_lang
