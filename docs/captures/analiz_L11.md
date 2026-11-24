# Paket Analizi Raporu (Faz 6-B)

Kaynak dosyalar: `L11_SNR-Gi0-2_ISS-Gi0-0.pcap`

Toplam 993 paket, sure 3213 sn. Zamanlar ilk pakete goredir.

## 1. Protokol dagilimi

| Protokol | Paket |
|---|---|
| Diger | 553 |
| OSPF | 340 |
| CDP / VTP / DTP (Cisco L2) | 94 |
| ARP | 6 |

## 5. OSPF (IP protokol 89)

| Tip | Ad | Paket |
|---|---|---|
| 1 | Hello | 324 |
| 2 | DBD (Database Description) | 5 |
| 3 | LSR (Link State Request) | 2 |
| 4 | LSU (Link State Update) | 5 |
| 5 | LSAck | 4 |

| Alan | Hello araligi | Dead araligi | Ag maskesi | DR | BDR | VLAN | Hedef |
|---|---|---|---|---|---|---|---|
| 300 | 10 sn | 40 sn | 255.255.255.252 | 0.0.0.0 | 0.0.0.0 | None | 198.51.100.6 |

| Router-ID | Arayuz IP |
|---|---|
| 172.20.20.5 | 198.51.100.1 |
| 172.20.20.6 | 198.51.100.6 |

**Komsuluk kurulumu zaman cizgisi (her tip/kaynak icin ilk gorulme):**

| Zaman | Kaynak | Paket |
|---|---|---|
| 1022.5 sn | 198.51.100.1 | Hello |
| 1082.3 sn | 198.51.100.6 | Hello |
| 1082.3 sn | 198.51.100.6 | DBD (Database Description) |
| 1082.3 sn | 198.51.100.1 | DBD (Database Description) |
| 1082.3 sn | 198.51.100.1 | LSR (Link State Request) |
| 1082.3 sn | 198.51.100.6 | LSU (Link State Update) |
| 1082.3 sn | 198.51.100.6 | LSR (Link State Request) |
| 1082.3 sn | 198.51.100.1 | LSU (Link State Update) |
| 1085.8 sn | 198.51.100.1 | LSAck |
| 1085.8 sn | 198.51.100.6 | LSAck |

Yorum: Hello'lar karsilikli gorulunce komsuluk 2-Way'e, DBD degisimiyle ExStart/Exchange'e, LSR/LSU/LSAck ile Loading ve ardindan Full durumuna gecer. DR ve BDR alanlarinin 0.0.0.0 olmasi arayuzun `ip ospf network point-to-point` oldugunu (DR secimi yok) dogrular.

## 6. GRE tuneli (IP protokol 47)

| Dis kaynak | Dis hedef | Paket |
|---|---|---|
| 198.51.100.1 | 198.51.100.6 | 187 |
| 198.51.100.6 | 198.51.100.1 | 179 |

**Tunelin icindeki (ic) paketler:**

| Ic paket | Ic kaynak | Ic hedef | Adet |
|---|---|---|---|
| OSPF Hello | 172.20.200.1 | 224.0.0.5 | 164 |
| OSPF Hello | 172.20.200.2 | 224.0.0.5 | 160 |
| ICMP echo | 172.16.10.100 | 172.18.10.100 | 5 |
| ICMP echo-reply | 172.18.10.100 | 172.16.10.100 | 5 |
| ICMP echo | 172.18.10.100 | 203.0.113.1 | 5 |
| ICMP echo-reply | 203.0.113.1 | 172.18.10.100 | 5 |
| OSPF DBD | 172.20.200.1 | 224.0.0.5 | 3 |
| OSPF LSU | 172.20.200.2 | 224.0.0.5 | 3 |
| OSPF LSAck | 172.20.200.1 | 224.0.0.5 | 3 |
| OSPF DBD | 172.20.200.2 | 224.0.0.5 | 2 |
| OSPF LSU | 172.20.200.1 | 224.0.0.5 | 2 |
| ICMP echo | 172.20.254.6 | 172.18.10.100 | 2 |

GRE ek yuku: dis IP basligi 20 bayt + GRE 4 bayt = 24 bayt. Yakalanan en buyuk cerceve 392 bayt. Tunelde `ip mtu 1400` ve `ip tcp adjust-mss 1360` bu ek yuk yuzunden parcalanmayi onlemek icindir.

**Tunel disi ICMP echo (NAT kaniti):**

| Kaynak | Hedef | Paket |
|---|---|---|
| 198.51.100.1 | 203.0.113.1 | 25 |

Yorum: Tesis LAN'indan (172.18.10.1) internete giden paket tunelin icinde ozel adresle gelir, SNR-RTR'da PAT ile 198.51.100.1 kaynak adresine cevrilip tunel disinda ISS'e gider.

## 7. DHCP (UDP 67/68)

27 adet relay'siz Discover (cihaz acilisindaki autoinstall denemeleri ve istemcinin ilk yayinlari) tabloda gosterilmedi.

| Zaman | Mesaj | Kaynak IP | Hedef IP | giaddr (relay) | yiaddr (verilen) | GRE icinde |
|---|---|---|---|---|---|---|
| 1527.3 sn | Discover | 172.18.10.1 | 172.20.20.3 | 172.18.10.1 | 0.0.0.0 | evet |
| 1530.1 sn | Offer | 172.20.254.6 | 172.18.10.1 | 172.18.10.1 | 172.18.10.100 | evet |
| 1530.1 sn | Request | 172.18.10.1 | 172.20.20.3 | 172.18.10.1 | 0.0.0.0 | evet |
| 1530.2 sn | ACK | 172.20.254.6 | 172.18.10.1 | 172.18.10.1 | 172.18.10.100 | evet |

Yorum: `giaddr` 0.0.0.0 ise istek sunucuya dogrudan (ayni VLAN'da) ulasmistir. `giaddr` dolu ise paket bir relay'den (`ip helper-address`) gecmistir: relay yayini unicast'e cevirir, kendi arayuz adresini `giaddr`'a yazar ve sunucu havuzu bu adrese gore secer. Tesis istemcisinin DORA'si FAB-RTR (172.18.10.1) -> GRE tuneli -> MRK-DAG1 Loopback0 (172.20.20.3) yolunu izler.
