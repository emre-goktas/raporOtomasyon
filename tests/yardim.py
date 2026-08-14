"""Testlerin ortak koşum yardımcısı — dış bağımlılık istemiyoruz.

Gerçek belgelerden çıkan **tam değerler** depoya girmez: TC kimlik numarası,
ad-soyad ve işveren ünvanı kişisel veridir. Bunlar `ornek_veri/beklenen.json`
içinde durur (gitignore'da). Dosya varsa testler tam eşitlik arar; yoksa
yalnız özellik kontrolü yapar (alan doldu mu, TC sağlaması tutuyor mu,
tarih ISO biçiminde mi). İkisi de aynı regresyonu yakalar; ikincisi değeri
açığa vurmaz.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

KOK = pathlib.Path(__file__).resolve().parent.parent
ORNEK = KOK / "ornek_veri" / "ornek_dosya"


def beklenen() -> dict | None:
    """ornek_veri/beklenen.json — yoksa None."""
    p = KOK / "ornek_veri" / "beklenen.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


BEKLENEN = beklenen()


class Sonuc:
    def __init__(self, baslik):
        print(f"\n{baslik}")
        self.gecen = self.kalan = 0

    def kontrol(self, ad, gercek, beklenen=True):
        ok = gercek == beklenen
        print(f"  {'✓' if ok else '✗'} {ad}"
              + ("" if ok else f"\n      gerçek  : {gercek!r}\n      beklenen: {beklenen!r}"))
        self.gecen += ok
        self.kalan += not ok
        return ok

    def dogru(self, ad, kosul):
        return self.kontrol(ad, bool(kosul), True)

    def tam_deger(self, ad, gercek, *yol):
        """beklenen.json varsa tam eşitlik; yoksa yalnız 'değer var mı'."""
        if BEKLENEN is None:
            return self.dogru(f"{ad} (değer dosyası yok, yalnız doluluk)", gercek not in (None, ""))
        d = BEKLENEN
        for k in yol:
            d = (d or {}).get(k) if isinstance(d, dict) else None
        return self.kontrol(ad, gercek, d)
