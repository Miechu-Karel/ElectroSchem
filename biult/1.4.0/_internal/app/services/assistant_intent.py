"""Conservative question shortcut; explicit drawing requests always win."""
import re


def explanation_only(prompt):
    text=prompt.strip().casefold()
    if re.search(r'\b(narysuj|zrób|zrob|stwórz|stworz|dodaj|usuń|usun|przesuń|obróć|popraw|draw|create|add|delete|move|rotate|build|fix)\b',text): return False
    return bool(re.match(r'(jak\b|dlaczego\b|czemu\b|co\b|czy\b|wyjaśnij\b|wytłumacz\b|what\b|why\b|how\b|explain\b|is\b|does\b|can\b)',text))
