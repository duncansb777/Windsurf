from typing import Dict


def lookup_code(text: str, vocab: str) -> Dict[str, str]:
    return {"system": vocab, "verification_required": True}
