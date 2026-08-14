from yardim import Sonuc
from core.metin import anahtarla, ondalik, tarih_bul, tarih_iso, tc_gecerli


def calistir():
    s = Sonuc("metin — tarih / sayı / TC")

    s.kontrol("27/03/2023 -> ISO", tarih_iso("27/03/2023")[0], "2023-03-27")
    s.kontrol("26.11.1976 -> ISO", tarih_iso("26.11.1976")[0], "1976-11-26")
    s.kontrol("zaten ISO", tarih_iso("2024-03-15")[0], "2024-03-15")
    # Eski projenin regex'i 32.13.2024'ü kabul ediyordu; sessizce yanlış dönmek yasak
    s.kontrol("takvimde olmayan tarih None döner", tarih_iso("32.13.2024")[0], None)
    s.dogru("... ve uyarı üretir", tarih_iso("32.13.2024")[1])
    s.kontrol("belge sayısını tarih sanmaz", tarih_bul("Sayı: E-91953272-03")[0], None)
    s.kontrol("satırdaki son tarih", tarih_bul("E-9195-03 15.03.2024", mod="son")[0], "2024-03-15")

    # Gerçek belgelerde iki ayraç düzeni de var: hizmet dökümü ABD, rapor TR
    s.kontrol("204,000,000.00 (hizmet dökümü)", str(ondalik("204,000,000.00")[0]), "204000000.00")
    s.kontrol("20.002,50 (TR)", str(ondalik("20.002,50")[0]), "20002.50")
    s.kontrol("666.75", str(ondalik("666.75")[0]), "666.75")
    s.dogru("1.234 belirsiz -> uyarı", ondalik("1.234")[1])

    s.dogru("sağlaması geçerli TC kabul edilir", tc_gecerli("10000000078"))
    s.dogru("uydurma TC reddedilir", not tc_gecerli("12345678901"))
    s.dogru("0 ile başlayan TC reddedilir", not tc_gecerli("00000000078"))
    s.kontrol("anahtarla Türkçe katlar", anahtarla("İşyeri Ünvanı"), "isyeri unvani")
    return s
