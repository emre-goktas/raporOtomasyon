"""
kosul.py — Rapor bloklarının koşullarını case.json'a karşı değerlendirir.

Koşullar YAML'da Türkçe yazılır ("işyeri tescilli", "iş kazası bildirim formu
yok"). Burada her koşul bir yükleme çevrilir.

**Belirlenemeyen koşul False değildir.** Veriden karar veremiyorsak `None`
döner ve uyarı üretilir — blok basılmaz ama sessizce de geçilmez. Aksi hâlde
"tanık var" koşulunu çıkaramadığımızda blok kendiliğinden düşer ve raporda
eksik olduğu kimseye görünmez (kural 1).
"""
from __future__ import annotations

import re

from core.metin import anahtarla

# YAML'daki belge adı -> belgeler[] içindeki tür
_BELGE_ADI = {
    "ise giris bildirgesi": "ise_giris_bildirgesi",
    "isten ayrilis bildirgesi": "isten_ayrilis_bildirgesi",
    "isyeri tescil": "isyeri_tescil",
    "hizmet dokumu": "hizmet_dokumu",
    "denetim gerekcesi": "denetim_gerekcesi",
    "unite karari": "unite_karari",
    "is kazasi bildirim formu": "kaza_bildirim_formu",
    "olay yeri inceleme raporu": "olay_yeri_inceleme",
    "ifade tutanagi": "ifade_tutanagi",
    "bilirkisi raporu": "bilirkisi_raporu",
    "savcilik yazisi": "savcilik_yazisi",
}


def _belge_var(baglam: dict, tur: str) -> bool:
    return any(b.get("tur") == tur for b in baglam.get("belgeler", []))


def degerlendir(kosul: str, baglam: dict) -> tuple[bool | None, str | None]:
    """(sonuç, uyarı). Sonuç None ise koşul veriden çıkarılamadı."""
    k = anahtarla(kosul)
    case = baglam.get("case", {})
    isveren = case.get("isveren") or {}

    if k in ("her zaman", "daima", ""):
        return True, None

    # ── işyeri tescil durumu ──
    if k == "isyeri tescilli":
        return bool(isveren.get("tescilli")), None
    if k == "isyeri tescilsiz":
        return not isveren.get("tescilli"), None

    # ── alt işveren ──
    if k in ("alt isveren var", "alt isveren yok"):
        alt = case.get("diger_isveren") or baglam.get("alt_isverenler") or []
        var = bool(alt)
        return (var if k.endswith("var") else not var), None

    # ── kazalı sayısı ──
    if k.startswith("kazali"):
        n = len(case.get("sigortalilar") or [])
        if not n:
            return None, "koşul: sigortalı sayısı bilinmiyor"
        if "birden fazla" in k:
            return n > 1, None
        m = re.search(r"\d+", k)
        return (n == int(m.group())) if m else (n == 1), None

    # ── olayın niteliği ──
    if k in ("olay olumlu", "olay yaralanmali"):
        dg = baglam.get("alanlar", {}).get("denetim_gerekcesi", {})
        olum = dg.get("olum_tarihi") or (anahtarla(dg.get("olay_turu") or "").find("olum") >= 0)
        if not dg:
            return None, "koşul: olayın ölümlü olup olmadığı belirlenemedi (denetim gerekçesi yok)"
        return (bool(olum) if k.endswith("olumlu") else not olum), None

    # ── belge var / yok ──
    m = re.match(r"^(.*?)\s+(var|yok)$", k)
    if m:
        ad, hal = m.group(1).strip(), m.group(2)
        tur = _BELGE_ADI.get(ad)
        if tur is None:
            return None, f"koşul: {kosul!r} — '{ad}' diye bir belge türü tanımlı değil"
        var = _belge_var(baglam, tur)
        return (var if hal == "var" else not var), None

    # ── tarih mantığı ──
    if "bildirgesi kaza tarihinden" in k:
        a = baglam.get("alanlar", {})
        giris = (a.get("ise_giris_bildirgesi") or {}).get("ise_baslama_tarihi")
        kaza = (a.get("denetim_gerekcesi") or {}).get("kaza_tarihi")
        if not (giris and kaza):
            return None, "koşul: işe giriş ya da kaza tarihi yok, karşılaştırılamadı"
        return (giris < kaza) if "once" in k else (giris > kaza), None

    return None, f"koşul: {kosul!r} tanınmadı — core/rapor/kosul.py'a eklenmeli"
