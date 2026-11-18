"""Çekirdek hesaplar: saf fonksiyonlar, ağ erişimi yok (test edilebilir)."""
from __future__ import annotations

import math

import pandas as pd

ISLEM_GUNU = 252


def _sayi(x) -> float | None:
    """Sayıya çevir; None, NaN, sonsuz veya sayı olmayan değerler için None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def temettu_verimi(info: dict) -> float | None:
    """Temettü verimini YÜZDE olarak döner.

    yfinance >= 0.2.54 (1.x dahil) `dividendYield` alanını YÜZDE verir (0.13 = %0.13).
    `trailingAnnualDividendYield` ise orandır (0.05 = %5); yedek olarak kullanılır.
    """
    dy = _sayi(info.get("dividendYield"))
    if dy is not None:
        return round(dy, 2)
    dy = _sayi(info.get("trailingAnnualDividendYield"))
    return None if dy is None else round(dy * 100, 2)


def oranlar(info: dict) -> dict:
    """Ham yfinance info sözlüğünden tabloya girecek temel oranlar.

    F/K ve PD/DD verilmemişse fiyat/EPS ve fiyat/defter değeri ile hesaplanır.
    Negatif kazançta F/K anlamsızdır -> None.
    Şirket bilançosunu fiyattan farklı para biriminde raporluyorsa (ör. TL fiyat, USD bilanço)
    Yahoo'nun F/K ve PD/DD değerleri karışık birimle hesaplanır; bunlar boş bırakılıp not düşülür.
    """
    fiyat_pb, bilanco_pb = info.get("currency"), info.get("financialCurrency")
    doviz_uyumsuz = bool(fiyat_pb and bilanco_pb and fiyat_pb != bilanco_pb)
    fiyat = _sayi(info.get("regularMarketPrice") or info.get("currentPrice")
                  or info.get("previousClose"))
    fk = _sayi(info.get("trailingPE"))
    if fk is None and fiyat:
        eps = _sayi(info.get("trailingEps"))
        fk = round(fiyat / eps, 2) if eps and eps > 0 else None
    if fk is not None and fk <= 0:
        fk = None
    pddd = _sayi(info.get("priceToBook"))
    if pddd is None and fiyat:
        bv = _sayi(info.get("bookValue"))
        pddd = round(fiyat / bv, 2) if bv and bv > 0 else None
    if doviz_uyumsuz:
        fk = pddd = None
    pd_deger = _sayi(info.get("marketCap"))
    return {
        "fiyat": fiyat,
        "fk": round(fk, 2) if fk is not None else None,
        "pddd": round(pddd, 2) if pddd is not None else None,
        "piyasa_degeri_mn": round(pd_deger / 1e6, 1) if pd_deger else None,
        "temettu_verimi": temettu_verimi(info),
        "not": f"Bilanço {bilanco_pb}: F/K, PD/DD gösterilmiyor" if doviz_uyumsuz else "",
    }


def temiz_kapanis(hist: pd.DataFrame) -> pd.Series:
    """Geçmiş verisinden boş (NaN) kapanışları atılmış kapanış serisi."""
    if hist is None or hist.empty or "Close" not in hist:
        return pd.Series(dtype=float)
    return hist["Close"].dropna()


def getiri(kapanis: pd.Series, gun: int) -> float | None:
    """Son `gun` işlem günündeki yüzde getiri. Yetersiz veri -> None."""
    if len(kapanis) <= gun or gun <= 0:
        return None
    once = float(kapanis.iloc[-gun - 1])
    if once == 0:
        return None
    return round((float(kapanis.iloc[-1]) / once - 1) * 100, 2)


def yillik_volatilite(kapanis: pd.Series) -> float | None:
    """Günlük getirilerin yıllıklandırılmış standart sapması (%)."""
    g = kapanis.pct_change().dropna()
    if len(g) < 2:
        return None
    return round(float(g.std() * math.sqrt(ISLEM_GUNU) * 100), 2)


def max_dusus(kapanis: pd.Series) -> float | None:
    """Zirveden en büyük düşüş (%, negatif sayı)."""
    if kapanis.empty:
        return None
    zirve = kapanis.cummax()
    return round(float(((kapanis / zirve) - 1).min() * 100), 2)


def hareketli_ortalama(kapanis: pd.Series, pencere: int) -> pd.Series:
    return kapanis.rolling(pencere, min_periods=pencere).mean()


def normalize(kapanislar: dict[str, pd.Series]) -> pd.DataFrame:
    """Karşılaştırma için her seriyi ilk ortak günde 100'e eşitler."""
    df = pd.DataFrame(kapanislar).dropna()
    if df.empty:
        return df
    return df / df.iloc[0] * 100


def sektor_ozeti(tablo: pd.DataFrame) -> pd.DataFrame:
    """Sektör bazında medyan oranlar ve hisse sayısı (medyan: aykırı değerlere dayanıklı)."""
    kolonlar = ["fk", "pddd", "temettu_verimi", "getiri_1a"]
    mevcut = [k for k in kolonlar if k in tablo]
    ozet = tablo.groupby("sektor")[mevcut].median(numeric_only=True).round(2)
    ozet.insert(0, "hisse_sayisi", tablo.groupby("sektor").size())
    return ozet.sort_values("hisse_sayisi", ascending=False)


def sektore_gore_fark(tablo: pd.DataFrame, kolon: str) -> pd.Series:
    """Her hissenin `kolon` değerinin kendi sektör medyanına göre yüzde farkı."""
    medyan = tablo.groupby("sektor")[kolon].transform("median")
    return ((tablo[kolon] / medyan - 1) * 100).round(1)
