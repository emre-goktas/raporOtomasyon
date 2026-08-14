"""Yeni sistemin PDF denetim gerekçesi ve ünite kararı (satir motoru).

Yedi denetim gerekçesi yedi ayrı SGK müdürlüğünden geliyor ve **yedisi de
etiketleri farklı yazıyor**; testler tam metin eşleşmesine değil, anahtar
kelime eşleşmesinin varyantları yakalamasına bakıyor.

Beklenen tam değerler `ornek_veri/beklenen.json`'da (gitignore'da) — kişisel
veri depoya girmesin diye. O dosya yoksa özellik kontrolleri yine çalışır.
"""
import re

from yardim import BEKLENEN, KOK, Sonuc
from core import belge, pdf
from core.cikarim import sema
from core.metin import tc_gecerli

YENI = KOK / "ornek_veri" / "yeni_sistem"


def calistir():
    s = Sonuc("satir — yeni sistem denetim gerekçesi / ünite kararı")
    if not YENI.is_dir():
        print(f"  ! {YENI} yok, atlandı")
        return s

    t = sema.yukle_domain("domains/is_kazasi")
    turler: dict[str, list[dict]] = {}
    for p in sorted(YENI.glob("*.pdf")):
        b = pdf.oku(p)
        if len(b.sayfalar) <= 2 and b.metin_katmani_var:
            k = belge.isle(p, t)
            if k["tur"]:
                turler.setdefault(k["tur"], []).append(k["alanlar"])
    for liste in turler.values():
        liste.sort(key=lambda a: str(a.get("sayi")))

    gerekceler = turler.get("denetim_gerekcesi", [])
    s.kontrol("7 denetim gerekçesi tanındı", len(gerekceler), 7)
    s.kontrol("1 ünite kararı tanındı", len(turler.get("unite_karari", [])), 1)

    # Etiket varyantlarına rağmen kritik alanlar her belgede çıkmalı
    s.dogru("hepsinde TC çıktı ve sağlaması tuttu",
            gerekceler and all(tc_gecerli(a.get("tc")) for a in gerekceler))
    s.dogru("hepsinde kaza/tespit tarihi ISO biçiminde çıktı",
            gerekceler and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.get("kaza_tarihi") or "")
                               for a in gerekceler))
    s.dogru("hepsinde işveren ünvanı çıktı",
            gerekceler and all((a.get("isveren_unvan") or "").strip() for a in gerekceler))
    s.dogru("hepsinde yazı tarihi çıktı",
            gerekceler and all(a.get("tarih") for a in gerekceler))

    # Bir müdürlük ':' yerine ';' yazmış; tescilsiz işyeri bilgisi kaybolmamalı
    s.kontrol("tescilsiz işyeri iki gerekçede okundu",
              sum(1 for a in gerekceler if "escilsiz" in (a.get("isyeri_sicil") or "")), 2)

    uk = (turler.get("unite_karari") or [{}])[0]
    s.dogru("ünite kararı: karar no sayı olarak çıktı", isinstance(uk.get("karar_no"), int))
    s.dogru("ünite kararı: TC sağlaması tuttu", tc_gecerli(uk.get("tc")))
    s.dogru("ünite kararı: kaza saati ss:dd biçiminde",
            re.fullmatch(r"\d{1,2}:\d{2}", uk.get("kaza_saati") or ""))
    s.dogru("ünite kararı: oluş şekli iki satır birleşti (nokta ile bitiyor)",
            (uk.get("olus_sekli") or "").endswith("."))
    s.kontrol("ünite kararı: adli rapor kutucuğu", uk.get("belge_adli_rapor"), True)
    s.kontrol("ünite kararı: kaza bildirimi kutucuğu", uk.get("belge_kaza_bildirimi"), False)
    s.dogru("ünite kararı: sonuç ve kanaat metni alındı",
            "karar verilmiştir" in (uk.get("sonuc_kanaat") or ""))

    # beklenen.json varsa tam alan karşılaştırması (en güçlü regresyon)
    if BEKLENEN:
        for tur, liste in sorted(turler.items()):
            s.kontrol(f"{tur}: tüm alanlar beklenenle aynı",
                      liste, BEKLENEN["yeni_sistem"][tur])
    return s
