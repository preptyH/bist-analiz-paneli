"""Yahoo Finance veri erişimi + disk cache.

Ağ hatasında son başarılı veri (eski de olsa) diskten döner; o da yoksa boş sonuç döner.
Uygulama hiçbir durumda çökmez.
"""
from __future__ import annotations

import io
import json
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from .hesap import getiri, max_dusus, oranlar, temiz_kapanis, yillik_volatilite
from .semboller import sektor, yf_sembol

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
INFO_TTL = 6 * 3600     # temel oranlar: 6 saat
HIST_TTL = 30 * 60      # fiyat geçmişi: 30 dk


class Cache:
    def __init__(self, dizin: Path = CACHE_DIR):
        self.dizin = dizin

    def _yol(self, anahtar: str) -> Path:
        return self.dizin / f"{anahtar.replace('/', '_')}.json"

    def oku(self, anahtar: str) -> tuple[Any, float] | None:
        """JSON cache (pickle değil: dosyadan kod çalıştırma riski yok)."""
        try:
            kayit = json.loads(self._yol(anahtar).read_text(encoding="utf-8"))
            veri = kayit["veri"]
            if kayit.get("tur") == "df":
                veri = pd.read_json(io.StringIO(veri), orient="split")
            return veri, float(kayit["zaman"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def yaz(self, anahtar: str, veri) -> None:
        try:
            if isinstance(veri, pd.DataFrame):
                kayit = {"tur": "df", "veri": veri.to_json(orient="split", date_format="iso")}
            else:
                kayit = {"tur": "json", "veri": veri}
            kayit["zaman"] = time.time()
            self.dizin.mkdir(parents=True, exist_ok=True)
            self._yol(anahtar).write_text(json.dumps(kayit, default=str), encoding="utf-8")
        except (OSError, TypeError, ValueError):
            pass  # cache yazılamazsa sadece performans kaybı olur


def cacheli(cache: Cache, anahtar: str, ttl: float, getir, bos):
    """(veri, durum) döner. durum: 'taze' | 'cache' | 'eski-cache' | 'hata'."""
    kayit = cache.oku(anahtar)
    if kayit and time.time() - kayit[1] < ttl:
        return kayit[0], "cache"
    try:
        veri = getir()
        bos_mu = veri.empty if isinstance(veri, pd.DataFrame) else not veri
        if bos_mu:
            raise ValueError("boş veri")
        cache.yaz(anahtar, veri)
        return veri, "taze"
    except Exception:
        if kayit:
            return kayit[0], "eski-cache"
        return bos, "hata"


def _yf():
    import yfinance as yf
    return yf


def info_getir(kod: str, cache: Cache | None = None) -> tuple[dict, str]:
    cache = cache or Cache()
    return cacheli(cache, f"info_{kod}", INFO_TTL,
                   lambda: dict(_yf().Ticker(yf_sembol(kod)).info), {})


def gecmis_getir(kod: str, donem: str = "1y", cache: Cache | None = None) -> tuple[pd.DataFrame, str]:
    cache = cache or Cache()
    return cacheli(cache, f"hist_{kod}_{donem}", HIST_TTL,
                   lambda: _yf().Ticker(yf_sembol(kod)).history(period=donem, auto_adjust=True),
                   pd.DataFrame())


def satir(kod: str, cache: Cache | None = None) -> dict:
    info, d1 = info_getir(kod, cache)
    hist, d2 = gecmis_getir(kod, "1y", cache)
    kap = temiz_kapanis(hist)
    o = oranlar(info)
    if o["fiyat"] is None and not kap.empty:
        o["fiyat"] = round(float(kap.iloc[-1]), 2)
    durumlar = {d1, d2}
    return {
        "kod": kod, "ad": info.get("shortName") or kod, "sektor": sektor(kod), **o,
        "getiri_1a": getiri(kap, 21), "getiri_1y": getiri(kap, len(kap) - 1) if len(kap) > 1 else None,
        "volatilite": yillik_volatilite(kap), "max_dusus": max_dusus(kap),
        "durum": "hata" if "hata" in durumlar else ("eski-cache" if "eski-cache" in durumlar else "ok"),
    }


def tablo_getir(kodlar: list[str], cache: Cache | None = None, paralel: int = 8) -> pd.DataFrame:
    with ThreadPoolExecutor(max_workers=paralel) as ex:
        satirlar = list(ex.map(lambda k: satir(k, cache), kodlar))
    df = pd.DataFrame(satirlar)
    sayisal = ["fiyat", "fk", "pddd", "piyasa_degeri_mn", "temettu_verimi",
                "getiri_1a", "getiri_1y", "volatilite", "max_dusus"]
    df[sayisal] = df[sayisal].apply(pd.to_numeric, errors="coerce")
    return df[[k for k in df.columns if k != "not"] + ["not"]]
