# Faz 3 — Kenar, WAN ve Servisler            Doğrulama tarihi: 2026-11-25

Gerçek GNS3 projesinde, gerçek VPCS uçlarından doğrulandı. Ham çıktılar: `lab/logs/gns3_acl.txt`,
`lab/logs/gns3_vpcs3.txt`; paket kanıtı: `docs/captures/gercek/analiz.md` (bölüm 1, 2 ve 5).

## Ne yapıldı
- GRE tüneli (SNR-RTR ↔ FAB-RTR, ISS-RTR üzerinden), üzerinde OSPF alan 300.
- NAT/PAT (SNR-RTR), simüle internet hedefi 203.0.113.1 (ISS-RTR).
- DHCP: havuzlar DAG1'de; Tesis için FAB-RTR'de relay (`ip helper-address`).
- ACL'ler: DAG1 ve DAG2 SVI'larında `ACL-V10-IN`, `ACL-V20-IN`, `ACL-V60-IN`, `ACL-SRV-OUT`, `ACL-V90-OUT`;
  FAB-RTR'de `ACL-FAB-IN`.

## Hangi komutla doğrulandı
| Komut | Sonuç |
|---|---|
| `lab/gns3_acl.py` | 16/16 (3 DHCP + 13 ACL satırı) |
| `lab/gns3_vpcs.py` | 8/8 |
| `show interfaces Tunnel0`, `show ip route` (FAB-RTR) | Tünel `up/up`, `O*IA 0.0.0.0/0 via 172.20.200.1` |
| `show access-lists` (DAG1, DAG2, FAB-RTR), testten önce ve sonra | Altı ACL'in sayaçları arttı |

## Beklenen ↔ gerçek
### DHCP (yol haritası 12.4)
| Test | Beklenen | Gerçek |
|---|---|---|
| `SAT-PC1> ip dhcp` | 172.16.10.1xx/24, GW 172.16.10.1 | `DORA IP 172.16.10.100/24 GW 172.16.10.1` |
| `FAB-PC1> ip dhcp` | 172.18.10.1xx/24 (GRE üstünden relay) | `DORA IP 172.18.10.100/24 GW 172.18.10.1` |
| `MSF-DZ1> ip dhcp` | 172.16.60.1xx/24 | `DORA IP 172.16.60.100/24 GW 172.16.60.1` |
| Relay paketinde `giaddr` | İlgili ağ geçidi adresi | 172.18.10.1 (kayıt G2) |

### ACL tablosu (yol haritası 12.3)
| # | Kaynak → Hedef | Beklenen | Gerçek |
|---|---|---|---|
| A1 | BIS-PC1 → SAT-PC1 ping | ✓ | ✓ 4/4 |
| A2 | SAT-PC1 → PER-PC1 ping | ✗ | ✗ ICMP tip 3 kod 13 (administratively prohibited) |
| A3 | SAT-PC1 → SNC-WEB tcp/80 | ✓ | ✓ bağlantı kuruldu |
| A4 | SAT-PC1 → SNC-DOSYA ping | ✓ | ✓ |
| A4b | SAT-PC1 → SNC-DOSYA tcp/22 (servis dışı port) | ✗ | ✗ administratively prohibited |
| A5 | SAT-PC1 → 172.16.90.11 (switch yönetimi) | ✗ | ✗ administratively prohibited |
| A6 | BIS-PC1 → 172.16.90.11 | ✓ | ✓ (statik varsayılan rota düzeltmesinden sonra) |
| A7 | MSF-DZ1 → SNC-DNS udp/53 | ✓ | ✓ |
| A8 | MSF-DZ1 → SNC-WEB ping | ✗ | ✗ administratively prohibited |
| A9 | MSF-DZ1 → 203.0.113.1 | ✓ | ✓ |
| A10 | FAB-PC1 → SNC-WEB | ✓ | ✓ 4/4 |
| A11 | FAB-PC1 → BIS-PC1 | ✗ | ✗ administratively prohibited (FAB-RTR) |
| A12 | SAT-PC1 → FAB-PC1 | ✓ | ✓ |

### ACL sayaçları (test öncesi → sonrası)
| Cihaz | ACL | Önce | Sonra |
|---|---|---|---|
| FAB-RTR | ACL-FAB-IN | 49 | 61 |
| MRK-DAG1 | ACL-SRV-OUT | 560 | 588 |
| MRK-DAG1 | ACL-V10-IN | 2768 | 3028 |
| MRK-DAG1 | ACL-V20-IN | 2077 | 2287 |
| MRK-DAG1 | ACL-V60-IN | 2080 | 2292 |
| MRK-DAG1 | ACL-V90-OUT | 4 | 8 |

V20 ve V60 sayaçlarındaki artışın çoğu HSRP hello paketlerinden geliyor (saniyede bir, `permit` satırına düşer).

### NAT
SAT-PC1'in pingi LAN'da 172.16.10.100 kaynak adresiyle, WAN'da 198.51.100.1 kaynak adresiyle görülüyor (kayıt G5 ve G1).

## Karşılaşılan sorun ve çözüm
- **A6 başlangıçta 0/4'tü.** IOSvL2'de `ip routing` açık olduğu için `ip default-gateway` yok sayılıyor; erişim
  switch'i başka VLAN'a yanıt veremiyordu. Altı L2 switch'e `ip route 0.0.0.0 0.0.0.0 <ağ geçidi>` eklendi, 4/4 oldu.
- **Sunucular VPCS.** Docker'a geçiş yapılmadı (GNS3 VM yok). VPCS tcp ve udp yoklamalarına yanıt verdiği için
  port bazlı ACL satırları yine sınanabildi; gerçek HTTP, DNS, FTP servisi sınanmadı.
- **İlk ping paketleri zaman aşımına düşüyor.** ARP çözümlemesi; sonraki paketler geçiyor.

## Sonraki faz için ayarlama
- ACL değişikliği iki DAG'da birden yapılmalı; şablon ikisine aynı listeyi basar.
