"""İzleme listesi: yerel JSON dosyasında saklanır (repoya girmez)."""
from __future__ import annotations

import json
from pathlib import Path

VARSAYILAN = Path(__file__).resolve().parent.parent / "izleme_listesi.json"


def yukle(yol: Path = VARSAYILAN) -> list[str]:
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(veri, list):
        return []
    return sorted({str(k).strip().upper() for k in veri if str(k).strip()})


def kaydet(kodlar, yol: Path = VARSAYILAN) -> list[str]:
    temiz = sorted({str(k).strip().upper() for k in kodlar if str(k).strip()})
    yol.write_text(json.dumps(temiz, ensure_ascii=False, indent=2), encoding="utf-8")
    return temiz
