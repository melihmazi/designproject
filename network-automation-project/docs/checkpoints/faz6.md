# Faz 6 — Yedekleme, Paket Analizi ve Uçtan Uca Doğrulama            Tarih: 2026-11-24

## Ne yapıldı
- `core/scripts/backup.py`: her cihazın `running-config`'ini `backups/YYYY-MM-DD_HHMMSS/<hostname>.cfg` olarak kaydeder. `--diff` önceki yedekle farkı gösterir, `--sanitize` parola satırları maskelenmiş kopya yazar, `--every N` N dakikada bir tekrarlar.
- `core/scripts/pcap_report.py`: pcap dosyalarından LACP, PVST+, HSRP, OSPF, GRE ve DHCP analizini Markdown olarak üretir. Wireshark'ın yerini tutmaz; aynı yakalamanın tekrarlanabilir, metin hâlinde kanıtıdır.
- `core/scripts/confcheck.py`: şablon ↔ running-config karşılaştırması ve **kararlı okuma** (aşağıda).
- `lab/big_test.py`: 13 IOS cihazının 9'u birlikte, uçtan uca senaryo.

## 6-A. Yedekleme — doğrulama
| Deney | Sonuç |
|---|---|
| İki cihaz yedeği, ardından elle tek satır ekleyip yeniden yedek | `MRK-DAG2: önceki yedeğe göre 1 satır değişti` + birleşik fark çıktısı |
| `--sanitize` | `enable secret 5 <MASKELENDI>`, `username admin ... <MASKELENDI>`; asıl dosyada özetler duruyor |
| 9 cihaz birlikte | 9/9 yedeklendi (`backups/2026-11-24_052226`) |

Zamanlama: `backup.py --every 60` ya da Windows Görev Zamanlayıcı ile `python core\scripts\backup.py --sanitize`.

## 6-B. Paket analizi — `docs/captures/`
Yakalamalar GNS3'teki "Start capture" yerine laboratuvarın QEMU `filter-dump` kaydıyla alındı (aynı pcap biçimi; dosyalar Wireshark'ta açılır).

| Dosya | Link | Rapor | Görülen |
|---|---|---|---|
| `L07_*.pcap`, `L08_*.pcap` | DAG1–DAG2 Po2 üyeleri | `analiz_dag.md` | LACP el sıkışması (Defaulted → Sync+Collecting+Distributing), VLAN başına STP kökü, 7 HSRP grubu, Vlan254'te OSPF komşuluk kurulumu |
| `L09_*.pcap` | CORE1 `Gi1/0` – SNR `Gi0/0` | `analiz_L09.md` | Area 0 OSPF Hello/DBD/LSU, DR/BDR 0.0.0.0 (point-to-point) |
| `L11_*.pcap` | SNR `Gi0/2` – ISS `Gi0/0` | `analiz_L11.md` | GRE dış başlık 198.51.100.1 ↔ .6, içinde OSPF Area 300; NAT sonrası 198.51.100.1 kaynaklı ICMP; **GRE içinde DHCP relay** |
| `L13_*.pcap` | FAB-RTR `Gi0/1` – FAB-ERS-1 | `analiz_L13.md` | Tesis LAN'ında istemciye dönen Offer/ACK, `giaddr` = 172.18.10.1 |
| `L15_*.pcap` | DAG1 `Gi1/0` – ERS-SAT `Gi0/0` | `analiz_L15.md` | Erişim uplink'inde HSRP, STP ve relay'siz DHCP (giaddr 0.0.0.0) |

Öne çıkan gözlemler:
- **HSRP geçişi (grup 10):** DAG1 SVI'ı kapatılınca DAG2 `Standby → Active` (248. sn); SVI açılınca DAG1 `Coup` mesajıyla aktifliği geri aldı (286. sn), DAG2 `Speak → Standby`.
- **OSPF komşuluk kurulumu:** Hello → DBD → LSR → LSU → LSAck sırası yaklaşık 4 sn içinde tamamlandı.
- **DHCP relay (L11):** Discover 172.18.10.1 → 172.20.20.3, `giaddr` 172.18.10.1, GRE içinde; Offer 172.20.254.6'dan (DAG1'in Core'a bakan arayüzü) dönüyor, verilen adres 172.18.10.100.

Yol haritasındaki tablodan **yakalanmayan** tek satır: konsol telnet trafiği (Netmiko komutları). Laboratuvarda konsol yerel soket olduğu için ağ arayüzünden geçmiyor.

## Uçtan uca koşu — `lab/big_test.py` (gerçek IOSv / IOSvL2, 9 cihaz birlikte)
Çalışan: CORE1/2, DAG1/2, SNR-RTR, ISS-RTR, FAB-RTR, MRK-ERS-SAT, FAB-ERS-1. PC yerine switch SVI'ları DHCP istemcisi yapıldı.
**Sonuç: 35 kontrolün 33'ü ilk koşuda geçti; kalan 2'si (yedek + sapma) aşağıdaki 3. bulgu düzeltildikten sonra ayrıca koşuldu ve geçti.**

