import re
import unicodedata


def slugify(value: str, max_length: int = 80) -> str:
    """ASCII kebab-case slug. Diacritics are stripped (Ọbalende becomes obalende)."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:max_length].strip("-")
    return slug or "spot"
