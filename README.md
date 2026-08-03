# Kirpinator ✂️

**Yağmurun Oyun Bahçesi** YouTube kanalı için uçtan uca, tamamen ücretsiz/açık
kaynak araçlarla çalışan otomatik video editleme ve yayınlama aracı.

Google Drive'a düşen ham telefon çekimlerini otomatik alır; konuşmayı yazıya
döker, sessiz/boş anları **cümle ortasından kesmeden** çıkarır, Yağmur'u
kadrajda tutacak şekilde yüz takipli otomatik kırpma yapar, telif sorunu
olmayan müzik ve basit kural tabanlı vurgu efektleri ekler; hazır olan videoyu
**siz onaylamadan** YouTube'a yüklemez.

## Neden bu isim

"Kırpmak" (cut/crop) fiilinden geliyor — aracın yaptığı iki temel şey de bu:
gereksiz kısımları kırpmak, kadrajı kırpmak.

## Mimari

```
Google Drive (kaynak klasör)
        │  (otomatik tarama, OAuth)
        ▼
storage/incoming/  ──────────────────────────────────────────────┐
        │                                                        │
        ▼                                                        │
 1. ffprobe:  format/yön/HDR/fps tespiti                         │
 2. faster-whisper: cümle bazlı transkript + kelime zaman damgası│
 3. ffmpeg silencedetect: sessizlik aralıkları                   │
 4. segment_planner: sessizlik + transkripti birleştirip          │
    HİÇBİR CÜMLEYİ YARIM BIRAKMADAN kesim planı çıkarır           │
 5. ffmpeg concat: planlı kesim                                   │
 6. MediaPipe FaceDetection: yüz merkezini takip edip yumuşatma  │
    (EMA) + ffmpeg sendcmd: dinamik kadraj/kırpma                 │
 7. Kural tabanlı vurgu tespiti (ses tepe noktaları + Türkçe      │
    ünlem kelimeleri) + basit efektler (parlama, metin çıkartma) │
 8. Yerel müzik kütüphanesi: ruh haline göre seçim + sidechain    │
    ducking ile otomatik miksaj                                  │
        │                                                        │
        ▼                                                        │
storage/output/*.mp4  +  otomatik başlık/açıklama/etiket          │
        │                                                        │
        ▼                                                        │
   [ İNCELEMEYE HAZIR ]  ← web arayüzünde bildirim ─────────────┘
        │
        │  (SİZ "Onayla ve Yükle" butonuna basana kadar burada bekler)
        ▼
YouTube Data API v3 (Shorts, Made for Kids işaretli)
```

Hiçbir aşama ücretli bir API'ye bağlı değildir. YouTube Data API v3 ücretsiz
kotasıyla, Google Drive API ücretsiz kotasıyla çalışır.

## Kurulum