| Grup | Kontrol | Sonuç |
|---|---|---|
| Config | Sıfırdan 9 cihaza Faz 1+2+3 (basış sonrası doğrulama dâhil) | 583 sn, 0 hata, 0 uyarı |
| Sağlık | `validate.py` | 9/9 sağlıklı, 77 kontrol OK |
| OSPF | CORE1'de 3 komşu; 172.18.10.0/24 `O IA`; DAG1'de default `O*E2` | Geçti |
| STP | ERS-SAT VLAN 10: `Gi0/0` Root FWD, `Gi0/1` Altn BLK | Geçti |
| DHCP | SAT istemcisi DAG1 havuzundan 172.16.10.100 | Geçti |
| DHCP relay | Tesis istemcisi GRE üstünden 172.18.10.100 | Geçti |
| NAT | SAT ve Tesis istemcisi → 203.0.113.1; SNR NAT tablosunda çeviri | Geçti |
| ACL | A12 SAT → FAB ✓ · SAT → VLAN 20 ✗ · A5 SAT → yönetim ✗ · A11 FAB → BIS ✗ · sayaçlar arttı | Geçti |
| Sertleştirme | `harden.py` sonrası OSPF MD5 ile 14 komşuluk yeniden FULL; Port Security; DHCP snooping; internet erişimi sürüyor | Geçti |
| F3 | CORE1 durduruldu: internet CORE2 üzerinden sürdü, rapor CORE1'i kırmızı gösterdi, geri gelince yeşil | Geçti |
| F4 | DAG1 durduruldu: DAG2 yedi VLAN'da Active, ERS-SAT `Gi0/1` forwarding, internet sürdü | Geçti |
| Canlı pytest | `pytest extensions/tests --live --only … --partial` | 39 geçti |

## Karşılaşılan sorunlar ve çözümleri (hepsi gerçek cihazda görüldü)
1. **Stub alan komutu reddedildi → Tesis tamamen koptu.** Dokuz cihazlı ilk koşuda SNR-RTR'da `area 300 stub no-summary` config'e girmedi; iki uçta stub bayrağı uyuşmadığı için tünelde OSPF komşuluğu hiç kurulmadı. IOS'un mesajı: `% OSPF: Area 300 is being deleted, please try later`. Tünel arayüzü yapılandırılırken kısa süre düşüyor, Area 300'ün tek arayüzü o olduğu için IOS alanı silmeye başlıyor ve hemen ardından gelen komutu reddediyor. Üç router'lı küçük koşuda aynı şablon çalışmıştı; hata zamanlamaya bağlı. **Çözüm:** `snr_faz3.j2` ve `fab_faz3.j2`'de alan tanımı tünel arayüzünden önceye alındı; pytest'e regresyon testi eklendi.
2. **Sessiz hata yakalanmıyordu.** `deploy.py` yalnız `% Invalid input` türü mesajlara bakıyordu; yukarıdaki `% OSPF: …` mesajı ve config'e girmeyen satır fark edilmedi. **Çözüm:** `%` ile başlayan her IOS yanıtı raporlanıyor (bilinen bilgi mesajları hariç) ve her basıştan sonra `running-config` geri okunup eksik satır yeniden basılıyor, yine yoksa `EKSIK` olarak raporlanıyor.
3. **Konsol okuması yük altında kayıplı.** 9 sanal cihaz çalışırken `show running-config` çıktısında var olan satırlar ara sıra eksik geldi (yanlış "EKSIK" alarmı, yedeklerde boş satırlar). **Çözüm:** `confcheck.read_running` iki ardışık okuma birebir aynı olana kadar tekrarlıyor; hem doğrulama hem yedek bunu kullanıyor. İlk sürümde çıktının sonuna eklenen cihaz prompt'u yüzünden bütün yedekler "kararsız" diye reddedildi; temizleme adımı son `end` satırından sonrasını atacak şekilde düzeltildi.
4. **Routed Port-channel açıklaması komşu bağlanınca siliniyor.** Tek cihazlı testte görünmedi; dokuz cihazlı koşudan sonra sapma raporu `description PO1-TO-CORE2` satırlarını eksik buldu. **Çözüm:** açıklama Faz 2 şablonlarında yeniden yazılıyor.
5. **Sapma raporu sertleştirme satırlarını "fazla" sayıyordu.** `drift.py --also extensions/security-hardening/rendered` eklendi; MD5 anahtarı karşılaştırmada maskeleniyor. Son durumda 9 cihazın 7'si uyumlu, kalan 2 sapma testte bilerek elle yapılan değişiklikler (`ip address dhcp`, `no ip default-gateway`).

## Yapılmayanlar
- **13 cihazın tamamı birlikte koşmadı.** MRK-ERS-PER/BIS/YNT/SRV yalnızca tek tek doğrulandı (`faz4.md`). Bu yüzden VLAN 20/30/40/50/60 için uçtan uca trafik, sunucu çiftliği ACL'i (`ACL-SRV-OUT`) ve misafir ağı (`ACL-V60-IN`) canlı trafikte sınanmadı; bunlar pytest'teki ACL değerlendiricisiyle çevrimdışı doğrulandı.
- **VPCS uçları yok.** İstemci rolünü switch SVI'ları oynadı.
- **Asıl GNS3 projesi.** Elle kurulmuş Faz 0–3 config'leriyle karşılaştırma yapılmadı; o projenin çalıştığı makine ve enable parolası gerekir.
- **F1, F2, F5, F6, F8 demoları** koşulmadı (F3, F4, F7 koşuldu).
- Emülasyon donanım hızlandırmasız (QEMU TCG) olduğundan süreler gerçek GNS3/KVM ortamını temsil etmez.

## Çekirdek proje durumu
Faz 4, 5 ve 6 tamam. Yol haritasına göre bu noktada çekirdek biter; genişletme modülleri `genisletme.md` içinde.
