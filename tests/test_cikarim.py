"""Gerçek belgeler üzerinde uçtan uca regresyon (3a belgeleri).

Beklenen tam değerler `ornek_veri/beklenen.json`'da (gitignore'da) durur —
TC, ad-soyad ve işveren ünvanı kişisel veridir, depoya girmez. Buradaki
kontroller değeri açığa vurmadan aynı regresyonu yakalar; beklenen.json
varsa üstüne tam alan karşılaştırması da yapılır.
"""
import re

from yardim import BEKLENEN, ORNEK, Sonuc
from core import belge
from core.cikarim import sema
from core.metin import tc_gecerli

ISO = r"\d{4}-\d{2}-\d{2}"


def calistir():
    s = Sonuc("cikarim — gerçek belgelerle uçtan uca")
    if not ORNEK.is_dir():
        print(f"  ! {ORNEK} yok, atlandı")
        return s

    tanimlar = sema.yukle_domain("domains/is_kazasi")
    s.kontrol("belge tanımları yüklendi", sorted(tanimlar),
              ["denetim_gerekcesi", "hizmet_dokumu", "ise_giris_bildirgesi",
               "isten_ayrilis_bildirgesi", "isyeri_tescil", "unite_karari"])

    kayitlar = {k["tur"]: k for k in belge.topla(ORNEK, tanimlar)}

    ig = kayitlar.get("ise_giris_bildirgesi", {}).get("alanlar", {})
    s.dogru("ig: işe başlama tarihi ISO", re.fullmatch(ISO, ig.get("ise_baslama_tarihi") or ""))
    s.dogru("ig: TC hücre ızgarasından okundu, sağlaması tuttu", tc_gecerli(ig.get("tc")))
    s.dogru("ig: meslek adı ve kodu birlikte çıktı", "-" in (ig.get("meslek") or ""))
    s.kontrol("ig: uyarısız", kayitlar["ise_giris_bildirgesi"]["uyarilar"], [])

    ia = kayitlar.get("isten_ayrilis_bildirgesi", {}).get("alanlar", {})
    s.dogru("ia: ayrılış tarihi ISO", re.fullmatch(ISO, ia.get("ayrilis_tarihi") or ""))
    s.dogru("ia: ayrılış nedeni kodu sayı", (ia.get("ayrilis_nedeni_kodu") or "").isdigit())
    s.dogru("ia: TC sağlaması tuttu", tc_gecerli(ia.get("tc")))
    s.kontrol("ia: uyarısız", kayitlar["isten_ayrilis_bildirgesi"]["uyarilar"], [])
    s.kontrol("ig ve ia aynı sigortalıyı gösteriyor", ig.get("tc"), ia.get("tc"))

    t = kayitlar.get("isyeri_tescil", {}).get("alanlar", {})
    s.dogru("tescil: sicil no taşan satırla birleşti (9 bölüm)",
            len((t.get("sicil_no") or "").split()) == 9)
    s.dogru("tescil: ünvan değer taşmasıyla birleşti (60 karakter)",
            len(t.get("unvan") or "") == 60)
    s.dogru("tescil: kanun kapsamına alınış ISO",
            re.fullmatch(ISO, t.get("kanun_kapsamina_alinis") or ""))
    s.dogru("tescil: iş kolu kodu tam sayfa genişliğinde okundu",
            (t.get("is_kolu_kodu") or "").endswith("hariç)"))
    s.dogru("tescil: e-posta satır kırılması kapandı",
            re.fullmatch(r"\S+@\S+\.\S+", t.get("eposta") or ""))
    s.dogru("tescil: 60 karakter kırpma uyarısı verildi",
            any("60 karakter" in u for u in kayitlar["isyeri_tescil"]["uyarilar"]))

    h = kayitlar.get("hizmet_dokumu", {})
    s.kontrol("hizmet dökümü: satır sayısı", len(h.get("satirlar", [])), 270)
    s.kontrol("hizmet dökümü: uyarısız", h.get("uyarilar"), [])
    kayit = [x for x in h.get("satirlar", []) if x["sgrt_kolu"] != "TOPLAM"]
    # Belgenin kendi beyanı: "Toplam 4a Uzun Vade PÖGS : 8103"
    s.kontrol("hizmet dökümü: Asıl gün toplamı belgedeki 8103 ile aynı",
              sum(int(x["gun"] or 0) for x in kayit if x["belge_turu"] == "Asıl"), 8103)
    s.dogru("hizmet dökümü: son kayıtta çıkış tarihi var", kayit[-1]["cikis_tarihi"])

    taranmis = [k for k in kayitlar.values() if k["tur"] is None]
    s.dogru("taranmış belge tanınmadı ama uyarıyla işaretlendi",
            taranmis and any("metin katmanı yok" in u for u in taranmis[0]["uyarilar"]))

    if BEKLENEN:
        for tur in ("ise_giris_bildirgesi", "isten_ayrilis_bildirgesi", "isyeri_tescil"):
            s.kontrol(f"{tur}: tüm alanlar beklenenle aynı",
                      kayitlar[tur]["alanlar"], BEKLENEN["eski_sistem"][tur])
    return s
