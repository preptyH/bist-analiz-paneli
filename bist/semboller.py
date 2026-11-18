"""İzlenen BIST hisseleri ve sektörleri (statik liste; ağ olmadan da sektör bilgisi mevcuttur)."""

HISSELER: dict[str, str] = {
    # Bankacılık
    "AKBNK": "Bankacılık", "GARAN": "Bankacılık", "ISCTR": "Bankacılık",
    "YKBNK": "Bankacılık", "HALKB": "Bankacılık", "VAKBN": "Bankacılık",
    # Holding
    "KCHOL": "Holding", "SAHOL": "Holding", "DOHOL": "Holding", "AGHOL": "Holding",
    # Ulaştırma
    "THYAO": "Ulaştırma", "PGSUS": "Ulaştırma", "TAVHL": "Ulaştırma",
    # Sanayi / Demir-çelik
    "EREGL": "Demir-Çelik", "KRDMD": "Demir-Çelik", "ISDMR": "Demir-Çelik",
    # Enerji / Petrokimya
    "TUPRS": "Enerji", "PETKM": "Enerji", "AKSEN": "Enerji", "ENJSA": "Enerji",
    # Otomotiv
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "DOAS": "Otomotiv",
    # Perakende / Gıda
    "BIMAS": "Perakende", "MGROS": "Perakende", "SOKM": "Perakende", "ULKER": "Gıda", "CCOLA": "Gıda",
    # Telekom / Teknoloji
    "TCELL": "Telekom", "TTKOM": "Telekom", "ASELS": "Savunma",
    # Cam / Kimya / İnşaat
    "SISE": "Cam", "SASA": "Kimya", "ENKAI": "İnşaat",
}


def yf_sembol(kod: str) -> str:
    """BIST kodunu Yahoo Finance sembolüne çevirir: THYAO -> THYAO.IS"""
    kod = kod.strip().upper()
    return kod if kod.endswith(".IS") else f"{kod}.IS"


def sektor(kod: str) -> str:
    return HISSELER.get(kod.strip().upper().removesuffix(".IS"), "Diğer")
