# Paket Analizi Raporu (Faz 6-B)

Kaynak dosyalar: `L07_DAG1-Gi0-2_DAG2-Gi0-2.pcap`, `L08_DAG1-Gi0-3_DAG2-Gi0-3.pcap`

Toplam 2353 paket, sure 329 sn. Zamanlar ilk pakete goredir.

## 1. Protokol dagilimi

| Protokol | Paket |
|---|---|
| HSRP | 1026 |
| STP / PVST+ | 982 |
| CDP / VTP / DTP (Cisco L2) | 90 |
| Diger | 80 |
| OSPF | 68 |
| LACP | 60 |
| ARP | 47 |

## 2. LACP (IEEE 802.3ad, Slow Protocols 0x8809)

| Gonderen MAC | PDU | Ort. aralik | Actor sistem | Key | Port | Ilk PDU bayraklari | Son PDU bayraklari | Partner sistem (son) |
|---|---|---|---|---|---|---|---|---|
| 0c:00:00:00:02:00 | 17 | 19.8 sn | 0c:00:00:00:80:00 | 2 | 3 | Activity(aktif), Aggregation, Defaulted | Activity(aktif), Aggregation, Synchronization, Collecting, Distributing | 0c:00:01:00:80:00 |
| 0c:00:00:00:03:00 | 17 | 19.4 sn | 0c:00:00:00:80:00 | 2 | 4 | Activity(aktif), Aggregation, Defaulted | Activity(aktif), Aggregation, Synchronization, Collecting, Distributing | 0c:00:01:00:80:00 |
| 0c:00:01:00:02:00 | 13 | 25.8 sn | 0c:00:01:00:80:00 | 2 | 3 | Activity(aktif), Aggregation, Defaulted | Activity(aktif), Aggregation, Synchronization, Collecting, Distributing | 0c:00:00:00:80:00 |
| 0c:00:01:00:03:00 | 13 | 26.2 sn | 0c:00:01:00:80:00 | 2 | 4 | Activity(aktif), Aggregation, Defaulted | Activity(aktif), Aggregation, Synchronization, Collecting, Distributing | 0c:00:00:00:80:00 |

Yorum: `Activity` biti iki tarafta da set, yani iki uc `mode active`. Ilk PDU'da partner bilinmez (00:00:00:00:00:00); `Synchronization + Collecting + Distributing` bitleri geldiginde port demete katilmis (`P`) demektir. `Timeout(kisa)` biti yoksa PDU araligi 30 sn, zaman asimi 90 sn'dir.

## 3. Rapid-PVST+ BPDU'lari (hedef 01:00:0c:cc:cc:cd)

| VLAN | BPDU | Kok onceligi | Kok MAC | Gorulen kopruler (oncelik/MAC) | Kopru basina aralik | Hello | MaxAge | FwdDelay |
|---|---|---|---|---|---|---|---|---|
| 10 | 123 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00<br>8192/0c:00:01:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 20 | 124 | 4096 | 0c:00:01:00:00:00 | 4096/0c:00:01:00:00:00<br>8192/0c:00:00:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 30 | 123 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00<br>8192/0c:00:01:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 40 | 123 | 4096 | 0c:00:01:00:00:00 | 4096/0c:00:01:00:00:00<br>8192/0c:00:00:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 50 | 123 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00<br>8192/0c:00:01:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 60 | 123 | 4096 | 0c:00:01:00:00:00 | 4096/0c:00:01:00:00:00<br>8192/0c:00:00:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 90 | 123 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00<br>8192/0c:00:01:00:00:00 | 5.2 sn | 2.0 | 20.0 | 15.0 |
| 254 | 120 | 4096 | 0c:00:00:00:00:00 | 4096/0c:00:00:00:00:00<br>8192/0c:00:01:00:00:00 | 5.4 sn | 2.0 | 20.0 | 15.0 |

Yorum: oncelik alani `oncelik + VLAN no` olarak tasinir (extended system ID); tabloda VLAN cikarilmis hali var. Kok onceligi 4096 olan kopru o VLAN'in kokudur; plan: VLAN 10/30/50/90/254 -> DAG1, VLAN 20/40/60 -> DAG2.

## 4. HSRP (UDP 1985, 224.0.0.2)

