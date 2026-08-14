"""
gorev_emri.py — Belgenet'ten gelen görev emri PDF'ini ayrıştırır.

Metin tabanlı ve tek sayfa; koordinat kullanmıyoruz çünkü yazının gövdesi
işten işe uzayıp kısalıyor. Etiket ve çapa cümlelere göre okuyoruz.

Rapor bu belgeye şu biçimde atıf yapıyor:
    "Rehberlik ve Teftiş Ankara Grup Başkanlığının 21/11/2024 tarihli ve
     106535159 sayılı görevlendirmesi. (Ek:1)"
Bu yüzden hem tam sayı (E-...-124944128) hem de rapora giren kuyruk (124944128)
ayrı ayrı tutulur.
"""
import re

_RE_TARIH = re.compile(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b")
_RE_SAYI = re.compile(r"Say[ıi]\s*[\n:]\s*:?\s*(\S+)", re.IGNORECASE)
_RE_MUFETTIS = re.compile(r"Say[ıi]n\s+(.+?)\s*\n\s*M[üu]fetti[şs]", re.IGNORECASE)
_RE_GRUP = re.compile(r"(Rehberlik ve Teftiş\s+\S+\s+Grup Başkanlığı)", re.IGNORECASE)
_RE_ADET = re.compile(r"kay[ıi]tl[ıi]\s+(\d+)\s+adet", re.IGNORECASE)
_RE_SON_TARIH = re.compile(r"(\d{2}[./-]\d{2}[./-]\d{4})\s+tarihine kadar", re.IGNORECASE)
_RE_IMZA = re.compile(r"^\s*(.+?)\s*\n\s*Grup Ba[şs]kan[ıi]\s*$", re.IGNORECASE | re.MULTILINE)


def _iso(tarih: str | None) -> str | None:
    if not tarih:
        return None
    m = _RE_TARIH.search(tarih)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def oku(pdf_yolu) -> dict:
    """Görev emrinden künye alanlarını çıkarır. Bulunamayan alan None kalır
    ve 'uyarilar' listesinde adıyla raporlanır — sessizce boş geçilmez."""
    import pymupdf

    with pymupdf.open(pdf_yolu) as doc:
        metin = "\n".join(sayfa.get_text() for sayfa in doc)

    if not metin.strip():
        return {"kaynak_dosya": str(pdf_yolu),
                "uyarilar": ["görev emrinde metin katmanı yok — taranmış olabilir"]}

    sayi_tam = None
    m = _RE_SAYI.search(metin)
    if m:
        sayi_tam = m.group(1).strip().rstrip(".,;")

    # Rapora giren kısım son tireden sonraki sayı bloğu
    sayi_kisa = None
    if sayi_tam:
        parcalar = re.findall(r"\d+", sayi_tam)
        sayi_kisa = parcalar[-1] if parcalar else None

    m = _RE_MUFETTIS.search(metin)
    mufettis = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    m = _RE_GRUP.search(metin)
    grup = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    m = _RE_ADET.search(metin)
    adet = int(m.group(1)) if m else None

    m = _RE_IMZA.search(metin)
    imzalayan = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    m = _RE_SON_TARIH.search(metin)
    son_tarih = _iso(m.group(1)) if m else None

    # Belgenin kendi tarihi: son_tarih dışındaki ilk tarih
    tarih = None
    for t in _RE_TARIH.finditer(metin):
        aday = _iso(t.group(0))
        if aday and aday != son_tarih:
            tarih = aday
            break

    sonuc = {
        "tarih": tarih,
        "sayi": sayi_kisa,
        "sayi_tam": sayi_tam,
        "grup_baskanligi": grup,
        "mufettis": mufettis,
        "imzalayan": imzalayan,
        "denetim_adedi": adet,
        "son_tarih": son_tarih,
        "kaynak_dosya": str(pdf_yolu),
    }

    zorunlu = ("tarih", "sayi", "grup_baskanligi", "mufettis")
    sonuc["uyarilar"] = [f"görev emri: {a} okunamadı" for a in zorunlu if not sonuc.get(a)]
    return sonuc
