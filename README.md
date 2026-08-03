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
 7. En-iyi-pencere seçimi: kaynak Shorts sınırından (60s) uzunsa,      │
    kesim adaylarından en çok vurgu içerenler seçilir — kronolojik    │
    ilk değil, en "hareketli" bölüm                                  │
 8. Kural tabanlı vurgu tespiti (ses tepe noktaları + Türkçe          │
    ünlem kelimeleri) + efektler (parlama/kontrast, metin çıkartma)  │
 9. Whisper'ın kelime zaman damgalarıyla senkron, kelime kelime      │
    vurgulanan alt yazı ("TikTok tarzı") — ffmpeg/libass ile yakılır│
10. Yerel müzik kütüphanesi: ruh haline göre seçim + sidechain        │
    ducking ile otomatik miksaj                                      │
        │                                                            │
        ▼                                                            │
storage/output/*.mp4  +  otomatik başlık/açıklama/etiket              │
        │                                                            │
        ▼                                                            │
   [ İNCELEMEYE HAZIR ]  ← web/ntfy/Windows bildirimi ──────────────┘
        │
        │  (SİZ "Onayla ve Yükle" butonuna basana kadar burada bekler —
        │   evden uzaktaysanız Tailscale üzerinden telefonunuzdan da)
        ▼
YouTube Data API v3 (Shorts, Made for Kids işaretli)
```

Hiçbir aşama ücretli bir API'ye bağlı değildir. YouTube Data API v3 ücretsiz
kotasıyla, Google Drive API ücretsiz kotasıyla çalışır. Uzaktan erişim
(Tailscale), bildirimler (ntfy.sh) ve sohbet arayüzündeki yapay zeka (Ollama)
da tamamen ücretsiz/açık kaynak.

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

```bash
.venv\Scripts\python.exe scripts\build_music_library.py
```

Bu, [Incompetech](https://incompetech.com/music/royalty-free/) (Kevin
MacLeod) kataloğundan, korku/karanlık temalar hariç tutularak çocuk kanalına
uygun, ruh haline göre etiketlenmiş ~32 parçayı otomatik indirir (CC BY 4.0,
API anahtarı gerektirmez). Elle eklemek isterseniz
[music_library/README.md](music_library/README.md)'ye bakın.

### Uzaktan erişim (evde değilken telefonunuzdan)

1. [Tailscale](https://tailscale.com)'i bu bilgisayara kurun, kendi
   hesabınızla giriş yapın (`tailscale up`).
2. Aynı hesapla telefonunuza da Tailscale uygulamasını kurup giriş yapın.
3. `.env` içinde `WEB_HOST`'u bu bilgisayarın Tailscale IP'sine ayarlayın
   (`tailscale ip -4` ile öğrenilir) — **asla `0.0.0.0` yapmayın**, bu ev
   WiFi'ınızdaki her cihaza da açar.
4. `WEB_AUTH_USERNAME` / `WEB_AUTH_PASSWORD`'ü mutlaka doldurun — bu uygulama
   YouTube'a yükleme onaylayabildiği ve özel aile videosu gösterdiği için,
   birden fazla cihazın erişebildiği an şifresiz kalmamalı.
5. Telefonunuzdan `http://<tailscale-ip>:8765` adresine gidin.

### Bildirimler (telefonunuza, her yerden)

Windows bildirimi sadece bilgisayar başındayken görünür. Her yerden bildirim
almak için ücretsiz, hesap gerektirmeyen [ntfy.sh](https://ntfy.sh) kullanılır:

1. `.env` içinde `NTFY_TOPIC`'e rastgele, tahmin edilemez bir isim yazın
   (şifre gibi düşünün — bu konuyu bilen herkes bildirimlerinizi okuyabilir).
2. Telefonunuza [ntfy uygulamasını](https://ntfy.sh/#subscribe) kurun, aynı
   konuya (topic) abone olun.

### Sohbetle talimat verme (`/chat`)

Video adını (ya da bir parçasını) ve ne istediğinizi serbest metinle yazıp
gönderin — sistem hangi videodan bahsettiğinizi ve ne yapmasını istediğinizi
anlamaya çalışır, bulur, işler, hazır olunca bildirim gönderir. Bunun için
[Ollama](https://ollama.com) (ücretsiz, bu bilgisayarda çalışan yerel yapay
zeka, API anahtarı gerekmez) kurulu ve `ollama serve` çalışır durumda olmalı:

```bash
winget install Ollama.Ollama
ollama pull qwen2.5:3b-instruct
```

**Not:** Bazı NVIDIA GPU'larda (özellikle eski sürücülü kartlarda) Ollama'nın
CUDA arka ucu çakışabilir. Böyle bir hata alırsanız CPU modunda çalıştırın:

```bash
set OLLAMA_LLM_LIBRARY=cpu
ollama serve
```

Ollama çalışmıyorsa `/chat` otomatik olarak basit anahtar kelime eşleştirmeye
düşer (bkz. Özel talimatlar) — hiçbir zaman tamamen bozulmaz, sadece daha az
esnek olur.

Video, dosya adında geçmeyen bir şeyle tarif edilirse (telefon kamerası
dosyaları genelde `20260724_213117.mp4` gibi anlamsız isimlerle gelir) ve
daha önce hiç işlenmediyse bulunamaz — ilk seferde ya Drive'da dosyayı
tanıyacağınız bir isimle yeniden adlandırın, ya da panelden elle seçin.

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
- **Sohbet** (`/chat`, mobil uyumlu): video adı + serbest talimat yazıp
  gönderme, geçmiş mesaj/sonuç listesi.
- **Video detayı** (`/video/{id}`): önizleme oynatıcı, üretilen başlık/açıklama/
  etiketler, video başına özellik açma/kapama (sessizlik kesimi, yüz takibi,
  müzik, efektler, alt yazı), serbest metin özel talimat kutusu, **"Onayla ve
  Yükle"** butonu (sadece video hazır olduğunda görünür).
- **Ayarlar** (`/settings`): Drive klasör ID'si, kanal geneli varsayılan
  özellikler, Made for Kids varsayılanı, YouTube gizlilik/kategori.

Şifre korumalıysa (bkz. Uzaktan erişim) her sayfa `WEB_AUTH_USERNAME`/
`WEB_AUTH_PASSWORD` ister.

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

## Depolama alanı

Video işleme her aşamada ara dosya üretir (tonemap, kesim, kırpma, efekt,
alt yazı, müzik) — birkaç dakikalık 4K bir kaynak, `storage/working/` içinde
tek başına birkaç GB tutabilir. SSD'de yer darsa, `storage/` klasörünü daha
büyük bir diske taşıyıp yerine bir **NTFS junction** koymak işe yarar (kod
hiçbir path değişikliği gerektirmeden şeffaf çalışır):

```powershell
# Sunucuyu durdurun, sonra:
robocopy "C:\...\kirpinator\storage" "D:\hedef\storage" /E /MOVE
Remove-Item "C:\...\kirpinator\storage" -Recurse -Force
New-Item -ItemType Junction -Path "C:\...\kirpinator\storage" -Target "D:\hedef\storage"
```

Kod, veritabanı ve `.venv`'i SSD'de bırakıp sadece `storage/`'ı taşımak
önerilir — küçük ama sık erişilen dosyalar (özellikle SQLite) SSD'nin hız
avantajından faydalanır, video dosyaları ise büyük ama çoğunlukla sıralı
(sequential) okuma/yazma olduğu için normal bir HDD'de de sorunsuz çalışır.

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
  db.py, models.py      SQLite kalıcılık (videos, job_events, chat_messages), veri sınıfları
  settings_store.py      çalışma zamanında değiştirilebilir ayarlar
  drive/                 Drive OAuth + indirme + isimle arama (find_video_by_name)
  youtube/                YouTube OAuth (drive/auth.py ile ortak), metadata, yükleme
  pipeline/                probe, transcribe, silence, segment_planner (en-iyi-pencere
                             seçimi dahil), cutter, face_tracker, crop_render,
                             highlight_detector, effects, captions, music,
                             llm_instructions (Ollama tabanlı sohbet ayrıştırma),
                             pipeline.py (orkestratör)
  jobs/                     arka plan işçisi (hata durumunda çökmez, devam eder), bildirimler
  web/                      FastAPI + Jinja2 arayüzü (Basic Auth destekli)
music_library/               scripts/build_music_library.py ile doldurulur
scripts/                      build_music_library.py, fetch_pixabay_music.py
storage/                       incoming / working / output / thumbnails
tests/                          saf mantık birim testleri
```

## Bilinen sınırlamalar / geliştirmeye açık

- Vurgu/efekt tespiti kural tabanlı (ses tepe noktası + Türkçe ünlem
  kelimeleri); istenirse öğrenilmiş bir modelle değiştirilebilir —
  `app/pipeline/highlight_detector.py`'deki `Highlight` arayüzü sabit
  tutulduğu sürece geri kalan pipeline'ı etkilemez.
- Pixabay üzerinden otomatik müzik indirme, Pixabay'in genel API'sinde stabil
  bir müzik-arama uç noktası olmadığı için şu an manuel indirmeye yönlendiriyor
  (bkz. `scripts/fetch_pixabay_music.py`) — asıl müzik kaynağı artık
  `scripts/build_music_library.py` (Incompetech).
- Çok uzun (onlarca dakikalık) kaynak videolarda Whisper transkripsiyon süresi
  CPU'da uzayabilir; `WHISPER_MODEL_SIZE=tiny` ile hızlandırılabilir.
- 4K HDR kaynaklarda tonemap adımı (özellikle CPU'da) yavaş olabilir; birkaç
  dakikalık 4K video için 10-20 dakika normaldir.
- `/chat`'teki 3B'lik yerel model küçük olduğu için mükemmel değil — bazen
  istenmeyen bir özelliği de değiştirebilir. Kritik bir video için sonucu
  video detay sayfasından kontrol edip gerekirse elle düzeltin.
- `/chat` bir videoyu ancak dosya adında veya (daha önce işlendiyse)
  başlığında/açıklamasında geçen bir kelimeyle bulabilir — telefon kamerası
  dosya adları (`20260724_213117.mp4`) tarif ettiğiniz içerikle örtüşmez.
