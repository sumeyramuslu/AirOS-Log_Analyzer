# AirOS Log Analyzer

PowerBeam ve Rocket M5 cihazlarından alınan AirOS 8 log dosyalarını analiz eden, Türkçe açıklamalar ve görsel dashboard sunan Python uygulaması.

## Özellikler

- **Log dosyası yükleme** — `.txt` / `.log` dosyalarını sürükle-bırak veya menüden seç
- **Cihazdan log alma** — IP adresi ile SSH/HTTP üzerinden log çekme
- **Satır satır Türkçe açıklama** — Her log kaydı için anlaşılır Türkçe açıklama
- **Olay sınıflandırma** — Reboot, Ethernet Down/Up, DHCP, Login, DFS, Radar vb.
- **Grafikler** — Olay dağılımı, zaman çizelgesi (hata/uyarı), en sık olaylar
- **Olası sorunlar** — Otomatik değerlendirme ve öneriler
- **Boş başlangıç** — Uygulama açıldığında veri yok, log yüklenince dolar

## Kurulum

```bash
cd C:\Users\rumey\Projects\airos-log-analyzer
pip install -r requirements.txt
python app.py
```

Tarayıcıda açın: **http://127.0.0.1:5000**

## Kullanım

1. Sol menüden **Log Dosyası Yükle** ile `.txt` dosyası seçin
2. Veya **Cihazdan Log Al** ile IP adresi girin (varsayılan: ubnt/ubnt)
3. Dashboard'da özet, grafikler, tablo ve olası sorunları inceleyin
4. Tabloda arama/filtre ile INFO, WARNING, ERROR kayıtlarını ayırın

## Desteklenen Olay Türleri

Reboot, Ethernet Down/Up, DHCP, Authentication, Deauthentication, DFS, Radar, NTP, Login, Login Failed, Wireless Disconnect, Link Down/Up, DFS CAC, Channel Change, Signal Problems

## Cihazdan Log Alma

SSH (port 22) veya HTTP üzerinden log çekilir. Cihazda SSH aktif olmalıdır. Varsayılan kimlik bilgileri: `ubnt` / `ubnt`