Gereksinim: Python 3.11+, [ffmpeg](https://ffmpeg.org) PATH'te.

```bash
python install.py
```

Bu komut sanal ortam kurar, tüm Python bağımlılıklarını (FastAPI, faster-whisper,
OpenCV, MediaPipe, google-api-python-client...) yükler, ffmpeg'i kontrol eder,
`.env` dosyasını `.env.example`'dan oluşturur ve Whisper modelini önceden indirir.
Hiçbir adımda onay istemez.

Windows'ta `SETUP.bat` dosyasını çift tıklamak da aynı işi yapar.

### Google Drive / YouTube yetkilendirmesi (tek seferlik, sizin tarayıcınızda)

1. [Google Cloud Console](https://console.cloud.google.com)'da bir proje açın,
   **Drive API** ve **YouTube Data API v3**'ü etkinleştirin.
2. **APIs & Services > Credentials > Create Credentials > OAuth client ID >
   Desktop app** ile bir istemci sırrı indirin.
3. İndirilen dosyayı `secrets/google_oauth_client_secret.json` olarak kaydedin.
4. Uygulamayı ilk çalıştırdığınızda tarayıcı otomatik açılır, hesabınızla tek
   seferlik giriş yaparsınız. Token `secrets/google_token.json` içinde saklanır
   ve otomatik yenilenir — bir daha tarayıcı açılmaz.

### Müzik kütüphanesi

`music_library/` klasörü boş gelir (telif nedeniyle içine dosya koyamıyoruz).
Doldurma talimatları için [music_library/README.md](music_library/README.md).

## Çalıştırma

```bash
.venv\Scripts\python.exe run.py
```

veya Windows'ta `START.bat`. Web arayüzü `http://127.0.0.1:8765` adresinde açılır.

Arka planda çalışan işçi (worker) sürekli:
- Drive klasörünü tarar, yeni videoları indirir,
- Kuyruktaki videoları sırayla işler,
- Her video "incelemeye hazır" olduğunda Windows bildirimi gösterir.

## Web arayüzü

- **Panel** (`/`): tüm videolar, durumları, küçük resimleri.
- **Video detayı** (`/video/{id}`): önizleme oynatıcı, üretilen başlık/açıklama/
  etiketler, video başına özellik açma/kapama (sessizlik kesimi, yüz takibi,
  müzik, efektler), serbest metin özel talimat kutusu, **"Onayla ve Yükle"**
  butonu (sadece video hazır olduğunda görünür).
- **Ayarlar** (`/settings`): Drive klasör ID'si, kanal geneli varsayılan
  özellikler, Made for Kids varsayılanı, YouTube gizlilik/kategori.

### Özel talimatlar

Video başına girilen serbest metin, ücretli bir yapay zekaya gönderilmez —
basit anahtar kelime eşleştirmesiyle yorumlanır (örn. "müzik ekleme",
"efektsiz olsun", "made for kids kapalı"). Tanınmayan metin yok sayılmaz,
kayıtlarda görünür kalır; kural listesini genişletmek için
[app/pipeline/instructions.py](app/pipeline/instructions.py) düzenlenir.

## Güvenlik: onaysız yükleme yok

Pipeline hiçbir zaman kendi kendine YouTube'a yüklemez. Bir video işlendiğinde
durumu `ready_for_review` olur ve orada bekler. Yükleme sadece web arayüzünde
insan "Onayla ve Yükle" butonuna bastığında (`app/youtube/upload.py`,
`status != "approved"` ise reddeder) tetiklenir.

## Made for Kids

Kanal geneli varsayılan **açık**tır (`.env` içinde `MADE_FOR_KIDS_DEFAULT=true`,
ayarlar sayfasından da değiştirilebilir). Her video için ayrıca video detay
sayfasından "Kanal varsayılanı / Evet / Hayır" olarak geçersiz kılınabilir.

## Test

```bash
.venv\Scripts\python.exe -m pytest
```

Testler dış bağımlılık gerektirmeyen saf mantık modüllerini kapsar: cümle
sınırını hiç bozmadan kesim planlama, zaman damgası eşleme, anahtar kelime
tespiti, metadata üretimi, özel talimat ayrıştırma.

## Proje yapısı

```
app/
  config.py            ayarlar (.env)
  db.py, models.py      SQLite kalıcılık, veri sınıfları
  settings_store.py      çalışma zamanında değiştirilebilir ayarlar
  drive/                 Drive OAuth + indirme
  youtube/                YouTube OAuth (drive/auth.py ile ortak), metadata, yükleme
  pipeline/                probe, transcribe, silence, segment_planner, cutter,
                             face_tracker, crop_render, highlight_detector,
                             effects, music, pipeline.py (orkestratör)
  jobs/                     arka plan işçisi, bildirimler
  web/                      FastAPI + Jinja2 arayüzü
music_library/               boş, kullanıcı doldurur
scripts/                      yardımcı script'ler (Pixabay müzik, vb.)
storage/                       incoming / working / output / thumbnails
tests/                          saf mantık birim testleri
```

## Bilinen sınırlamalar / geliştirmeye açık

- Vurgu/efekt tespiti v1 kural tabanlı (ses tepe noktası + Türkçe ünlem
  kelimeleri); istenirse öğrenilmiş bir modelle değiştirilebilir —
  `app/pipeline/highlight_detector.py`'deki `Highlight` arayüzü sabit
  tutulduğu sürece geri kalan pipeline'ı etkilemez.
- Pixabay üzerinden otomatik müzik indirme, Pixabay'in genel API'sinde stabil
  bir müzik-arama uç noktası olmadığı için şu an manuel indirmeye yönlendiriyor
  (bkz. `scripts/fetch_pixabay_music.py`); YouTube Audio Library'den elle
  ekleme en güvenilir yol.
- Çok uzun (onlarca dakikalık) kaynak videolarda Whisper transkripsiyon süresi
  CPU'da uzayabilir; `WHISPER_MODEL_SIZE=tiny` ile hızlandırılabilir.
