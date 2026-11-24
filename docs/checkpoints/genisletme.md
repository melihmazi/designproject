# Genişletme Modülleri            Tarih: 2026-11-24

Ortak kural korundu: modüller `extensions/` altında yaşar, çekirdeğin envanterini, üretilen config'lerini ve raporlarını
girdi olarak kullanır. Çekirdekte tek değişiklik, karşılaştırma mantığının `core/scripts/confcheck.py`'ye alınmasıdır
(hem `deploy.py`'nin basış sonrası doğrulaması hem sapma modülü onu kullanır).

| # | Modül | Durum | Kabul kriteri (yol haritası) | Gerçek sonuç |
|---|---|---|---|---|
| 3 | pytest test katmanı | Tamam | Tüm testler yeşil; kablo çıkarınca kırmızı | 33 çevrimdışı + 6 canlı test geçti; kırmızı durum `validate.py` üzerinden Faz 5'te gösterildi |
| 2 | Config sapma raporu | Tamam (NAPALM'sız) | Elle eklenen açıklama raporda görünür | 13 gerçek config uyumlu; kasıtlı 4 değişikliğin 4'ü yakalandı; ayrıca iki gerçek hatayı kendiliğinden buldu |
| 7 | Güvenlik sertleştirme | Kısmen | Kaçak DHCP ve MAC taşması engellenir | Config 9 cihazda hatasız, ağ çalışmaya devam etti; **saldırı testleri yapılmadı** |
| 4 | Git tabanlı config geçmişi | Tamam | `git log -p` ile cihaz geçmişi | 7 yedek commit'lendi; `git log -p -- MRK-DAG2.cfg` elle eklenen satırı gösteriyor |
| 8 | Web panosu | Tamam (Flask'sız) | Yeşil/kırmızı cihaz kartları | `reports/dashboard.html` üretiliyor; `--serve` ile localhost:5000 |
| 1 | Ansible katmanı | Yapılmadı | — | Ansible kontrol düğümü Windows'ta çalışmaz; WSL ya da Linux gerekir |
| 5 | İzleme (LibreNMS/Zabbix) | Yapılmadı | — | Ayrı VM/Docker ve tam topoloji ister |
| 6 | IPv6 dual-stack | Yapılmadı | — | Zaman ayrılmadı |

## 3 — pytest (`extensions/tests`)
- **Çevrimdışı (33 test, cihaz gerekmez):** envanter tutarlılığı (13 cihaz, benzersiz konsol portu / router-id / IP, link uçları çakışmıyor, her /30 tam iki uçta, HSRP 4+3, OSPF beklentisi simetrik, STP kökü = HSRP active), şablon kuralları (Faz 1 IP silmiyor, açıklama `no switchport`'tan sonra, stub tanımı tünelden önce) ve **ACL politika matrisi**.
- **ACL matrisi:** küçük bir ACL değerlendiricisi şablondan üretilen ACL'leri okur, isteği ve dönüş paketini kaynak SVI giriş ACL'inden ve hedef SVI çıkış ACL'inden geçirir. Yol haritası Bölüm 12.3'teki A1–A12 ve 6 ek durum (toplam 18) sınanıyor. Tam topoloji olmadan politika doğrulamasının yolu bu oldu.
- **Canlı (6 test):** `--live` ile `validate.py`'yi çalıştırır; erişim, CDP, EtherChannel, OSPF, HSRP, tünel grupları ayrı testlerdir.

## 2 — Sapma raporu (`extensions/drift`)
NAPALM kullanılmadı: IOS sürücüsü SSH/SCP ister, bu projede yönetim yolu konsol telnet (yol haritası U6). Yerine şablon çıktısı ile yedek karşılaştırılıyor. IOS'un komutları farklı yazmasına karşı normalizasyon var (port adları `80 → www`, `interface range` açılımı, `portfast → portfast edge`, varsayılan satırlar).
Kendiliğinden bulduğu gerçek hatalar: SNR-RTR'da eksik `area 300 stub no-summary` ve routed Port-channel'larda kaybolan açıklamalar (`faz6.md`, bulgu 1 ve 4).

## 7 — Güvenlik sertleştirme (`extensions/security-hardening`)
- Erişim switch'leri: Port Security (sticky, en çok 2 MAC, `restrict`), DHCP Snooping (uplink'ler trusted, Option 82 kapalı), uç portlarda DHCP hız sınırı, kullanılmayan portlar kapalı.
- OSPF cihazları: transit arayüzlerde MD5 kimlik doğrulama. Anahtar `NET_OSPF_KEY` ortam değişkeninden gelir, diske maskeli yazılır.
- `--rollback` şablonları yazıldı ama **canlı denenmedi**.
- Bilerek dışarıda bırakılanlar: native VLAN değişikliği (tüm trunk'larda eşzamanlı yapılmalı), DAI (statik IP'li uçlar ARP ACL ister), 802.1X (VPCS desteklemez).
- Kabul kriterindeki kaçak DHCP sunucusu ve MAC taşması testleri için saldırgan rolünde bir uç gerekir; yapılmadı.

## 4 — Config geçmişi (`extensions/config-history`)
Yalnızca maskelenmiş yedekler alınır; depo yereldir, hiçbir yere gönderilmez. Her yedek klasörü, hangi cihazların değiştiğini söyleyen ayrı bir commit olur.

## 8 — Pano (`extensions/dashboard`)
Flask yerine standart kütüphane kullanıldı (tek sayfa, salt okunur). Sağlık raporu kartları ve sapma özeti aynı sayfada; açık ve koyu tema destekli. Sayfa tarayıcıda görsel olarak kontrol edilmedi; HTML yapısı betikle doğrulandı.
