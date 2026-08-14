"""Çapraz doğrulamanın gerçekten ateşlendiğini gösteren negatif testler.

Hiç uyarı üretmeyen bir doğrulayıcı, olmayan doğrulayıcıdan daha tehlikelidir:
kontrol edildiği izlenimi verir. Bu yüzden her kontrolün bozuk veriyle
uyarı ürettiği ayrıca sınanıyor.
"""
from yardim import Sonuc
from core.capraz import dogrula


# Sentetik veri: TC'ler sağlama algoritmasını geçer ama gerçek kişiye ait
# değildir. Gerçek belgelerden çıkan değerler ornek_veri/ altında kalır.
def _case(tc="10000000078", ad="ALİ VELİ", sicil="2 0000 01 01 1000000 027 09-51",
          unvan="ÖRNEK LOJİSTİK NAKLİYAT TAŞIMACILIK SANAYİ VE TİCARET LİMİ"):
    return {"sigortalilar": [{"ad_soyad": ad, "tc": tc}],
            "isveren": {"unvan": unvan, "sicil_no": sicil}}


def _belgeler(tc="10000000078", ad="ALİ", soyad="VELİ",
              sicil="2 0000 1 1 1000000 27 9 9 0", giris="2023-03-27", cikis="2024-03-02",
              unvan="ÖRNEK LOJİSTİK NAKLİYAT TAŞIMACILIK SANAYİ VE TİCARET"):
    return [
        {"tur": "ise_giris_bildirgesi", "alanlar": {
            "tc": tc, "ad": ad, "soyad": soyad, "isyeri_sicil_hucreler": sicil,
            "isveren_unvan": unvan, "ise_baslama_tarihi": giris}, "satirlar": []},
        {"tur": "isten_ayrilis_bildirgesi", "alanlar": {
            "tc": tc, "ad": ad, "soyad": soyad, "isyeri_sicil_hucreler": sicil,
            "isveren_unvan": unvan, "ayrilis_tarihi": cikis}, "satirlar": []},
    ]


def calistir():
    s = Sonuc("capraz — uyumsuzluk yakalama (negatif testler)")

    s.kontrol("tutarlı veri uyarı üretmez", dogrula(_case(), _belgeler()), [])

    s.dogru("TC uyuşmazlığı yakalanır",
            any("TC" in u for u in dogrula(_case(), _belgeler(tc="10000000146"))))
    s.dogru("ad-soyad uyuşmazlığı yakalanır",
            any("adı" in u for u in dogrula(_case(), _belgeler(ad="HASAN"))))
    s.dogru("sicil uyuşmazlığı yakalanır",
            any("sicil" in u for u in dogrula(_case(), _belgeler(sicil="2 0000 1 1 9999999 27 9 9 0"))))
    s.dogru("ünvan uyuşmazlığı yakalanır",
            any("ünvan" in u for u in dogrula(_case(), _belgeler(unvan="BAŞKA BİR ŞİRKET LTD"))))
    s.dogru("ayrılış tarihi girişten önceyse yakalanır",
            any("önce" in u for u in dogrula(_case(), _belgeler(cikis="2022-01-01"))))

    # Kırpma farkı uyumsuzluk DEĞİL: kurum sistemi ünvanı farklı yerlerde
    # farklı uzunlukta kesiyor, kısası uzunun başlangıcıysa aynı işverendir.
    s.kontrol("kırpılmış ünvan yanlış alarm vermez",
              [u for u in dogrula(_case(), _belgeler(unvan="ÖRNEK LOJİSTİK NAKLİYAT")) if "ünvan" in u],
              [])
    # Aynı sicil üç ayrı biçimde yazılıyor; biçim farkı uyumsuzluk sayılmamalı
    s.kontrol("sicil biçim farkı yanlış alarm vermez",
              [u for u in dogrula(_case(sicil="2 0000 01 01 1000000 027 09-51 000 001"),
                                  _belgeler()) if "sicil" in u], [])
    return s
