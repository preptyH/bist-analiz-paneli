"""BIST Analiz Paneli — Streamlit arayüzü.  Çalıştır: streamlit run app.py"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bist import izleme
from bist.hesap import hareketli_ortalama, normalize, sektor_ozeti, sektore_gore_fark, temiz_kapanis
from bist.semboller import HISSELER
from bist.veri import gecmis_getir, tablo_getir

UYARI = ("⚠️ **Yatırım tavsiyesi değildir.** Bu panel yalnızca bilgilendirme amaçlıdır; "
         "AL/SAT önerisi içermez. Veriler Yahoo Finance'ten gecikmeli gelir, hatalı veya eksik olabilir.")
KOLON_ADI = {
    "kod": "Kod", "ad": "Şirket", "sektor": "Sektör", "fiyat": "Fiyat (TL)", "fk": "F/K",
    "pddd": "PD/DD", "piyasa_degeri_mn": "Piyasa Değeri (mn TL)", "temettu_verimi": "Temettü %",
    "getiri_1a": "1A Getiri %", "getiri_1y": "1Y Getiri %", "volatilite": "Yıllık Volatilite %",
    "max_dusus": "Maks. Düşüş %", "durum": "Veri", "not": "Not",
}

st.set_page_config(page_title="BIST Analiz Paneli", page_icon="📊", layout="wide")
st.title("📊 BIST Analiz Paneli")
st.warning(UYARI)


@st.cache_data(ttl=1800, show_spinner="Veriler çekiliyor (ilk açılış ~30 sn)...")
def tablo(kodlar: tuple[str, ...]) -> pd.DataFrame:
    return tablo_getir(list(kodlar))


@st.cache_data(ttl=1800)
def gecmis(kod: str, donem: str):
    return gecmis_getir(kod, donem)


if "izleme" not in st.session_state:
    st.session_state.izleme = izleme.yukle()

with st.sidebar:
    st.header("Filtre")
    sektorler = sorted(set(HISSELER.values()))
    secili_sektor = st.multiselect("Sektör", sektorler, default=sektorler)
    sadece_izleme = st.checkbox("Sadece izleme listesi")
    if st.button("Verileri yenile"):
        st.cache_data.clear()
    st.caption("Kaynak: Yahoo Finance (yfinance). Ağ hatasında son kayıtlı veri gösterilir.")

df = tablo(tuple(HISSELER))
hatali = int((df["durum"] == "hata").sum())
eski = int((df["durum"] == "eski-cache").sum())
if hatali:
    st.error(f"{hatali} hisse için veri alınamadı (ağ/kaynak hatası). Diğerleri gösteriliyor.")
if eski:
    st.info(f"{eski} hisse için güncel veri alınamadı; son kayıtlı veri gösteriliyor.")

gorunen = df[df["sektor"].isin(secili_sektor)]
if sadece_izleme:
    gorunen = gorunen[gorunen["kod"].isin(st.session_state.izleme)]

sek_tablo, sek_hisse, sek_sektor, sek_izleme = st.tabs(
    ["📋 Tablo", "📈 Hisse", "🏭 Sektör karşılaştırma", "⭐ İzleme listesi"])

with sek_tablo:
    st.dataframe(gorunen.rename(columns=KOLON_ADI), hide_index=True, use_container_width=True,
                 height=560, column_config={"Piyasa Değeri (mn TL)": st.column_config.NumberColumn(format="%,.0f")})
    st.caption("F/K: negatif kârda boş bırakılır. Temettü %: son 12 ay. Boş hücre = kaynakta veri yok.")

with sek_hisse:
    c1, c2 = st.columns([2, 1])
    kod = c1.selectbox("Hisse", list(HISSELER), format_func=lambda k: f"{k} — {HISSELER[k]}")
    donem = c2.selectbox("Dönem", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    hist, durum = gecmis(kod, donem)
    if hist.empty:
        st.error("Fiyat geçmişi alınamadı (ağ hatası ve kayıtlı veri yok).")
    else:
        if durum == "eski-cache":
            st.info("Güncel veri alınamadı; son kayıtlı veri gösteriliyor.")
        h = hist.dropna(subset=["Close"])
        kap = temiz_kapanis(h)
        fig = go.Figure([go.Candlestick(x=h.index, open=h["Open"], high=h["High"], low=h["Low"],
                                        close=h["Close"], name=kod)])
        for p, renk in [(50, "#1f77b4"), (200, "#ff7f0e")]:
            fig.add_scatter(x=kap.index, y=hareketli_ortalama(kap, p), name=f"HO{p}",
                            line={"width": 1.5, "color": renk})
        fig.update_layout(height=480, xaxis_rangeslider_visible=False, margin={"t": 20, "b": 10})
        st.plotly_chart(fig, use_container_width=True)
        satir = df[df["kod"] == kod].iloc[0]
        m = st.columns(5)
        for kutu, alan in zip(m, ["fiyat", "fk", "pddd", "temettu_verimi", "volatilite"]):
            deger = satir[alan]
            kutu.metric(KOLON_ADI[alan], "—" if pd.isna(deger) else f"{deger:,.2f}")

with sek_sektor:
    st.subheader("Sektör medyanları")
    st.dataframe(sektor_ozeti(df).rename(columns=KOLON_ADI | {"hisse_sayisi": "Hisse"}),
                 use_container_width=True)
    secim = st.selectbox("Sektör içi karşılaştırma", sorted(set(HISSELER.values())))
    alt = df[df["sektor"] == secim].copy()
    alt["F/K sektöre göre %"] = sektore_gore_fark(alt, "fk")
    alt["PD/DD sektöre göre %"] = sektore_gore_fark(alt, "pddd")
    st.dataframe(alt[["kod", "ad", "fk", "pddd", "temettu_verimi", "getiri_1y",
                      "F/K sektöre göre %", "PD/DD sektöre göre %"]].rename(columns=KOLON_ADI),
                 hide_index=True, use_container_width=True)
    seriler = {}
    for k in alt["kod"]:
        hk, _ = gecmis(k, "1y")
        if not hk.empty:
            seriler[k] = temiz_kapanis(hk).tz_localize(None) if temiz_kapanis(hk).index.tz else temiz_kapanis(hk)
    norm = normalize(seriler)
    if not norm.empty:
        st.caption("1 yıllık performans (başlangıç = 100)")
        st.line_chart(norm)

with sek_izleme:
    secim = st.multiselect("İzlenen hisseler", list(HISSELER), default=st.session_state.izleme)
    if st.button("Listeyi kaydet"):
        st.session_state.izleme = izleme.kaydet(secim)
        st.success("Kaydedildi.")
    liste = df[df["kod"].isin(st.session_state.izleme)]
    if liste.empty:
        st.info("İzleme listeniz boş. Hisse seçip kaydedin.")
    else:
        st.dataframe(liste.rename(columns=KOLON_ADI), hide_index=True, use_container_width=True)

st.caption("Bu uygulama yatırım tavsiyesi vermez. Kararlarınızı lisanslı bir danışmana danışarak verin.")
