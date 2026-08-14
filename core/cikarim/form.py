"""
form.py — Sabit devlet formlarından etiket çapalı alan çıkarımı.

İşe giriş / işten ayrılış bildirgeleri bu motorla okunur. Düz metinde bu
formların okuma sırası karışık: etiketler bir blokta, değerler bambaşka
yerde akıyor, "işe başladığı tarih" ile "27/03/2023" arasında metinsel hiçbir
bağ yok. Konumda ise ikisi aynı satırda ve yan yana.

Çapa **etiketin kendi kelimeleri**; mutlak dikdörtgen değil. Eski projede
sabit `clip` koordinatları kullanılmış, form sürümü kayınca kalibrasyon
bozulmuş, alanlar sessizce boş dönmüştü. Etiket kayarsa değer de onunla
kayar; hiç bulunmazsa uyarı çıkar.

Değerin nerede bittiğini **yatay boşluk** söyler: form kolonları arasındaki
boşluk (25pt+) kelime aralarındakinden (2-4pt) çok daha geniştir. Böylece
"ÖRNEK ... TİCARET" ünvanı, aynı satırdaki adres kolonuna taşmadan biter.

Hücre ızgaralı alanlar (TC'nin haneleri, işyeri sicilinin bölümleri) tek tek
kutulara yazıldığı için boşluk kuralı işlemez; onlarda `x_araligi` ile açık
bir pencere verilir. Bu tek koordinatlı yol; bu yüzden `dogrula:` ile
eşleşir — kalibrasyon kayarsa sessizce yanlış değil, gürültülü hata verir.

YAML:
    alanlar:
      ise_baslama_tarihi:
        capa: "Sigortalının işe başladığı tarih"
        yon: sag                 # sag | alt
        tip: tarih
        zorunlu: true
      tc:
        capa: "GÜVENLİK NUMARASI)"
        yon: alt
        x_araligi: [40, 320]     # hücre ızgarası — boşluk kuralı işlemez
        tip: tc
        dogrula: tc              # pencere kayarsa sessiz değil gürültülü hata
      sigortali_sicil_no:
        capa: "Sicil Numarası"   # formda iki yerde geçiyor
        yon: sag
        deger_deseni: "\\d{13}"  # doğru olanı biçiminden ayır, sıradan değil
"""
from __future__ import annotations

import re

from core.metin import anahtarla, rakamlar, tc_gecerli
from core.pdf import Belge, Kelime, Satir

_BOSLUK_ESIGI = 15.0        # kolonlar arası boşluk; kelime arası 2-4pt
_ALT_SATIR_ESIGI = 40.0     # 'alt' yönünde en fazla bu kadar aşağı bakılır


def _capa_bul(satir: Satir, capa_kelimeleri: list[str]) -> tuple[int, int] | None:
    """Satırda çapa ifadesini bitişik kelime dizisi olarak arar, (baş, son) indeks."""
    n = len(capa_kelimeleri)
    katlanmis = [anahtarla(k.metin) for k in satir.kelimeler]
    for i in range(len(katlanmis) - n + 1):
        if katlanmis[i:i + n] == capa_kelimeleri:
            return i, i + n - 1
    return None


def _kesintisiz(kelimeler: list[Kelime], esik: float) -> list[Kelime]:
    """İlk büyük yatay boşluğa kadar olan kelimeleri döndürür."""
    if not kelimeler:
        return []
    out = [kelimeler[0]]
    for onceki, k in zip(kelimeler, kelimeler[1:]):
        if k.x0 - onceki.x1 > esik:
            break
        out.append(k)
    return out


def _dogrula(tur: str, deger: str) -> str | None:
    if tur == "tc":
        return None if tc_gecerli(deger) else f"TC sağlaması tutmuyor ({deger})"
    if tur.startswith("uzunluk="):
        beklenen = int(tur.split("=", 1)[1])
        r = rakamlar(deger)
        return None if len(r) == beklenen else f"{beklenen} hane bekleniyordu, {len(r)} geldi ({deger})"
    if tur.startswith("desen="):
        kalip = tur.split("=", 1)[1]
        return None if re.fullmatch(kalip, deger.strip()) else f"desene uymuyor ({deger!r} ~ {kalip})"
    return f"bilinmeyen doğrulama: {tur!r}"


