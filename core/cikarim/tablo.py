"""
tablo.py — Sabit kolonlu kurum tablolarını satır listesine çevirir.

Hizmet dökümü bu motorla okunur: 10 sayfa, sayfa başına tekrar eden başlık,
satırların çoğu alanı boş (giriş/çıkış tarihi yalnız o ay değişmişse dolu).
Düz metinde kolon bilgisi tamamen kaybolur — "1 120 728,400,000.00" dizisinde
hangi sayının hangi kolona ait olduğunu yalnız x konumu söyler.

Kolon çapaları YAML'da açıkça yazılır (tablo sabit genişlikli bir kurum
çıktısı; gerçek yapısı budur), ama **her sayfada başlık satırıyla doğrulanır**:
beklenen başlık kelimesi beklenen kolon aralığında yoksa uyarı üretilir.
Eski projenin sessizce yanlış kolon okuma hatası böyle gürültülü hâle gelir.

Satır birleştirme: `satir_capasi` kolonu dolu olan satır yeni kayıt başlatır;
altındaki bitişik satırlar (ör. "Aylık Bordro"nun ikinci satırı) aynı kaydın
hücrelerine eklenir. Ne başlık ne kayıt olan satırlar `atlanan` listesinde
görünür — sessizce yutulmaz.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.metin import anahtarla
from core.pdf import Belge, Satir

_HIZA_TOLERANS = 4.0        # değerler kolon çapasına sola dayalı
_BITISIK_ESIK = 12.0        # devam satırının önceki satıra dikey uzaklığı


@dataclass
class Kolon:
    ad: str
    x: float
    baslik: str
    sag: float = float("inf")


@dataclass
class Sonuc:
    satirlar: list[dict]
    atlanan: list[tuple[int, float, str]]     # (sayfa, y, metin)
    uyarilar: list[str]


def _kolonlari_kur(tanim: dict) -> tuple[list[Kolon], list[str]]:
    ham = tanim.get("kolonlar") or []
    if not ham:
        return [], ["tablo: tanımda 'kolonlar' yok"]
    kolonlar = [Kolon(ad=k["ad"], x=float(k["x"]), baslik=k.get("baslik", "")) for k in ham]
    kolonlar.sort(key=lambda k: k.x)
    for i in range(len(kolonlar) - 1):
        kolonlar[i].sag = kolonlar[i + 1].x
    return kolonlar, []


def _kolon_no(kolonlar: list[Kolon], x0: float) -> int | None:
    """Sola dayalı değeri kendi kolonuna eşler."""
    secim = None
    for i, k in enumerate(kolonlar):
        if x0 + _HIZA_TOLERANS >= k.x:
            secim = i
        else:
            break
    return secim


def _basligi_dogrula(kolonlar: list[Kolon], baslik_satirlari: list[Satir],
                     sayfa_no: int) -> list[str]:
    """Beklenen başlık kelimesi beklenen kolon aralığında mı?"""
    kelimeler = [k for s in baslik_satirlari for k in s.kelimeler]
    uyarilar = []
    for kol in kolonlar:
        if not kol.baslik:
            continue
        beklenen = anahtarla(kol.baslik)
        varmi = any(anahtarla(k.metin) == beklenen
                    and kol.x - _HIZA_TOLERANS <= k.x0 < kol.sag for k in kelimeler)
        if not varmi:
            uyarilar.append(f"tablo: s.{sayfa_no} — '{kol.baslik}' başlığı {kol.ad} "
                            f"kolonunda (x≈{kol.x:.0f}) yok; kolon hizası kaymış olabilir")
    return uyarilar


def cikar(belge: Belge, tanim: dict) -> Sonuc:
    kolonlar, uyarilar = _kolonlari_kur(tanim)
    if not kolonlar:
        return Sonuc([], [], uyarilar)

    capa = tanim.get("satir_capasi")
    if capa and capa not in {k.ad for k in kolonlar}:
        return Sonuc([], [], uyarilar + [f"tablo: satir_capasi {capa!r} kolonlar arasında yok"])

    baslik_isaretleri = [anahtarla(x) for x in (tanim.get("baslik_capalari") or [])]
    bitis_isaretleri = [anahtarla(x) for x in (tanim.get("bitis_capalari") or [])]
    en_az_dolu = int(tanim.get("en_az_dolu_kolon", 3))
    baslik_yuksekligi = float(tanim.get("baslik_yuksekligi", 32))

    satirlar: list[dict] = []
    atlanan: list[tuple[int, float, str]] = []

    for sayfa in belge.sayfalar:
        tum = sayfa.satirlar()

        # Başlık bloğu: çapa kelimesini taşıyan ilk satır ve onun altındaki
        # başlık yüksekliği kadar satır. Tablonun üstünde yazı olabiliyor
        # (hizmet dökümünün 1. sayfasında üst yazı var), bu yüzden başlık
        # sayfanın en üstünde aranmaz — sayfanın tamamında aranır.
        baslik_sonu = -1
        baslik_satirlari: list[Satir] = []
        bas = next((i for i, s in enumerate(tum)
                    if baslik_isaretleri
                    and any(b in {anahtarla(k.metin) for k in s.kelimeler}
                            for b in baslik_isaretleri)), None)
        if bas is not None:
            tavan = tum[bas].y0 + baslik_yuksekligi
            for i in range(bas, len(tum)):
                if tum[i].y0 > tavan:
                    break
                baslik_satirlari.append(tum[i])
                baslik_sonu = i
        if baslik_satirlari:
            uyarilar += _basligi_dogrula(kolonlar, baslik_satirlari, sayfa.no)
        elif baslik_isaretleri:
            uyarilar.append(f"tablo: s.{sayfa.no} — başlık satırı bulunamadı "
                            f"(aranan: {tanim.get('baslik_capalari')})")

        son_kayit: dict | None = None
        son_y1 = None
        for s in tum[baslik_sonu + 1:]:
            katlanmis = {anahtarla(k.metin) for k in s.kelimeler}
            if bitis_isaretleri and any(b in katlanmis for b in bitis_isaretleri):
                break

            hucreler: dict[str, list[str]] = {}
            for k in s.kelimeler:
                i = _kolon_no(kolonlar, k.x0)
                if i is None:
                    continue
                hucreler.setdefault(kolonlar[i].ad, []).append(k.metin)
            deger = {ad: " ".join(p) for ad, p in hucreler.items()}

            yeni_kayit = bool(deger.get(capa)) if capa else len(deger) >= en_az_dolu
            if yeni_kayit and len(deger) >= en_az_dolu:
                son_kayit = {k.ad: deger.get(k.ad) or None for k in kolonlar}
                son_kayit["_sayfa"] = sayfa.no
                son_kayit["_y"] = round(s.y0, 1)
                satirlar.append(son_kayit)
                son_y1 = s.y1
                continue

            if son_kayit is not None and son_y1 is not None and (s.y0 - son_y1) <= _BITISIK_ESIK:
                for ad, parca in deger.items():
                    son_kayit[ad] = f"{son_kayit[ad]} {parca}".strip() if son_kayit.get(ad) else parca
                son_y1 = s.y1
                continue

            atlanan.append((sayfa.no, round(s.y0, 1), s.metin[:90]))
            son_kayit, son_y1 = None, None

    return Sonuc(satirlar, atlanan, uyarilar)
