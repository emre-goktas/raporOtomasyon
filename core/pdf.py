"""
pdf.py — pymupdf üzerine ince bir katman: kelime, satır, sayfa.

Çıkarım motorlarının üçü de (form / etiketli / tablo) aynı ilkel yapıları
kullanır: konumlu kelimeler ve dikey örtüşmeye göre kurulan satırlar.

Neden düz metin değil: kurum formlarında okuma sırası karışık geliyor —
işe giriş bildirgesinde etiketler bir blokta, değerler bambaşka bir blokta
akıyor. Düz metinde "işe başladığı tarih" ile "27/03/2023" arasında hiçbir
bağ yok; konumda ise ikisi aynı satırda ve yan yana.

Neden mutlak koordinat da değil: eski projede sabit `clip` dikdörtgenleri
kullanılmış, form sürümü kayınca kalibrasyon bozulmuş ve alanlar sessizce
boş dönmüş. Burada çapa **etiketin kendi metni**; etiket nereye kayarsa
değer de onunla birlikte kayar.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

# Sayfa medyan satır yüksekliğinin bu katından uzun kelimeler yatay metin
# değildir (dik basılmış damga kodu, tablo çizgisi). Satır kurmada kullanılmaz.
_DEV_KELIME_KATI = 3.0


@dataclass(frozen=True)
class Kelime:
    x0: float
    y0: float
    x1: float
    y1: float
    metin: str

    @property
    def orta_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def yukseklik(self) -> float:
        return self.y1 - self.y0

    def dikey_ortusuyor(self, other: "Kelime", oran: float = 0.4) -> bool:
        """İki kelime aynı satırda mı? Yükseklikleri farklı olabilir (form
        etiketi 7pt, değeri 9pt) — bu yüzden örtüşme oranına bakıyoruz."""
        ust = max(self.y0, other.y0)
        alt = min(self.y1, other.y1)
        if alt <= ust:
            return False
        return (alt - ust) >= oran * min(self.yukseklik, other.yukseklik)


@dataclass
class Satir:
    kelimeler: list[Kelime]

    @property
    def metin(self) -> str:
        return " ".join(k.metin for k in self.kelimeler)

    @property
    def y0(self) -> float:
        return min(k.y0 for k in self.kelimeler)

    @property
    def y1(self) -> float:
        return max(k.y1 for k in self.kelimeler)


@dataclass
class Sayfa:
    no: int                      # 1 tabanlı
    genislik: float
    yukseklik: float
    kelimeler: list[Kelime]
    duz_metin: str
    # satirlar() doldurur: satır kurmaya katılmayan dik/dev kelimeler
    ayrik_kelimeler: list[Kelime] = field(default_factory=list)

    def satirlar(self, oran: float = 0.4) -> list[Satir]:
        """Kelimeleri satırlara toplar, soldan sağa sıralar.

        Gruplama dikey örtüşmeye göre; ama önce **dik/dev kelimeler ayıklanır**.
        Ünite kararında sayfanın kenarına dik basılmış 215pt'lik bir damga
        kodu var (medyan satır yüksekliği 12pt) — örtüşme ölçütüyle o tek
        kelime sayfadaki her satırı kendine çekiyor, sayfa dört dev satıra
        iniyordu.

        Ayıklananlar `ayrik_kelimeler` içinde durur — atılmaz, çünkü sessizce
        kaybolan içerik en tehlikeli davranıştır.
        """
        if not self.kelimeler:
            return []

        medyan = statistics.median(k.yukseklik for k in self.kelimeler) or 1.0
        tavan = medyan * _DEV_KELIME_KATI
        yatay = [k for k in self.kelimeler if k.yukseklik <= tavan]
        self.ayrik_kelimeler = [k for k in self.kelimeler if k.yukseklik > tavan]
        if not yatay:
            return []

        gruplar: list[list[Kelime]] = []
        for k in sorted(yatay, key=lambda k: (k.y0, k.x0)):
            for g in gruplar:
                if g[0].dikey_ortusuyor(k, oran):
                    g.append(k)
                    break
            else:
                gruplar.append([k])

        satirlar = [Satir(sorted(g, key=lambda k: k.x0)) for g in gruplar]
        return sorted(satirlar, key=lambda s: s.y0)


@dataclass
class Belge:
    yol: Path
    sayfalar: list[Sayfa]

    @property
    def duz_metin(self) -> str:
        return "\n".join(s.duz_metin for s in self.sayfalar)

    @property
    def metin_katmani_var(self) -> bool:
        """False ise belge taranmıştır — deterministik çıkarım denenmemeli,
        Faz 5'in vision yoluna düşer. Sessizce boş alan üretmektense
        belgeyi 'okunamadı' diye işaretlemek gerekir."""
        return len(self.duz_metin.strip()) >= 50


def oku(pdf_yolu) -> Belge:
    import pymupdf

    yol = Path(pdf_yolu)
    sayfalar = []
    with pymupdf.open(yol) as doc:
        for i, sayfa in enumerate(doc, start=1):
            kelimeler = [
                Kelime(x0, y0, x1, y1, t)
                for x0, y0, x1, y1, t, *_ in sayfa.get_text("words")
                if t.strip()
            ]
            sayfalar.append(Sayfa(
                no=i,
                genislik=sayfa.rect.width,
                yukseklik=sayfa.rect.height,
                kelimeler=kelimeler,
                duz_metin=sayfa.get_text(),
            ))
    return Belge(yol=yol, sayfalar=sayfalar)
