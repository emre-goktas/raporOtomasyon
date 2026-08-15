"""
ek.py — Türkçe ek uyumu: ünlü uyumu, ünsüz benzeşmesi, kesme işareti.

Gerçek raporda iki yerde hata var: `Can ÖRNEK'ya ait` (doğrusu `ÖRNEK'e`) —
önceki rapordan kalan Ctrl+H artığı, gözle kontrolden kaçmış. Kural
deterministik olduğu için bu hata kategorisi tamamen kapatılabilir.

Çekim son **seslinin** kalınlığına bakar, son harfin değil: "LTD.ŞTİ." noktayla
biter ama son sesli 'i'dir → "LTD.ŞTİ.'nin". Kısaltmalar harf harf okunduğu
için ayrıca istisna tablosu var: "A.Ş." → "a şe" diye okunur, son sesi 'e'dir,
harfe bakan bir kural "ş" görüp yanlış ek üretir.
"""
from __future__ import annotations

import re

_KALIN, _INCE = "aıouAIOU", "eiöüEİÖÜ"
_SESLI = _KALIN + _INCE
# Sert ünsüzle biten sözcükte ek sertleşir (ünsüz benzeşmesi): -de → -te
_SERT = "fstkçşhpFSTKÇŞHP"

# Harf harf okunan kısaltmalar: son SES neyse o. "A.Ş." = "a şe" → e
_KISALTMA = {
    "A.Ş.": "e", "AŞ": "e", "A.Ş": "e",
    "LTD.ŞTİ.": "i", "LTD.ŞTİ": "i", "STİ": "i",
    "T.C.": "e", "TC": "e",
    "SGK": "ka", "TL": "ra", "KDV": "ve", "OSB": "be",
}

# çekim: (kalın-düz, ince-düz, kalın-yuvarlak, ince-yuvarlak), sesliden sonraki tampon
_CEKIM = {
    "yonelme":  (("a", "e", "a", "e"), "y"),      # -e/-a hâli
    "belirtme": (("ı", "i", "u", "ü"), "y"),      # -i hâli
    "ilgi":     (("ın", "in", "un", "ün"), "n"),  # -in hâli
    "bulunma":  (("da", "de", "da", "de"), ""),   # -de hâli
    "ayrilma":  (("dan", "den", "dan", "den"), ""),
    "vasita":   (("la", "le", "la", "le"), "y"),  # ile
}
_SERTLESIR = {"bulunma", "ayrilma"}


def _son_ses(s: str) -> tuple[str, bool]:
    """(son sesli harf, sözcük sesliyle mi bitiyor) — kısaltmaları çözerek."""
    temiz = s.strip()
    for kisa, okunus in _KISALTMA.items():
        if temiz.upper().endswith(kisa.upper()):
            return okunus[-1], True         # kısaltmanın okunuşu hep sesliyle biter
    govde = temiz.rstrip(" .,;:!?\"'’”)")
    sesliler = [c for c in govde if c in _SESLI]
    if not sesliler:
        return "e", False                   # sesli yoksa ince varsay
    return sesliler[-1], (govde[-1:] in _SESLI)


# Python'da "İ".lower() iki karakter üretir (i + birleşen nokta), "I".lower()
# ise "i" verir — ikisi de Türkçe için yanlış. Küçültmeyi elle yapıyoruz.
_KUCULT = str.maketrans("AIİOÖUÜE", "aıioöuüe")


def _uyum(sesli: str) -> int:
    """0 kalın-düz · 1 ince-düz · 2 kalın-yuvarlak · 3 ince-yuvarlak"""
    s = sesli.translate(_KUCULT)
    if s in "aı":  return 0
    if s in "ei":  return 1
    if s in "ou":  return 2
    return 3                                 # ö, ü


def _sert_biter(s: str) -> bool:
    govde = s.strip().rstrip(" .,;:!?\"'’”)")
    return bool(govde) and govde[-1] in _SERT


def cekimle(sozcuk: str, cekim: str, *, ozel_ad: bool = True) -> str:
    """'ALİ VELİ' + 'yonelme' -> "ALİ VELİ'e"

    ozel_ad=True ise ek kesme işaretiyle ayrılır (özel adlarda zorunlu).
    Rapordaki her şey (kişi, şirket, işyeri) özel ad olduğu için varsayılan bu.
    """
    if not sozcuk or not sozcuk.strip():
        return sozcuk or ""
    if cekim not in _CEKIM:
        raise ValueError(f"bilinmeyen çekim {cekim!r} (geçerli: {sorted(_CEKIM)})")

    ekler, tampon = _CEKIM[cekim]
    sesli, sesliyle_bitiyor = _son_ses(sozcuk)
    ek = ekler[_uyum(sesli)]

    if sesliyle_bitiyor and tampon:
        ek = tampon + ek
    if cekim in _SERTLESIR and _sert_biter(sozcuk) and not sesliyle_bitiyor:
        ek = "t" + ek[1:]                    # -de → -te, -dan → -tan

    ayrac = "'" if ozel_ad else ""
    return f"{sozcuk.rstrip()}{ayrac}{ek}"


_YER_TUTUCU = re.compile(r"\{\{\s*([\wçğıöşüÇĞİÖŞÜ_.]+)\s*\|\s*(\w+)\s*\}\}")


def cekimleri_uygula(metin: str, veri: dict) -> tuple[str, list[str]]:
    """Metindeki {{alan|cekim}} kalıplarını çözer. (metin, uyarılar)"""
    uyarilar: list[str] = []

    def degistir(m):
        alan, cekim = m.group(1), m.group(2)
        if alan not in veri or veri[alan] in (None, ""):
            uyarilar.append(f"ek çekimi: {alan!r} alanı boş, yer tutucu olduğu gibi kaldı")
            return m.group(0)
        try:
            return cekimle(str(veri[alan]), cekim)
        except ValueError as e:
            uyarilar.append(f"ek çekimi: {e}")
            return m.group(0)

    return _YER_TUTUCU.sub(degistir, metin), uyarilar
