# Müzik kütüphanesi

Bu klasör, videolara otomatik eklenecek telif sorunu olmayan müzikleri barındırır.

**Şu an 32 parça hazır** (her mod için 8): `scripts/build_music_library.py` ile
[Incompetech](https://incompetech.com/music/royalty-free/) (Kevin MacLeod)
katalogundan, korku/karanlık/hüzünlü temalar hariç tutularak, çocuk kanalına
uygun şekilde otomatik seçilip indirildi. Tamamı **CC BY 4.0** (atıfla serbest
kullanım) — dosya başına gerekli atıf metni zaten `index.json` içinde
`attribution` alanında hazır duruyor, sistem bunu kullanmıyor ama video
açıklamasına eklemek istersen oradan alabilirsin.

Daha fazla/başka parça eklemek istersen `scripts/build_music_library.py`'yi
tekrar çalıştırabilir (farklı `TARGET_PER_MOOD` ile) ya da aşağıdaki gibi elle
ekleyebilirsin.

## Format

`index.json` şu şekilde bir liste olmalı:

```json
[
  {
    "file": "playful_01.mp3",
    "mood": "playful",
    "bpm": 110,
    "license": "YouTube Audio Library - no attribution required",
    "attribution": ""
  }
]
```

Geçerli `mood` değerleri: `playful`, `funny`, `exciting`, `calm` (kod bunlardan
birini transkriptten otomatik seçer; eşleşme yoksa `playful` varsayılır).

## Ücretsiz kaynaklar (öneri sırası)

1. **YouTube Audio Library** (studio.youtube.com > Audio Library) — YouTube'un
   kendi kanalınıza yükleyeceğiniz videolar için en güvenli seçenek; API'si
   olmadığı için indirme tarayıcıdan tek tek yapılır, bu depoya kopyalayıp
   `index.json`'a satır eklemeniz gerekir (tek seferlik manuel adım).
2. **Pixabay Music** (pixabay.com/music) — ücretsiz ve ücretsiz API anahtarı ile
   programatik indirilebilir. `.env` içine `PIXABAY_API_KEY` eklerseniz
   `scripts/fetch_pixabay_music.py` bu klasöre otomatik indirir ve
   `index.json`'a ekler.

Sistem hiçbir ücretli müzik API'sine bağlanmaz.
