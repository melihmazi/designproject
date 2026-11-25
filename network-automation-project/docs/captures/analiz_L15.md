# Paket Analizi Raporu (Faz 6-B)

Kaynak dosyalar: `L15_DAG1-Gi1-0_ERS-SAT-Gi0-0.pcap`

Toplam 5009 paket, sure 3130 sn. Zamanlar ilk pakete goredir.

## 1. Protokol dagilimi

| Protokol | Paket |
|---|---|
| HSRP | 2302 |
| STP / PVST+ | 2047 |
| Diger | 382 |
| CDP / VTP / DTP (Cisco L2) | 252 |
| ARP | 24 |
| OSPF | 2 |

## 3. Rapid-PVST+ BPDU'lari (hedef 01:00:0c:cc:cc:cd)

| VLAN | BPDU | Kok onceligi | Kok MAC | Gorulen kopruler (oncelik/MAC) | Kopru basina aralik | Hello | MaxAge | FwdDelay |
|---|---|---|---|---|---|---|---|---|
| 1 | 218 | 32768 | 0c:00:00:00:00:00 | 32768/0c:00:00:00:00:00<br>32768/0c:00:04:00:00:00 | 5.5 sn | 2.0 | 20.0 | 15.0 |
| 10 | 905 | 4096 | 0c:00:00:00:00:00 | 32768/0c:00:04:00:00:00<br>4096/0c:00:00:00:00:00 | 5.6 sn | 2.0 | 20.0 | 15.0 |
| 20 | 1 | 8192 | 0c:00:00:00:00:00 | 8192/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |
| 30 | 1 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |
| 40 | 1 | 8192 | 0c:00:00:00:00:00 | 8192/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |
| 50 | 1 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |
| 60 | 1 | 8192 | 0c:00:00:00:00:00 | 8192/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |
| 90 | 918 | 4096 | 0c:00:00:00:00:00 | 32768/0c:00:04:00:00:00<br>4096/0c:00:00:00:00:00 | 5.5 sn | 2.0 | 20.0 | 15.0 |
| 254 | 1 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00 | 0.0 sn | 2.0 | 20.0 | 15.0 |

Yorum: oncelik alani `oncelik + VLAN no` olarak tasinir (extended system ID); tabloda VLAN cikarilmis hali var. Kok onceligi 4096 olan kopru o VLAN'in kokudur; plan: VLAN 10/30/50/90/254 -> DAG1, VLAN 20/40/60 -> DAG2.

## 4. HSRP (UDP 1985, 224.0.0.2)

| Grup | Kaynak IP | Oncelik | Sanal IP | Hello/Hold | Paket | Durum gecisleri |
|---|---|---|---|---|---|---|
| 10 | 172.16.10.2 | 110 | 172.16.10.1 | 3/10 | 582 | Speak@915s -> Standby@930s -> Active@931s |
| 10 | 172.16.10.3 | 90 | 172.16.10.1 | 3/10 | 574 | Speak@920s -> Standby@960s |
| 90 | 172.16.90.2 | 110 | 172.16.90.1 | 3/10 | 579 | Speak@924s -> Standby@936s -> Active@941s |
| 90 | 172.16.90.3 | 90 | 172.16.90.1 | 3/10 | 567 | Speak@930s -> Standby@970s |

Yorum: `Speak -> Standby -> Active` acilis sirasidir. `Resign` aktif yonlendiricinin gorevi biraktigini (ornegin SVI kapatildi), `Coup` ise daha yuksek oncelikli yonlendiricinin `preempt` ile aktifligi geri aldigini gosterir. Kimlik dogrulama alani varsayilan duz metin `cisco`'dur.

## 5. OSPF (IP protokol 89)

| Tip | Ad | Paket |
|---|---|---|
| 1 | Hello | 2 |

| Alan | Hello araligi | Dead araligi | Ag maskesi | DR | BDR | VLAN | Hedef |
|---|---|---|---|---|---|---|---|
| 100 | 10 sn | 40 sn | 255.255.255.0 | 0.0.0.0 | 0.0.0.0 | 10 | 224.0.0.5 |

| Router-ID | Arayuz IP |
|---|---|
| 172.20.20.3 | 172.16.10.2 |
| 172.20.20.4 | 172.16.10.3 |

**Komsuluk kurulumu zaman cizgisi (her tip/kaynak icin ilk gorulme):**

| Zaman | Kaynak | Paket |
|---|---|---|
| 901.1 sn | 172.16.10.2 | Hello |
| 905.3 sn | 172.16.10.3 | Hello |

Yorum: Hello'lar karsilikli gorulunce komsuluk 2-Way'e, DBD degisimiyle ExStart/Exchange'e, LSR/LSU/LSAck ile Loading ve ardindan Full durumuna gecer. DR ve BDR alanlarinin 0.0.0.0 olmasi arayuzun `ip ospf network point-to-point` oldugunu (DR secimi yok) dogrular.

## 7. DHCP (UDP 67/68)

13 adet relay'siz Discover (cihaz acilisindaki autoinstall denemeleri ve istemcinin ilk yayinlari) tabloda gosterilmedi.

| Zaman | Mesaj | Kaynak IP | Hedef IP | giaddr (relay) | yiaddr (verilen) | GRE icinde |
|---|---|---|---|---|---|---|
| 1472.8 sn | Offer | 172.16.10.2 | 255.255.255.255 | 0.0.0.0 | 172.16.10.100 | hayir |
| 1472.8 sn | Request | 0.0.0.0 | 255.255.255.255 | 0.0.0.0 | 0.0.0.0 | hayir |
| 1472.8 sn | ACK | 172.16.10.2 | 255.255.255.255 | 0.0.0.0 | 172.16.10.100 | hayir |

Yorum: `giaddr` 0.0.0.0 ise istek sunucuya dogrudan (ayni VLAN'da) ulasmistir. `giaddr` dolu ise paket bir relay'den (`ip helper-address`) gecmistir: relay yayini unicast'e cevirir, kendi arayuz adresini `giaddr`'a yazar ve sunucu havuzu bu adrese gore secer. Tesis istemcisinin DORA'si FAB-RTR (172.18.10.1) -> GRE tuneli -> MRK-DAG1 Loopback0 (172.20.20.3) yolunu izler.
