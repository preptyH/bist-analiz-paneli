import math

import pandas as pd
import pytest

from bist import izleme
from bist.hesap import (getiri, hareketli_ortalama, max_dusus, normalize, oranlar, sektor_ozeti,
                        sektore_gore_fark, temettu_verimi, temiz_kapanis, yillik_volatilite)
from bist.semboller import HISSELER, sektor, yf_sembol
from bist.veri import Cache, cacheli


def seri(*v):
    return pd.Series(v, dtype=float, index=pd.date_range("2025-01-01", periods=len(v)))


# --- oranlar ---
def test_oranlar_dogrudan():
    o = oranlar({"regularMarketPrice": 100, "trailingPE": 8.456, "priceToBook": 1.234,
                 "marketCap": 2_500_000_000, "dividendYield": 3.5})
    assert o == {"fiyat": 100.0, "fk": 8.46, "pddd": 1.23, "piyasa_degeri_mn": 2500.0,
                 "temettu_verimi": 3.5, "not": ""}


def test_fk_eps_ile_hesaplanir():
    assert oranlar({"regularMarketPrice": 50, "trailingEps": 5})["fk"] == 10.0


def test_negatif_kazancta_fk_bos():
    assert oranlar({"regularMarketPrice": 50, "trailingEps": -2})["fk"] is None
    assert oranlar({"regularMarketPrice": 50, "trailingPE": -4})["fk"] is None


def test_pddd_defter_degeri_ile():
    assert oranlar({"currentPrice": 30, "bookValue": 10})["pddd"] == 3.0


def test_eksik_ve_bozuk_veri_none():
    o = oranlar({"trailingPE": "NaN", "priceToBook": float("inf"), "marketCap": None})
    assert o == {"fiyat": None, "fk": None, "pddd": None, "piyasa_degeri_mn": None,
                 "temettu_verimi": None, "not": ""}


def test_doviz_raporlayan_sirkette_oranlar_bos():
    # Fiyat TRY, bilanço USD: Yahoo'nun F/K ve PD/DD değeri para birimi karışık -> güvenilmez
    o = oranlar({"currentPrice": 80, "currency": "TRY", "financialCurrency": "USD",
                 "trailingPE": 15.4, "priceToBook": 53.2, "marketCap": 1e9, "dividendYield": 4.6})
    assert o["fk"] is None and o["pddd"] is None
    assert o["piyasa_degeri_mn"] == 1000.0 and o["temettu_verimi"] == 4.6
    assert "USD" in o["not"]


def test_ayni_para_biriminde_oranlar_korunur():
    o = oranlar({"currentPrice": 10, "currency": "TRY", "financialCurrency": "TRY",
                 "trailingPE": 5, "priceToBook": 1})
    assert o["fk"] == 5 and o["pddd"] == 1 and o["not"] == ""


@pytest.mark.parametrize("info,beklenen", [
    ({"dividendYield": 0.13}, 0.13),           # yfinance 1.x: her zaman yüzde
    ({"dividendYield": 4.2}, 4.2),
    ({"dividendYield": 0.0}, 0.0),
    ({"trailingAnnualDividendYield": 0.05}, 5.0),
    ({}, None),
])
def test_temettu_verimi_birim(info, beklenen):
    assert temettu_verimi(info) == beklenen


# --- fiyat serisi ---
def test_getiri():
    s = seri(100, 110, 121)
    assert getiri(s, 1) == 10.0 and getiri(s, 2) == 21.0


def test_getiri_yetersiz_veri():
    assert getiri(seri(100, 110), 5) is None and getiri(seri(100), 0) is None


def test_volatilite_sabit_fiyat_sifir():
    assert yillik_volatilite(seri(10, 10, 10, 10)) == 0.0


def test_volatilite_bilinen_deger():
    s = seri(100, 101, 100, 101, 100)
    g = s.pct_change().dropna()
    assert yillik_volatilite(s) == round(g.std() * math.sqrt(252) * 100, 2)


def test_volatilite_yetersiz():
    assert yillik_volatilite(seri(10, 11)) is None


