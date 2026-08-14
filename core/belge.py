"""
belge.py — Bir belgeyi tanır, doğru motora yönlendirir, çıkarımı toplar.

Belge türü **içerikten** anlaşılır, dosya adından değil (kural 2): eski
projede konfigürasyon `*_ic.pdf` bekliyordu, sistem `_ia` veriyordu, parser
sessizce hiç çalışmadı. Ayrıca JETEK dosyaları yeniden adlandırıyor.

Tanıma imzası her belge tanımının `tanima:` bloğunda:

    tanima:
      metin_icerir: ["SİGORTALI İŞE GİRİŞ BİLDİRGESİ"]   # düz metinde geçmeli
      gerekli_anahtarlar: ["İş Yeri Sicil No"]            # etiketli motorda

Hiçbir tanıma uymazsa belge `tur: null` ile kaydedilir ve uyarı üretilir —
tanınmayan belge sessizce yok sayılmaz, Faz 3/5'in kuyruğunda görünür.
"""
from __future__ import annotations

from pathlib import Path

from core import pdf
from core.cikarim import etiketli, form, satir, sema, tablo
from core.metin import anahtarla

_PDF_UZANTILARI = {".pdf"}


def _imza_skoru(belge: pdf.Belge, tanim: sema.BelgeTanimi,
                etiket_anahtarlari: set[str] | None) -> int:
    """Kaç tanıma ölçütü tuttu? 0 = bu belge değil."""
    t = tanim.tanima or {}
    metin = anahtarla(belge.duz_metin)
    skor = 0

    beklenen = t.get("metin_icerir") or []
    for parca in beklenen:
        if anahtarla(parca) in metin:
            skor += 1
        else:
            return 0                      # bildirilen imza tutmuyorsa aday değil

    gerekli = t.get("gerekli_anahtarlar") or []
    if gerekli:
        if etiket_anahtarlari is None:
            return 0
        for a in gerekli:
            if anahtarla(a) not in etiket_anahtarlari:
                return 0
            skor += 1

    return skor if (beklenen or gerekli) else 0


def tani(belge: pdf.Belge, tanimlar: dict[str, sema.BelgeTanimi]
         ) -> tuple[sema.BelgeTanimi | None, list[str]]:
    """Belgeye uyan tanımı döndürür. Birden çok aday varsa uyarı üretir."""
    if not belge.metin_katmani_var:
        return None, [f"{belge.yol.name}: metin katmanı yok — taranmış belge, "
                      f"deterministik çıkarım uygulanamaz (Faz 5)"]

    # 'gerekli_anahtarlar' kullanan tanımlar için etiketleri bir kez çıkar
    etiket_anahtarlari: set[str] | None = None
    if any((t.tanima or {}).get("gerekli_anahtarlar") for t in tanimlar.values()):
        alanlar, _, _ = etiketli.ayristir(belge)
        etiket_anahtarlari = {a.anahtar for a in alanlar}

    adaylar = [(t, s) for t in tanimlar.values()
               if (s := _imza_skoru(belge, t, etiket_anahtarlari)) > 0]
    if not adaylar:
        return None, [f"{belge.yol.name}: hiçbir belge tanımına uymadı — "
                      f"tanınmayan belge"]

    adaylar.sort(key=lambda p: -p[1])
    uyarilar = []
    if len(adaylar) > 1 and adaylar[0][1] == adaylar[1][1]:
        uyarilar.append(f"{belge.yol.name}: {adaylar[0][0].belge_turu} ve "
                        f"{adaylar[1][0].belge_turu} imzaları eşit güçte, "
                        f"ilki seçildi")
    return adaylar[0][0], uyarilar


def isle(yol: Path, tanimlar: dict[str, sema.BelgeTanimi]) -> dict:
    """Tek bir belgeyi case.json'ın belgeler[] girdisine çevirir."""
    belge = pdf.oku(yol)
    kayit: dict = {
        "tur": None,
        "motor": None,
        "kaynak": {"dosya": str(yol), "dosya_adi": yol.name,
                   "sayfa_sayisi": len(belge.sayfalar),
                   "metin_katmani": belge.metin_katmani_var},
        "alanlar": {},
        "satirlar": [],
        "uyarilar": [],
        "ek_no": None,          # Faz 7: JETEK manifest'inden gelecek
        "citation_key": None,   # Faz 6: rapordaki sabit atıf anahtarı
    }

    tanim, uyarilar = tani(belge, tanimlar)
    kayit["uyarilar"] += uyarilar
    if tanim is None:
        return kayit

    kayit["tur"] = tanim.belge_turu
    kayit["motor"] = tanim.motor
    kayit["citation_key"] = tanim.belge_turu.replace("_", "-")

    if tanim.motor == "etiketli":
        alanlar, serbest, u1 = etiketli.ayristir(belge)
        ham, u2 = etiketli.sozluk(alanlar)
        veri, u3 = sema.uygula(tanim, ham)
        kayit["alanlar"] = veri
        kayit["uyarilar"] += u1 + u3          # tekrar uyarıları (u2) gürültü, atlanıyor
        kayit["kaynak"]["bolum_basliklari"] = [s.metin for s in serbest
                                               if len(s.metin) > 6 and "/" not in s.metin]

    elif tanim.motor == "satir":
        alanlar, bloklar, u1 = satir.ayristir(belge)
        veri, u2 = sema.uygula(tanim, satir.ham_sozluk(alanlar, bloklar))
        kayit["alanlar"] = veri
        kayit["uyarilar"] += u1 + u2
        kayit["kaynak"]["bolum_basliklari"] = [b for b in bloklar if not b.startswith("_")]

    elif tanim.motor == "form":
        ham, u1 = form.cikar(belge, tanim.alanlar)
        veri, u2 = sema.uygula(tanim, ham)
        kayit["alanlar"] = veri
        kayit["uyarilar"] += u1 + u2

    elif tanim.motor == "tablo":
        import yaml as _yaml
        tablo_tanimi = (_yaml.safe_load(tanim.yol.read_text(encoding="utf-8"))
                        or {}).get("tablo") or {}
        sonuc = tablo.cikar(belge, tablo_tanimi)
        kayit["satirlar"] = sonuc.satirlar
        kayit["uyarilar"] += sonuc.uyarilar
        if sonuc.atlanan:
            kayit["kaynak"]["atlanan_satir"] = len(sonuc.atlanan)
        # Tablo motorunda alan tanımı varsa (özet alanlar) o da uygulanır
        if tanim.alanlar:
            veri, u = sema.uygula(tanim, {})
            kayit["alanlar"] = veri
            kayit["uyarilar"] += u

    else:
        kayit["uyarilar"].append(f"{yol.name}: bilinmeyen motor {tanim.motor!r}")

    return kayit


def topla(girdi: Path, tanimlar: dict[str, sema.BelgeTanimi]) -> list[dict]:
    """Klasördeki tüm PDF'leri işler. Dosya adına göre sıralı, tekrarlanabilir."""
    dosyalar = sorted(p for p in Path(girdi).iterdir()
                      if p.is_file() and p.suffix.lower() in _PDF_UZANTILARI)
    return [isle(p, tanimlar) for p in dosyalar]
