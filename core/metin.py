"""
metin.py — Metin normalizasyonu: tarih, sayı, TC, Türkçe harf katlama.

Eski projedeki `src/utils.py`'ın bilgisi buraya taşındı; davranış iki yerde
bilerek değiştirildi:

  * Tarih çıktısı `gg/aa/yyyy` değil **ISO** (`2024-03-15`) — case.json'ın
    her yerinde ISO kullanılıyor, biçim çevrimi tek noktada kalsın.
  * Tarih artık **takvim olarak doğrulanıyor**. Eski regex `32.13.2024`'ü
    memnuniyetle kabul ediyordu; sessizce yanlış dönmek, hiç dönmemekten kötü.

Sayı ayracı için tek bir kural yok, çünkü gerçek belgelerde ikisi de var:
hizmet dökümünde `204,000,000.00` (ABD biçimi), raporun başka tablosunda
`20.002,50` (TR biçimi). Belirsiz kaldığında tahmin edilmez, uyarı üretilir.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

# gg.aa.yyyy | gg/aa/yyyy | gg-aa-yyyy — ayraçtan sonra tam 4 basamak.
# "03-91953272" gibi belge sayılarına takılmamak için sağda rakam yasak.
_RE_TARIH = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b(?!\d)")
_RE_TARIH_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b(?!\d)")

_TR_KATLAMA = str.maketrans({
    "İ": "I", "ı": "i", "Ş": "S", "ş": "s", "Ğ": "G", "ğ": "g",
    "Ü": "U", "ü": "u", "Ö": "O", "ö": "o", "Ç": "C", "ç": "c",
})


# --------------------------------------------------------------------------
# Türkçe harf katlama
# --------------------------------------------------------------------------

def sadelestir(s: str) -> str:
    """Türkçe harfleri ASCII'ye katlar, BÜYÜK/küçük ayrımını korur.
    Dosya/klasör adı üretmek için."""
    s = (s or "").translate(_TR_KATLAMA)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def anahtarla(s: str) -> str:
    """Etiket eşleştirme anahtarı: harf katla, küçült, boşlukları tekille.

    'İşyeri Ünvanı' ve 'ISYERI  UNVANI' aynı anahtara düşsün — kurum
    çıktıları aynı alanı belgeden belgeye farklı yazıyor.
    """
    s = (s or "").replace("I", "i").replace("İ", "i").replace("ı", "i")
    s = sadelestir(s).lower()
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# Tarih
# --------------------------------------------------------------------------

def tarih_iso(ham: str | None) -> tuple[str | None, str | None]:
    """Tek bir tarih dizesini ISO'ya çevirir. (deger, uyari) döner."""
    if not ham or not str(ham).strip():
        return None, None
    ham = str(ham).strip()

    m = _RE_TARIH_ISO.fullmatch(ham)
    if m:
        y, a, g = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _RE_TARIH.search(ham)
        if not m:
            return None, f"tarih tanınmadı: {ham!r}"
        g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))

    try:
        return date(y, a, g).isoformat(), None
    except ValueError:
        return None, f"takvimde olmayan tarih: {ham!r}"


def tarih_bul(metin: str | None, *, mod: str = "ilk") -> tuple[str | None, str | None]:
    """Metnin içinden tarih çıkarır. mod: 'ilk' | 'son'. (ISO, uyari) döner."""
    if not metin:
        return None, None
    bulunanlar = _RE_TARIH.findall(metin) or [
        (g, a, y) for y, a, g in _RE_TARIH_ISO.findall(metin)
    ]
    if not bulunanlar:
        return None, None
    g, a, y = bulunanlar[0] if mod == "ilk" else bulunanlar[-1]
    return tarih_iso(f"{g}.{a}.{y}")


def tarihleri_bul(metin: str | None) -> list[str]:
    """Metindeki takvimde geçerli tüm tarihleri sırayla ISO olarak döndürür."""
    if not metin:
        return []
    out = []
    for g, a, y in _RE_TARIH.findall(metin):
        iso, uyari = tarih_iso(f"{g}.{a}.{y}")
        if iso and not uyari:
            out.append(iso)
    return out


# --------------------------------------------------------------------------
# Sayı
# --------------------------------------------------------------------------

def ondalik(ham: str | None, *, alan: str = "sayı") -> tuple[Decimal | None, str | None]:
    """'204,000,000.00' ve '20.002,50' — ikisini de çözer. (Decimal, uyari).

    Kural: iki ayraç da varsa **sondaki** ondalık ayracıdır. Tek tür ayraç
    birden çok kez geçiyorsa binliktir. Tek kez geçiyorsa ardından gelen
    basamak sayısına bakılır; 3 basamakta karar verilemez (`1.234` hem 1234
    hem 1,234 olabilir) — binlik varsayılır ama uyarı üretilir.
    """
    if ham is None or str(ham).strip() == "":
        return None, None

    s = re.sub(r"[^\d.,-]", "", str(ham).strip())
    if not s or not re.search(r"\d", s):
        return None, f"{alan}: sayı bulunamadı ({ham!r})"

    eksi = s.startswith("-")
    s = s.lstrip("-")
    uyari = None

    nokta, virgul = s.count("."), s.count(",")

    if nokta and virgul:
        ondalik_ayrac = "." if s.rfind(".") > s.rfind(",") else ","
        binlik = "," if ondalik_ayrac == "." else "."
        s = s.replace(binlik, "").replace(ondalik_ayrac, ".")
    elif nokta or virgul:
        ayrac = "." if nokta else ","
        adet = nokta or virgul
        kuyruk = len(s) - s.rfind(ayrac) - 1
        if adet > 1 or kuyruk == 3:
            if adet == 1 and kuyruk == 3:
                uyari = (f"{alan}: '{ham}' — tek ayraç ve 3 basamak, binlik mi "
                         f"ondalık mı belirsiz; binlik varsayıldı")
            s = s.replace(ayrac, "")
        else:
            s = s.replace(ayrac, ".")

    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, f"{alan}: sayıya çevrilemedi ({ham!r})"
    return (-d if eksi else d), uyari


def rakamlar(ham: str | None) -> str:
    """Yalnızca rakamları bitiştirir: '2 0000 01' -> '2000001'."""
    return re.sub(r"\D", "", ham or "")


# --------------------------------------------------------------------------
# TC kimlik numarası
# --------------------------------------------------------------------------

def tc_gecerli(tc: str | None) -> bool:
    """TC kimlik numarasının kendi sağlama algoritmasıyla doğrular.

    Excel'den gelen TC'lere körü körüne güvenilmiyor (kural 6) — bu sağlama
    bedava bir çapraz kontrol: 10. hane tek/çift hane toplamlarından,
    11. hane ilk on hanenin toplamından üretilir.
    """
    t = rakamlar(tc)
    if len(t) != 11 or t[0] == "0":
        return False
    d = [int(c) for c in t]
    tek = sum(d[0:9:2])      # 1., 3., 5., 7., 9. haneler
    cift = sum(d[1:8:2])     # 2., 4., 6., 8. haneler
    if (tek * 7 - cift) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]