def test_max_dusus():
    assert max_dusus(seri(100, 120, 60, 90, 130)) == -50.0
    assert max_dusus(seri(1, 2, 3)) == 0.0
    assert max_dusus(pd.Series(dtype=float)) is None


def test_hareketli_ortalama():
    ho = hareketli_ortalama(seri(1, 2, 3, 4), 2)
    assert ho.isna().iloc[0] and list(ho.iloc[1:]) == [1.5, 2.5, 3.5]


def test_temiz_kapanis_nan_atar():
    hist = pd.DataFrame({"Close": [1.0, float("nan"), 3.0]})
    assert list(temiz_kapanis(hist)) == [1.0, 3.0]
    assert temiz_kapanis(pd.DataFrame()).empty


def test_normalize_100den_baslar():
    n = normalize({"A": seri(10, 20), "B": seri(50, 25)})
    assert list(n.iloc[0]) == [100.0, 100.0] and list(n.iloc[1]) == [200.0, 50.0]


# --- sektör ---
def _tablo():
    return pd.DataFrame({"kod": ["A", "B", "C", "D"], "sektor": ["X", "X", "X", "Y"],
                         "fk": [5.0, 10.0, 100.0, 8.0], "pddd": [1.0, 2.0, 3.0, 4.0],
                         "temettu_verimi": [1.0, None, 3.0, 0.0], "getiri_1a": [1, 2, 3, 4]})


def test_sektor_ozeti_medyan():
    oz = sektor_ozeti(_tablo())
    assert oz.loc["X", "fk"] == 10.0 and oz.loc["X", "hisse_sayisi"] == 3
    assert oz.loc["X", "temettu_verimi"] == 2.0  # NaN atlanır


def test_sektore_gore_fark():
    f = sektore_gore_fark(_tablo(), "fk")
    assert list(f) == [-50.0, 0.0, 900.0, 0.0]


# --- semboller ---
def test_semboller():
    assert yf_sembol("thyao") == "THYAO.IS" and yf_sembol("THYAO.IS") == "THYAO.IS"
    assert sektor("garan.is") == "Bankacılık" and sektor("XXXXX") == "Diğer"
    assert len(HISSELER) >= 30


# --- cache / ağ hatası ---
def test_cache_df_gidis_donus(tmp_path):
    c = Cache(tmp_path)
    df = pd.DataFrame({"Close": [1.5, 2.5]}, index=pd.date_range("2025-01-01", periods=2))
    c.yaz("x", df)
    okunan, _ = c.oku("x")
    assert list(okunan["Close"]) == [1.5, 2.5]


def test_ag_hatasinda_eski_cache_doner(tmp_path):
    c = Cache(tmp_path)
    c.yaz("k", {"a": 1})

    def patla():
        raise ConnectionError("ağ yok")
    veri, durum = cacheli(c, "k", ttl=0, getir=patla, bos={})
    assert veri == {"a": 1} and durum == "eski-cache"


def test_ag_hatasi_cache_yoksa_bos(tmp_path):
    veri, durum = cacheli(Cache(tmp_path), "yok", 60, lambda: 1 / 0, pd.DataFrame())
    assert veri.empty and durum == "hata"


def test_taze_cache_ag_cagirmaz(tmp_path):
    c = Cache(tmp_path)
    c.yaz("k", {"a": 1})
    veri, durum = cacheli(c, "k", 3600, lambda: pytest.fail("ağa gidilmemeli"), {})
    assert durum == "cache"


def test_bos_yanit_hata_sayilir(tmp_path):
    veri, durum = cacheli(Cache(tmp_path), "k", 60, lambda: pd.DataFrame(), pd.DataFrame())
    assert durum == "hata"


def test_bozuk_cache_dosyasi(tmp_path):
    (tmp_path / "k.json").write_text("bozuk{", encoding="utf-8")
    assert Cache(tmp_path).oku("k") is None


# --- izleme listesi ---
def test_izleme_kaydet_yukle(tmp_path):
    yol = tmp_path / "iz.json"
    assert izleme.yukle(yol) == []
    izleme.kaydet(["thyao", "GARAN", "THYAO", " "], yol)
    assert izleme.yukle(yol) == ["GARAN", "THYAO"]
