# Faz 0 — Ortam ve İskelet            Doğrulama tarihi: 2026-11-25

Bu faz GNS3 arayüzünde elle kuruldu. Bu not, kurulu projenin gerçek GNS3 ortamında (2.2.61, yerel sunucu)
betiklerle yeniden doğrulanmasının kaydıdır. Ham çıktılar: `lab/logs/gns3_kanit.txt`, `lab/logs/gns3_validate6.txt`.

## Ne yapıldı
- 30 düğüm (10 IOSvL2 switch, 3 IOSv router, 17 VPCS) ve 40 bağlantı çizildi.
- Her cihaza ad, yerel kullanıcı, enable parolası ve konsol erişimi verildi.
- Konsol portları 5000–5058 aralığına sabitlendi; `core/inventory/consoles.yaml` bu portlardan üretildi.

## Hangi komutla doğrulandı
| Komut | Sonuç |
|---|---|
| `POST /v2/projects/load` + `nodes/start` | 30 düğüm, 40 bağlantı, hepsi başladı |
| `validate.py` → "Erisim" kontrolleri | 13/13 cihaza konsoldan girildi |
| `validate.py` → "CDP" kontrolleri | Her cihazda beklenen komşu ve port eşleşti |
| `show cdp neighbors` | Aşağıdaki tablo |

## Beklenen ↔ gerçek
| Cihaz | Beklenen CDP komşu sayısı | Gerçek |
|---|---|---|
| MRK-CORE1 | 5 (CORE2 ×2, DAG1 ×2, SNR) | 5 |
| MRK-CORE2 | 5 (CORE1 ×2, DAG2 ×2, SNR) | 5 |
| MRK-DAG1 | 9 (CORE1 ×2, DAG2 ×2, 5 erişim switch'i) | 9 |
| MRK-DAG2 | 9 (CORE2 ×2, DAG1 ×2, 5 erişim switch'i) | 9 |
| MRK-ERS-SAT | 2 (DAG1, DAG2) | 2 |
| MRK-ERS-SRV | 2 (DAG1, DAG2) | 2 |
| FAB-ERS-1 | 1 (FAB-RTR) | 1 |

## Karşılaşılan sorun ve çözüm
- **GNS3 VM yok.** Bu bilgisayarda VMware kurulu değil; düğümler yerel sunucuda donanım hızlandırma olmadan
  çalışıyor. 13 cihazın açılması yaklaşık 10 dakika sürüyor.
- **Konsol portu kayması.** Proje yüklenirken bir port doluysa GNS3 sessizce başka port verip öyle kaydediyor.
  Yüklemeden önce 5000–5058 aralığı boş olmalı.
- **Switch parolaları belgelerde yoktu.** Diskler yedeklenip (`lab/gns3_disk_yedek/`) kayıtlı yapılandırma yeni
  parolayla geri yüklendi; 10 switch'te eksik satır 0 (ayrıntı: `tam-topoloji.md`).

## Sonraki faz için ayarlama
- Enable isteyen her betik `lab/gns3_run.py sw|rtr` üzerinden koşulur; switch ve router parolaları ayrıdır.