| Grup | Kaynak IP | Oncelik | Sanal IP | Hello/Hold | Paket | Durum gecisleri |
|---|---|---|---|---|---|---|
| 10 | 172.16.10.2 | 110 | 172.16.10.1 | 3/10 | 66 | Speak@34s -> Standby@46s -> Active@50s -> Listen@286s -> Active@286s |
| 10 | 172.16.10.3 | 90 | 172.16.10.1 | 3/10 | 73 | Speak@37s -> Standby@82s -> Active@248s -> Speak@286s -> Standby@301s |
| 20 | 172.16.20.2 | 90 | 172.16.20.1 | 3/10 | 69 | Speak@34s -> Standby@85s |
| 20 | 172.16.20.3 | 110 | 172.16.20.1 | 3/10 | 77 | Speak@36s -> Standby@53s -> Active@54s |
| 30 | 172.16.30.2 | 110 | 172.16.30.1 | 3/10 | 78 | Speak@34s -> Standby@48s -> Active@50s |
| 30 | 172.16.30.3 | 90 | 172.16.30.1 | 3/10 | 71 | Speak@36s -> Standby@79s |
| 40 | 172.16.40.2 | 90 | 172.16.40.1 | 3/10 | 70 | Speak@34s -> Standby@84s |
| 40 | 172.16.40.3 | 110 | 172.16.40.1 | 3/10 | 78 | Speak@35s -> Standby@52s -> Active@53s |
| 50 | 172.16.50.2 | 110 | 172.16.50.1 | 3/10 | 79 | Speak@35s -> Standby@47s -> Active@51s |
| 50 | 172.16.50.3 | 90 | 172.16.50.1 | 3/10 | 70 | Speak@37s -> Standby@82s |
| 60 | 172.16.60.2 | 90 | 172.16.60.1 | 3/10 | 70 | Speak@35s -> Standby@78s |
| 60 | 172.16.60.3 | 110 | 172.16.60.1 | 3/10 | 78 | Speak@36s -> Standby@49s -> Active@51s |
| 90 | 172.16.90.2 | 110 | 172.16.90.1 | 3/10 | 77 | Speak@35s -> Standby@47s -> Active@50s |
| 90 | 172.16.90.3 | 90 | 172.16.90.1 | 3/10 | 70 | Speak@37s -> Standby@78s |

**Ozel mesajlar (failover ani):**

| Zaman | Grup | Kaynak | Mesaj |
|---|---|---|---|
| 286.4 sn | 10 | 172.16.10.2 | Coup |

Yorum: `Speak -> Standby -> Active` acilis sirasidir. `Resign` aktif yonlendiricinin gorevi biraktigini (ornegin SVI kapatildi), `Coup` ise daha yuksek oncelikli yonlendiricinin `preempt` ile aktifligi geri aldigini gosterir. Kimlik dogrulama alani varsayilan duz metin `cisco`'dur.

## 5. OSPF (IP protokol 89)

| Tip | Ad | Paket |
|---|---|---|
| 1 | Hello | 49 |
| 2 | DBD (Database Description) | 5 |
| 3 | LSR (Link State Request) | 2 |
| 4 | LSU (Link State Update) | 8 |
| 5 | LSAck | 4 |

| Alan | Hello araligi | Dead araligi | Ag maskesi | DR | BDR | VLAN | Hedef |
|---|---|---|---|---|---|---|---|
| 0 | 10 sn | 40 sn | 255.255.255.252 | 0.0.0.0 | 0.0.0.0 | 254 | 224.0.0.5 |

| Router-ID | Arayuz IP |
|---|---|
| 172.20.20.3 | 172.20.254.13 |
| 172.20.20.4 | 172.20.254.14 |

**Komsuluk kurulumu zaman cizgisi (her tip/kaynak icin ilk gorulme):**

| Zaman | Kaynak | Paket |
|---|---|---|
| 12.8 sn | 172.20.254.14 | Hello |
| 13.0 sn | 172.20.254.13 | Hello |
| 23.2 sn | 172.20.254.13 | DBD (Database Description) |
| 23.5 sn | 172.20.254.14 | DBD (Database Description) |
| 23.7 sn | 172.20.254.13 | LSR (Link State Request) |
| 23.9 sn | 172.20.254.14 | LSU (Link State Update) |
| 23.9 sn | 172.20.254.14 | LSR (Link State Request) |
| 23.9 sn | 172.20.254.13 | LSU (Link State Update) |
| 27.5 sn | 172.20.254.13 | LSAck |
| 27.6 sn | 172.20.254.14 | LSAck |

Yorum: Hello'lar karsilikli gorulunce komsuluk 2-Way'e, DBD degisimiyle ExStart/Exchange'e, LSR/LSU/LSAck ile Loading ve ardindan Full durumuna gecer. DR ve BDR alanlarinin 0.0.0.0 olmasi arayuzun `ip ospf network point-to-point` oldugunu (DR secimi yok) dogrular.
