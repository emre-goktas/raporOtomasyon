"""Excel'in sessiz bozmalarının geri alınması (Faz 1)."""
from yardim import Sonuc
from core.onarim import seri_tarih, uzun_sayi


def calistir():
    s = Sonuc("onarim — Excel'in sessiz bozmaları")
    s.kontrol("45366 -> 15.03.2024 (UDF ile doğrulandı)", seri_tarih(45366.0)[0], "2024-03-15")
    s.kontrol("45292 -> 01.01.2024 (bilinen Excel çıpası)", seri_tarih(45292.0)[0], "2024-01-01")
    s.kontrol("metin dokunulmaz", seri_tarih("15/03/2024")[0], "15/03/2024")
    s.kontrol("None", seri_tarih(None)[0], None)
    s.dogru("aralık dışı uyarır", seri_tarih(5.0)[1])

    s.kontrol("9.2063506E7", uzun_sayi(9.2063506e7)[0], "92063506")
    s.kontrol("9.2029814E7", uzun_sayi(9.2029814e7)[0], "92029814")
    s.kontrol("metin dokunulmaz", uzun_sayi("E-89442903-204")[0], "E-89442903-204")
    s.kontrol("None", uzun_sayi(None)[0], None)
    return s