def cikar(belge: Belge, alanlar) -> tuple[dict[str, str], list[str]]:
    """Alan tanımlarını forma uygulayıp {alan_adi: ham_deger} döndürür."""
    uyarilar: list[str] = []
    ham: dict[str, str] = {}

    sayfa_satirlari = [(s, s.satirlar()) for s in belge.sayfalar]

    for a in alanlar:
        capa = a.ek.get("capa")
        if not capa:
            uyarilar.append(f"form: {a.ad} — tanımda 'capa' yok, alan atlandı")
            continue

        yon = a.ek.get("yon", "sag")
        esik = float(a.ek.get("bosluk_esigi", _BOSLUK_ESIGI))
        aralik = a.ek.get("x_araligi")
        capa_kelimeleri = [anahtarla(w) for w in str(capa).split()]

        bulunanlar: list[str] = []
        for sayfa, satirlar in sayfa_satirlari:
            for idx, satir in enumerate(satirlar):
                yer = _capa_bul(satir, capa_kelimeleri)
                if yer is None:
                    continue
                bas, son = yer

                if yon == "sag":
                    sag_kelimeler = satir.kelimeler[son + 1:]
                    if aralik:
                        sag_kelimeler = [k for k in sag_kelimeler if aralik[0] <= k.x0 <= aralik[1]]
                    else:
                        # Çapadan sonraki ilk boşluk zaten değerin başlangıcı;
                        # kesintisizlik oradan itibaren işletilir.
                        sag_kelimeler = _kesintisiz(sag_kelimeler, esik)
                    deger = " ".join(k.metin for k in sag_kelimeler)
                elif yon == "alt":
                    capa_kel = satir.kelimeler[bas:son + 1]
                    # Pencere çapanın kendi sol kenarından başlar: form alan
                    # numarası ("22") çapanın solunda kalır, değere karışmasın.
                    pencere = (aralik if aralik else
                               (min(k.x0 for k in capa_kel) - 2.0, float("inf")))
                    deger = ""
                    for alt in satirlar[idx + 1:]:
                        if alt.y0 - satir.y1 > _ALT_SATIR_ESIGI:
                            break
                        icerik = [k for k in alt.kelimeler if pencere[0] <= k.x0 <= pencere[1]]
                        if not icerik:
                            continue
                        if not aralik:
                            icerik = _kesintisiz(icerik, esik)
                        deger = " ".join(k.metin for k in icerik)
                        break
                else:
                    uyarilar.append(f"form: {a.ad} — bilinmeyen yön {yon!r} (sag|alt)")
                    break

                if deger.strip():
                    bulunanlar.append(deger.strip())

        if not bulunanlar:
            uyarilar.append(f"form: {a.ad} — '{capa}' çapası bulunamadı ya da değeri boş"
                            + (" [ZORUNLU]" if a.zorunlu else ""))
            continue

        # Aynı çapa metni birden çok yerde geçebiliyor ("Sicil Numarası" hem
        # sigortalının hem işyerinin bölümünde). Sıraya göre seçmek yerine
        # değerin biçimine bakmak hem anlamlı hem denetlenebilir.
        if desen := a.ek.get("deger_deseni"):
            elenen = [d for d in bulunanlar if re.fullmatch(desen, d.strip())]
            if not elenen:
                uyarilar.append(f"form: {a.ad} — '{capa}' çapasının hiçbir değeri "
                                f"{desen!r} desenine uymadı (bulunanlar: {bulunanlar[:3]})")
                continue
            bulunanlar = elenen

        benzersiz = list(dict.fromkeys(bulunanlar))
        if len(benzersiz) > 1:
            sira = a.ek.get("sira")
            if sira is None:
                uyarilar.append(f"form: {a.ad} — '{capa}' çapası {len(benzersiz)} farklı "
                                f"değer verdi {benzersiz[:3]}, ilki alındı; "
                                f"tanıma 'sira' ekle")
            else:
                benzersiz = [benzersiz[int(sira)]] if int(sira) < len(benzersiz) else benzersiz

        deger = benzersiz[0]
        if dogrulama := a.ek.get("dogrula"):
            if hata := _dogrula(str(dogrulama), deger):
                uyarilar.append(f"form: {a.ad} — {hata}; çapa/x_araligi kalibrasyonu kaymış olabilir")

        ham[a.ad] = deger

    return ham, uyarilar
