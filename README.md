# SigortaOtomasyonu

SGK müfettiş rapor otomasyonu. Çekirdek boru hattı iş türünden bağımsız;
her iş türü `domains/<ad>/` altında kendi belge listesi, çıkarım kuralları,
kural seti ve rapor şablonuyla tanımlanır.

    çekirdek:  iş oluştur → belge topla → sınıflandır → çıkar → kural işlet → rapor render
    domain:    hangi belgeler / hangi alanlar / hangi kurallar / hangi şablon

İlk domain: `is_kazasi`.
