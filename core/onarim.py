"""
onarim.py — Excel'in sessizce bozduğu değerleri geri kazanma.

Denetim listesindeki iki gerçek bozulma:
  * Yazı Tarihi  -> 45369.0        (seri tarih numarası, metin değil)
  * Yazı Sayısı  -> 9.2063506E+07  (uzun sayı bilimsel gösterime dönmüş)

Her fonksiyon (değer, uyarı) döndürür. Uyarı None değilse çağıran taraf
bunu case.json'daki "uyarilar" listesine yazar; sessizce tahmin etmeyiz.
"""
from datetime import date, timedelta

# Excel 1900 tarih sistemi: 1900'ü artık yıl sanan hata yüzünden
# referans 31.12.1899 değil 30.12.1899 alınır.
_EXCEL_EPOK = date(1899, 12, 30)


def seri_tarih(deger, *, alan: str = "tarih") -> tuple[str | None, str | None]:
    """Excel seri tarih numarasını ISO tarihe çevirir. Zaten metinse dokunmaz."""
    if deger is None or deger == "":
        return None, None

    if isinstance(deger, str):
        return deger.strip(), None

    try:
        seri = int(float(deger))
    except (TypeError, ValueError):
        return None, f"{alan}: sayıya çevrilemedi ({deger!r})"

    # 60 = Excel'in var olmayan 29.02.1900'ü; altındaki değerler güvenilmez.
    if seri < 61 or seri > 80000:
        return None, f"{alan}: seri tarih aralık dışı ({seri})"

    return (_EXCEL_EPOK + timedelta(days=seri)).isoformat(), None


def uzun_sayi(deger, *, alan: str = "sayı") -> tuple[str | None, str | None]:
    """Bilimsel gösterime dönmüş tam sayıyı metin olarak geri verir.

    float 15 anlamlı basamaktan fazlasını taşıyamaz; o eşiği aşan değerlerde
    geri dönüş kesin olmadığı için uyarı üretilir.
    """
    if deger is None or deger == "":
        return None, None

    if isinstance(deger, str):
        return deger.strip(), None

    try:
        f = float(deger)
    except (TypeError, ValueError):
        return None, f"{alan}: sayıya çevrilemedi ({deger!r})"

    if f != int(f):
        return str(deger).strip(), f"{alan}: tam sayı değil ({deger!r})"

    metin = str(int(f))
    if len(metin) > 15:
        return metin, f"{alan}: 15 basamağı aşıyor, float hassasiyeti kaybolmuş olabilir ({metin})"
    return metin, None
