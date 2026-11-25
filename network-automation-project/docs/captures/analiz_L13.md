# Paket Analizi Raporu (Faz 6-B)

Kaynak dosyalar: `L13_FAB-RTR-Gi0-1_FAB-ERS-1-Gi0-0.pcap`

Toplam 1568 paket, sure 3224 sn. Zamanlar ilk pakete goredir.

## 1. Protokol dagilimi

| Protokol | Paket |
|---|---|
| STP / PVST+ | 1142 |
| Diger | 300 |
| CDP / VTP / DTP (Cisco L2) | 119 |
| ARP | 7 |

## 3. Rapid-PVST+ BPDU'lari (hedef 01:00:0c:cc:cc:cd)

| VLAN | BPDU | Kok onceligi | Kok MAC | Gorulen kopruler (oncelik/MAC) | Kopru basina aralik | Hello | MaxAge | FwdDelay |
|---|---|---|---|---|---|---|---|---|
| 1 | 367 | 32768 | 0c:00:09:00:00:00 | 32768/0c:00:09:00:00:00 | 2.8 sn | 2.0 | 20.0 | 15.0 |
| 110 | 775 | 32768 | 0c:00:09:00:00:00 | 32768/0c:00:09:00:00:00 | 2.8 sn | 2.0 | 20.0 | 15.0 |

Yorum: oncelik alani `oncelik + VLAN no` olarak tasinir (extended system ID); tabloda VLAN cikarilmis hali var. Kok onceligi 4096 olan kopru o VLAN'in kokudur; plan: VLAN 10/30/50/90/254 -> DAG1, VLAN 20/40/60 -> DAG2.

## 7. DHCP (UDP 67/68)

28 adet relay'siz Discover (cihaz acilisindaki autoinstall denemeleri ve istemcinin ilk yayinlari) tabloda gosterilmedi.

| Zaman | Mesaj | Kaynak IP | Hedef IP | giaddr (relay) | yiaddr (verilen) | GRE icinde |
|---|---|---|---|---|---|---|
| 1542.7 sn | Offer | 172.18.10.1 | 255.255.255.255 | 172.18.10.1 | 172.18.10.100 | hayir |
| 1542.7 sn | Request | 0.0.0.0 | 255.255.255.255 | 0.0.0.0 | 0.0.0.0 | hayir |
| 1542.7 sn | ACK | 172.18.10.1 | 255.255.255.255 | 172.18.10.1 | 172.18.10.100 | hayir |

Yorum: `giaddr` 0.0.0.0 ise istek sunucuya dogrudan (ayni VLAN'da) ulasmistir. `giaddr` dolu ise paket bir relay'den (`ip helper-address`) gecmistir: relay yayini unicast'e cevirir, kendi arayuz adresini `giaddr`'a yazar ve sunucu havuzu bu adrese gore secer. Tesis istemcisinin DORA'si FAB-RTR (172.18.10.1) -> GRE tuneli -> MRK-DAG1 Loopback0 (172.20.20.3) yolunu izler.
