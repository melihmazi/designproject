# Faz 1 — L2 Omurga            Doğrulama tarihi: 2026-11-25

Gerçek GNS3 projesinde betiklerle doğrulandı. Ham çıktılar: `lab/logs/gns3_kanit.txt`;
paket kanıtı: `docs/captures/gercek/analiz.md` (bölüm 3 ve 4).

## Ne yapıldı
- VLAN'lar (10, 20, 30, 40, 50, 60, 90, 254) ve erişim portları.
- LACP demetleri: CORE1–CORE2 (Po1), CORE–DAG (Po2/Po1), DAG1–DAG2 L2 trunk (Po2).
- Rapid-PVST+: tek VLAN'lar için kök DAG1, çift VLAN'lar için kök DAG2 (HSRP ile aynı taraf).
- Erişim switch'lerinde iki uplink: biri iletimde, öbürü yedek.

## Hangi komutla doğrulandı
| Komut | Sonuç |
|---|---|
| `show etherchannel summary` (CORE1, CORE2, DAG1, DAG2) | Aşağıdaki tablo |
| `show spanning-tree root` (DAG1, DAG2) | Kök dağılımı beklendiği gibi |
| `show spanning-tree vlan 10` (ERS-SAT) | `Gi0/0 Root FWD`, `Gi0/1 Altn BLK` |
| `show interfaces trunk` (ERS-SAT) | İki uplink 802.1Q, native 90, izinli VLAN 10 ve 90 |
| `validate.py` → EtherChannel, STP kontrolleri | Hepsi OK |

## Beklenen ↔ gerçek
| Kontrol | Beklenen | Gerçek |
|---|---|---|
| CORE1 Po1, Po2 | `RU`, üyeler `P` | `Po1(RU) Gi0/0(P) Gi0/1(P)`, `Po2(RU) Gi0/2(P) Gi0/3(P)` |
| CORE2 Po1, Po2 | `RU`, üyeler `P` | Aynı |
| DAG1 / DAG2 Po1 (uplink) | `RU` | `Po1(RU) Gi0/0(P) Gi0/1(P)` |
| DAG1 / DAG2 Po2 (L2 interlink) | `SU` | `Po2(SU) Gi0/2(P) Gi0/3(P)` |
| STP kökü VLAN 10, 30, 50, 90, 254 | DAG1 | `0c41.0065.0000` (DAG1), öncelik 4096 + VLAN |
| STP kökü VLAN 20, 40, 60 | DAG2 | `0c99.624c.0000` (DAG2) |
| ERS-SAT yedek uplink | `Altn BLK` | `Gi0/1 Altn BLK` |
| Aynı VLAN'da ping | Geçer | SAT-PC1 → ağ geçidi 4/4 |
| LACP paketleri | İki uç anlaşmış | Aktör ve partner durumu `0x3d` (kayıt G3) |

## Karşılaşılan sorun ve çözüm
- **Routed Port-channel açıklamaları yeniden başlatmada kayboluyor** (IOSvL2 davranışı). Sapma raporu yakalıyor,
  `lab/gns3_fix.py` yeniden basıyor.
- **Yeni oluşturulan SVI'lar kapalı geliyor.** Yapılandırma geri yüklenirken `no shutdown` eklendi.

## Sonraki faz için ayarlama
- L2 interlink (Po2) F5 ve F8 senaryolarında trafiği taşıyan yol; kaldırılmamalı.
