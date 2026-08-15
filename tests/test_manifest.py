"""JETEK manifest'inin okunması ve belgelerle eşlenmesi.

Bu katman raporun `(Ek:7)` atıflarının tek kaynağı — yanlış eşleşen bir ek,
raporda yanlış belgeye atıf yapar ve bunu hiçbir şey fark etmez. Bu yüzden
testlerin çoğu eşleşmenin *olmadığı* durumları sınıyor.
"""
import json
import tempfile
from pathlib import Path

from yardim import Sonuc
from core import manifest


def _ek(no, mahiyet, dosya, sayfa, kaynak=None, anahtar=None):
    # citation_key JETEK'in ürettiği ASCII slug — burada elle yazılıyor,
    # mahiyet'ten türetilmiyor: `"İ".lower()` Python'da da JS'te de iki kod
    # noktası ("i" + birleşen nokta) verir, testin kendi kolaylık kodu bu
    # tuzağa düşerse sınadığı şeyi değil kendini sınamış olur.
    return {"ek_no": no, "citation_key": anahtar or mahiyet.replace(" ", "-"),
            "mahiyet": mahiyet, "dosya": dosya, "sayfa_adedi": sayfa,
            "sayfa_araligi": [1, sayfa],
            "kaynak": {"dosya_adi": kaynak} if kaynak else None}


def _belge(dosya_adi, tur=None, sayfa=1):
    return {"tur": tur, "citation_key": tur.replace("_", "-") if tur else None,
            "kaynak": {"dosya_adi": dosya_adi, "sayfa_sayisi": sayfa},
            "ek_no": None, "alanlar": {}, "satirlar": [], "uyarilar": []}


def calistir():
    s = Sonuc("manifest — JETEK ek numarası bağlama")

    # ── oku ──────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "manifest.json").write_text(json.dumps(
            {"surum": 1, "ekler": [_ek(1, "Görev Emri", "01_ge.pdf", 1)]}), encoding="utf-8")
        ekler, u = manifest.oku(d / "manifest.json")
        s.kontrol("geçerli manifest okunur", len(ekler), 1)
        s.kontrol("geçerli manifest uyarı üretmez", u, [])
        s.kontrol("bul() dizinde manifest'i bulur", manifest.bul(d).name, "manifest.json")
        s.kontrol("bul() yoksa None döner", manifest.bul(d / "yok"), None)

        (d / "bozuk.json").write_text("{ bu json değil", encoding="utf-8")
        ekler, u = manifest.oku(d / "bozuk.json")
        s.kontrol("bozuk JSON boş liste döner", ekler, [])
        s.dogru("bozuk JSON sessiz kalmaz", any("okunamadı" in x for x in u))

        (d / "yeni.json").write_text(json.dumps({"surum": 99, "ekler": []}), encoding="utf-8")
        _, u = manifest.oku(d / "yeni.json")
        s.dogru("bilinmeyen sürüm uyarı üretir", any("sürüm" in x for x in u))
        s.dogru("ek listesi yoksa uyarı üretir", any("ek listesi yok" in x for x in u))

    # ── bagla: iki eşleme yolu ───────────────────────────────────────────
    ekler = [
        _ek(7, "İşyeri Tescil", "07_tescil.pdf", 4, kaynak="tescilBilgi_92063506.pdf",
            anahtar="isyeri-tescil"),
        _ek(8, "İfade Tutanağı", "08_ifade.pdf", 3, kaynak="tarama.pdf",
            anahtar="ifade-tutanagi"),
    ]

    b = [_belge("07_tescil.pdf", "isyeri_tescil", 4)]
    u, _ = manifest.bagla(b, ekler)
    s.kontrol("JETEK ZIP adıyla eşleşir", b[0]["ek_no"], 7)
    s.kontrol("eşleşen belge uyarı üretmez", u, [])

    b = [_belge("tescilBilgi_92063506.pdf", "isyeri_tescil", 4)]
    manifest.bagla(b, ekler)
    s.kontrol("ham kurum dosya adıyla da eşleşir", b[0]["ek_no"], 7)

    # ── bagla: gürültülü başarısızlıklar ─────────────────────────────────
    b = [_belge("hicbir_yerde_yok.pdf", "isyeri_tescil", 4)]
    u, _ = manifest.bagla(b, ekler)
    s.kontrol("eşleşmeyen belgeye numara atanmaz", b[0]["ek_no"], None)
    s.dogru("eşleşmeyen belge uyarı üretir", any("ek listesinde yok" in x for x in u))

    b = [_belge("07_tescil.pdf", "isyeri_tescil", 3)]   # manifest 4 sayfa diyor
    u, _ = manifest.bagla(b, ekler)
    s.dogru("sayfa adedi uyuşmazlığı yakalanır", any("sayfa beyan" in x for x in u))
    s.kontrol("uyuşmazlığa rağmen numara atanır (uyarıyla)", b[0]["ek_no"], 7)

    b = [_belge("07_tescil.pdf", "isyeri_tescil", 4)]
    u, bilgi = manifest.bagla(b, ekler)
    s.kontrol("klasörde olmayan ek uyarı DEĞİL bilgi üretir", u, [])
    s.dogru("klasörde olmayan ek bilgi olarak bildirilir",
            any("Ek:8" in x for x in bilgi))

    # ── yeniden çalıştırma ───────────────────────────────────────────────
    b = [_belge("07_tescil.pdf", "isyeri_tescil", 4)]
    manifest.bagla(b, ekler)
    manifest.bagla(b, [])                 # manifest boşaldı
    s.kontrol("eski ek numarası asılı kalmaz", b[0]["ek_no"], None)

    # ── ek_haritasi ──────────────────────────────────────────────────────
    b = [_belge("07_tescil.pdf", "isyeri_tescil", 4)]
    manifest.bagla(b, ekler)
    h = manifest.ek_haritasi(b, ekler)
    s.kontrol("tanınan belge türüyle çözülür", h["isyeri_tescil"], 7)
    s.kontrol("tanınmayan belge citation_key ile çözülür", h["ifade-tutanagi"], 8)
    s.kontrol("manifest yoksa yalnız belgelerden kurulur",
              manifest.ek_haritasi(b, None), {"isyeri_tescil": 7, "isyeri-tescil": 7})

    return s
