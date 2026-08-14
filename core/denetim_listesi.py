"""
denetim_listesi.py — Görev emrine ekli DenetimListesi.xlsx'i iş kayıtlarına çevirir.

Excel'in bozduğu iki alan (Yazı Tarihi seri numara, Yazı Sayısı bilimsel
gösterim) onarim.py üzerinden geri kazanılır; onarım şüpheliyse uyarı üretilir
ve iş kaydının "uyarilar" listesine düşer.

Kolon düzeni başlık satırından okunur, sabit indeks varsayılmaz — kurum
sisteminin kolon sırasını değiştirmesi sessizce yanlış veri üretmesin.
"""
import re

from core.metin import anahtarla
from core.onarim import seri_tarih, uzun_sayi

# Başlıklar hücre içinde satır kırılmasıyla geliyor: "Denetim\nNo"
_BASLIKLAR = {
    "denetim no": "denetim_no",
    "yazi tarihi": "yazi_tarihi",
    "yazi sayisi": "yazi_sayisi",
    "denetim alani": "denetim_alani",
    "statusu": "statu",
    "illeri": "il",
    "sigortali bilgisi": "sigortali_ham",
    "tescilli isveren bilgisi": "tescilli_isveren_ham",
    "diger isveren bilgisi": "diger_isveren_ham",
    "havale edilen mufettis": "mufettis",
}

_RE_SIGORTALI = re.compile(r"(\d+)\s*\.\s*(.+?)\s*\n\s*TC\s*NO\s*:\s*(\d{11})", re.IGNORECASE)
_RE_ISVEREN = re.compile(r"(?:\d+\s*\.\s*)?(.+?)\s*\n\s*S[İI]C[İI]L\s*NO\s*:\s*(.+?)\s*$",
                         re.IGNORECASE | re.DOTALL)


def _basliklari_bul(rows: list[list]) -> tuple[int, dict[int, str]]:
    """Başlık satırının indeksini ve {kolon_indeksi: alan_adi} eşlemesini döndürür."""
    for i, row in enumerate(rows[:10]):
        eslesme = {}
        for j, hucre in enumerate(row):
            if not isinstance(hucre, str):
                continue
            alan = _BASLIKLAR.get(anahtarla(hucre))
            if alan:
                eslesme[j] = alan
        if len(eslesme) >= 5:
            return i, eslesme
    raise ValueError("Denetim listesinde başlık satırı bulunamadı")


def _sigortalilari_ayir(ham: str) -> list[dict]:
    """'1.AYŞE ÖRNEK\\nTC NO:123...\\n2.MITHAT...' -> [{sira, ad_soyad, tc}, ...]"""
    if not ham:
        return []
    kisiler = [
        {"sira": int(m.group(1)), "ad_soyad": m.group(2).strip(), "tc": m.group(3)}
        for m in _RE_SIGORTALI.finditer(ham)
    ]
    if kisiler:
        return kisiler
    # TC'siz ya da beklenmedik biçim: bilgiyi kaybetmemek için ham haliyle taşı
    ad = ham.strip().splitlines()[0].strip()
    return [{"sira": 1, "ad_soyad": re.sub(r"^\d+\s*\.\s*", "", ad), "tc": None}] if ad else []


def _isvereni_ayir(ham: str) -> dict | None:
    """'1.ÜNVAN\\nSİCİL NO:2 0000 ...' -> {unvan, sicil_no}"""
    if not ham or not ham.strip():
        return None
    m = _RE_ISVEREN.match(ham.strip())
    if m:
        return {"unvan": m.group(1).strip(), "sicil_no": re.sub(r"\s+", " ", m.group(2)).strip()}
    return {"unvan": re.sub(r"^\d+\s*\.\s*", "", ham.strip().splitlines()[0]).strip(), "sicil_no": None}


def oku(xlsx_yolu, rows: list[list]) -> list[dict]:
    """Denetim listesini iş (case) sözlüklerine çevirir."""
    baslik_idx, kolonlar = _basliklari_bul(rows)
    isler = []

    for i, row in enumerate(rows[baslik_idx + 1:], start=baslik_idx + 1):
        ham = {}
        for j, alan in kolonlar.items():
            ham[alan] = row[j] if j < len(row) else None

        if not ham.get("denetim_no"):
            continue

        uyarilar = []
        denetim_no, u = uzun_sayi(ham.get("denetim_no"), alan="denetim_no")
        if u: uyarilar.append(u)
        yazi_tarihi, u = seri_tarih(ham.get("yazi_tarihi"), alan="yazi_tarihi")
        if u: uyarilar.append(u)
        yazi_sayisi, u = uzun_sayi(ham.get("yazi_sayisi"), alan="yazi_sayisi")
        if u: uyarilar.append(u)

        def metin(alan):
            v = ham.get(alan)
            return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else (v or None)

        tescilli = _isvereni_ayir(ham.get("tescilli_isveren_ham") or "")
        sigortalilar = _sigortalilari_ayir(ham.get("sigortali_ham") or "")

        if not sigortalilar:
            uyarilar.append("sigortalı bilgisi okunamadı")
        if tescilli is None:
            uyarilar.append("tescilli işveren boş — işyeri tescilsiz olabilir")

        isler.append({
            "schema_version": 1,
            "denetim_no": denetim_no,
            "domain": None,                       # denetim_alani'ndan eşlenecek
            "denetim_alani": metin("denetim_alani"),
            "statu": metin("statu"),
            "il": metin("il"),
            "mufettis": metin("mufettis"),
            "denetim_gerekcesi": {
                "tarih": yazi_tarihi,
                "sayi": yazi_sayisi,
                "mudurluk": None,                 # faz 2: UDF'den gelecek
            },
            "sigortalilar": sigortalilar,
            "isveren": {
                "tescilli": tescilli is not None,
                **(tescilli or {"unvan": None, "sicil_no": None}),
            },
            "diger_isveren": _isvereni_ayir(ham.get("diger_isveren_ham") or ""),
            "gorev_emri": None,                   # cli tarafından doldurulur
            "belgeler": [],
            "bulgular": [],
            "uyarilar": uyarilar,
            "kaynak": {"denetim_listesi": str(xlsx_yolu), "satir": i},
        })

    return isler
