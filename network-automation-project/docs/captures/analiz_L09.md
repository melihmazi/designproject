# Paket Analizi Raporu (Faz 6-B)

Kaynak dosyalar: `L09_CORE1-Gi1-0_SNR-Gi0-0.pcap`

Toplam 151 paket, sure 356 sn. Zamanlar ilk pakete goredir.

## 1. Protokol dagilimi

| Protokol | Paket |
|---|---|
| OSPF | 79 |
| Diger | 49 |
| CDP / VTP / DTP (Cisco L2) | 18 |
| ARP | 5 |

## 5. OSPF (IP protokol 89)

| Tip | Ad | Paket |
|---|---|---|
| 1 | Hello | 53 |
| 2 | DBD (Database Description) | 5 |
| 3 | LSR (Link State Request) | 1 |
| 4 | LSU (Link State Update) | 13 |
| 5 | LSAck | 7 |

| Alan | Hello araligi | Dead araligi | Ag maskesi | DR | BDR | VLAN | Hedef |
|---|---|---|---|---|---|---|---|
| 0 | 10 sn | 40 sn | 255.255.255.252 | 0.0.0.0 | 0.0.0.0 | None | 224.0.0.5 |

| Router-ID | Arayuz IP |
|---|---|
| 172.20.20.1 | 172.20.254.17 |
| 172.20.20.5 | 172.20.254.18 |

**Komsuluk kurulumu zaman cizgisi (her tip/kaynak icin ilk gorulme):**

| Zaman | Kaynak | Paket |
|---|---|---|
| 13.9 sn | 172.20.254.18 | Hello |
| 29.2 sn | 172.20.254.17 | Hello |
| 34.9 sn | 172.20.254.17 | DBD (Database Description) |
| 34.9 sn | 172.20.254.18 | DBD (Database Description) |
| 35.1 sn | 172.20.254.17 | LSR (Link State Request) |
| 35.1 sn | 172.20.254.18 | LSU (Link State Update) |
| 38.2 sn | 172.20.254.17 | LSAck |
| 39.5 sn | 172.20.254.17 | LSU (Link State Update) |
| 43.2 sn | 172.20.254.18 | LSAck |

Yorum: Hello'lar karsilikli gorulunce komsuluk 2-Way'e, DBD degisimiyle ExStart/Exchange'e, LSR/LSU/LSAck ile Loading ve ardindan Full durumuna gecer. DR ve BDR alanlarinin 0.0.0.0 olmasi arayuzun `ip ospf network point-to-point` oldugunu (DR secimi yok) dogrular.
