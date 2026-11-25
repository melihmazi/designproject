# Genişletme Modülleri            Tarih: 2026-11-24

Ortak kural korundu: modüller `extensions/` altında yaşar, çekirdeğin envanterini, üretilen config'lerini ve raporlarını
girdi olarak kullanır. Çekirdekte tek değişiklik, karşılaştırma mantığının `core/scripts/confcheck.py`'ye alınmasıdır
(hem `deploy.py`'nin basış sonrası doğrulaması hem sapma modülü onu kullanır).

| # | Modül | Durum | Kabul kriteri (yol haritası) | Gerçek sonuç |
|---|---|---|---|---|
| 3 | pytest test katmanı | Tamam | Tüm testler yeşil; kablo çıkarınca kırmızı | 47 çevrimdışı + 6 canlı test geçti; kırmızı durum `validate.py` üzerinden Faz 5'te gösterildi |
| 2 | Config sapma raporu | Tamam (NAPALM'sız) | Elle eklenen açıklama raporda görünür | 13 gerçek config uyumlu; kasıtlı 4 değişikliğin 4'ü yakalandı; ayrıca iki gerçek hatayı kendiliğinden buldu |
| 7 | Güvenlik sertleştirme | Tamam | Kaçak DHCP ve MAC taşması engellenir | 13 cihazda hatasız; kaçak DHCP ve MAC taşması önce gösterildi, sonra engellendi; `--rollback` canlıda geçti |
| 4 | Git tabanlı config geçmişi | Tamam | `git log -p` ile cihaz geçmişi | 7 yedek commit'lendi; `git log -p -- MRK-DAG2.cfg` elle eklenen satırı gösteriyor |
| 8 | Web panosu | Tamam (Flask'sız) | Yeşil/kırmızı cihaz kartları | `reports/dashboard.html` üretiliyor; `--serve` ile localhost:5000; tarayıcıda görsel kontrol edildi |
| 1 | Ansible katmanı | Tamam | İkinci çalıştırmada changed=0 | QEMU'daki Alpine kontrol düğümünden 12 cihaz: changed=0, elle bozulan 3 ayar düzeltildi, yine changed=0 |
| 5 | İzleme | Tamam (LibreNMS'siz) | Link düşünce alarm | SNMP v2c ile 13/13 cihaz; link kapatınca alarm ve olay kaydı, açınca alarm kalkıyor; pano bölümü var |
| 6 | IPv6 dual-stack | Tamam | Uçlar IPv6 ile haberleşir | OSPFv3 14 komşuluk, SLAAC, IPv6 ACL, tünel üzerinden IPv6; geri alma temiz |

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
- `--rollback` canlıda 13 cihazda denendi. İlk denemede DHCP snooping kapanmadı (şablon hatası); düzeltildi, ayrıntı `tam-topoloji.md`.
- Bilerek dışarıda bırakılanlar: native VLAN değişikliği (tüm trunk'larda eşzamanlı yapılmalı), DAI (statik IP'li uçlar ARP ACL ister), 802.1X (VPCS desteklemez).
- Kaçak DHCP sunucusu ve MAC taşması testleri `lab/hosts.py` ile yapıldı; sonuç tablosu `tam-topoloji.md`'de.

## 4 — Config geçmişi (`extensions/config-history`)
Yalnızca maskelenmiş yedekler alınır; depo yereldir, hiçbir yere gönderilmez. Her yedek klasörü, hangi cihazların değiştiğini söyleyen ayrı bir commit olur.

## 8 — Pano (`extensions/dashboard`)
Flask yerine standart kütüphane kullanıldı (tek sayfa, salt okunur). Sağlık raporu kartları ve sapma özeti aynı sayfada; açık ve koyu tema destekli. Sayfa tarayıcıda kontrol edildi (13 kart, sapma özeti, canlı izleme tablosu).

## 1, 5, 6 — Ansible, izleme, IPv6
Üçü de 13 cihazlı tam topolojide canlı denendi. Tasarım kararları ve ölçümler `tam-topoloji.md`'de.
- **Ansible:** çekirdeğin yerine geçmez; Faz 1–2 hedefini deklaratif tarif eder ve `deploy.py` ile aynı sonuca vardığını gösterir.
- **İzleme:** LibreNMS/Zabbix yerine tek dosyalık SNMP yoklayıcı. Ayrı sunucu istemez, pano ile aynı raporu besler.
- **IPv6:** çekirdek envanterine dokunmaz; adres planı `extensions/ipv6/plan.yaml`. `--rollback` ile tümüyle kaldırılır.
