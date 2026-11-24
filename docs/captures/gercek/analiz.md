# Gerçek GNS3 projesinden paket kayıtları (25 Kasım 2026)

Kayıtlar GNS3 API'siyle (`lab/gns3_capture.py`) beş bağlantıda aynı anda alındı. Kayıt sürerken gerçek VPCS uçlarından
trafik üretildi: `ip dhcp` (SAT-PC1, FAB-PC1), internete ping, ACL'e takılan ping, SNC-WEB'e tcp/80.
Alanlar `tshark 4.6.10` ile çıkarıldı; her satırın altındaki filtre Wireshark'ta aynı paketleri gösterir.

| Dosya | Bağlantı | Görülen protokoller |
|---|---|---|
| `G1_SNR-Gi0-2_ISS-Gi0-0.pcap` | SNR-RTR ↔ ISS-RTR (WAN) | NAT sonrası ICMP, GRE içinde OSPF + DHCP + ICMP, CDP |
| `G2_ISS-Gi0-1_FAB-RTR-Gi0-0.pcap` | ISS-RTR ↔ FAB-RTR | GRE içinde OSPF, DHCP relay, ICMP |
| `G3_CORE1-Gi0-0_CORE2-Gi0-0.pcap` | CORE1 ↔ CORE2 (Po1 üyesi) | LACP, OSPF hello, CDP |
| `G4_ERS-SAT-Gi0-0_DAG1-Gi1-0.pcap` | ERS-SAT ↔ DAG1 (trunk) | 802.1Q, HSRP, Rapid-PVST+, DTP, DHCP, ICMP, TCP |
| `G5_ERS-SAT-Gi0-2_SAT-PC1.pcap` | ERS-SAT ↔ SAT-PC1 (erişim portu) | DHCP DORA, ARP, ICMP, TCP, HSRP, STP |

## 1. DHCP relay, GRE tünelinin içinden (G2)

Filtre: `dhcp`

| t (sn) | Dış IP (GRE) | İç IP | Mesaj | `giaddr` | Verilen adres |
|---|---|---|---|---|---|
| 27,52 | 198.51.100.6 → 198.51.100.1 | 172.18.10.1 → 172.20.20.3 | Discover | 172.18.10.1 | – |
| 27,53 | 198.51.100.1 → 198.51.100.6 | 172.20.254.6 → 172.18.10.1 | Offer | 172.18.10.1 | 172.18.10.100 |
| 28,53 | 198.51.100.6 → 198.51.100.1 | 172.18.10.1 → 172.20.20.3 | Request | 172.18.10.1 | – |
| 28,53 | 198.51.100.1 → 198.51.100.6 | 172.20.254.6 → 172.18.10.1 | ACK | 172.18.10.1 | 172.18.10.100 |

- FAB-PC1'in yayın (broadcast) isteği FAB-RTR'de tekil (unicast) pakete çevriliyor: hedef DAG1'in Loopback0 adresi
  (172.20.20.3), `giaddr` = FAB-RTR'nin LAN adresi (172.18.10.1). DHCP sunucusu havuzu `giaddr`'a bakarak seçiyor.
- Paket ISS-RTR'den geçerken GRE ile sarılı: ISS yalnız 198.51.100.x dış adreslerini görüyor, şirket içi
  adresleri bilmiyor. Tünelin amacı bu.

## 2. NAT/PAT (G1 ve G5 karşılaştırması)

Filtre: `icmp && !gre`

| Kayıt | Kaynak → Hedef | Adet |
|---|---|---|
| G5 (SAT-PC1 portu) | 172.16.10.100 → 203.0.113.1 (echo request) | 5 |
| G1 (WAN) | **198.51.100.1** → 203.0.113.1 (echo request) | 8 (5 SAT-PC1 + 3 FAB-PC1) |
| G1 (WAN) | 203.0.113.1 → 198.51.100.1 (echo reply) | 8 |

Aynı ping LAN'da özel adresle, WAN'da SNR-RTR'nin dış adresiyle görülüyor. FAB-PC1'in internet trafiği de önce tünelden
Merkez'e geliyor (G1'de `gre && icmp`: 172.18.10.100 ↔ 203.0.113.1), sonra SNR'de çevrilip aynı hattan çıkıyor.

## 3. LACP ve hızlı OSPF zamanlayıcıları (G3)

Filtre: `lacp` ve `ospf`

- LACP: iki uçtan da 3'er LACPDU, port 1, aktör ve partner durumu `0x3d` (Activity, Aggregation, Synchronization,
  Collecting, Distributing bitleri açık). Demet sağlıklı, iki uç anlaşmış.
- OSPF: 172.20.254.1 → 224.0.0.5, 88 Hello. **Hello aralığı 1 sn, dead aralığı 4 sn.** Hızlı yakınsama modülünün
  (`extensions/fast-convergence`) cihazda etkin olduğunun paket düzeyinde kanıtı. Po1 tek mantıksal arayüz olduğu
  için OSPF paketleri yalnız bir üyeden gidiyor; kayıtta tek yön görünmesi bundan.

## 4. HSRP ve Rapid-PVST+ (G4)

Filtre: `hsrp` ve `stp`

| VLAN | Gönderen | Durum | Öncelik | Sanal IP | Hello / Hold |
|---|---|---|---|---|---|
| 10 (etiketli) | 172.16.10.2 (DAG1) | Active (16) | 110 | 172.16.10.1 | 1 / 3 sn |
| 10 (etiketli) | 172.16.10.3 (DAG2) | Standby (8) | 90 | 172.16.10.1 | 1 / 3 sn |
| 90 (native, etiketsiz) | 172.16.90.2 (DAG1) | Active (16) | 110 | 172.16.90.1 | 1 / 3 sn |
| 90 (native, etiketsiz) | 172.16.90.3 (DAG2) | Standby (8) | 90 | 172.16.90.1 | 1 / 3 sn |

- DAG2'nin HSRP paketleri bu hatta da görünüyor: DAG2 → Po2 L2 trunk → DAG1 → ERS-SAT yolundan geliyor.
- STP: VLAN 10 ve native VLAN için kök köprü `0c41.0065.0000` (DAG1), BPDU'yu kökün kendisi gönderiyor
  (bayraklar `0x3c`: Designated, Learning, Forwarding). `show spanning-tree root` çıktısıyla aynı.
- VLAN 10 çerçeveleri 802.1Q etiketli, VLAN 90 çerçeveleri etiketsiz: native VLAN 90.

## 5. Uç tarafında DHCP, ACL reddi ve TCP (G5)

Filtre: `dhcp || icmp || tcp`

- DHCP DORA: Offer ve ACK 172.16.10.2'den (DAG1 SVI), verilen adres 172.16.10.100, ağ geçidi 172.16.10.1 (HSRP sanal
  IP), DNS 172.16.50.11.
- ACL reddi: 172.16.10.100 → 172.16.20.11 için 3 echo request, karşılığında 172.16.10.2'den 3 adet
  **ICMP tip 3 kod 13** (administratively prohibited). `ACL-V10-IN` paketi SVI girişinde düşürüyor.
- İnternet: 5 echo request, 5 echo reply.
- TCP: 172.16.10.100 → 172.16.50.12:80 SYN, karşılığında SYN+ACK. Servis portu izinli.

## Arıza kaydı (önceki tur)

`../core1_snr.pcap` ve `../core2_snr.pcap`: CORE1 durdurulurken SNR-RTR'nin iki uplink'i. Ping'ler CORE1 hattında
~16. saniyede kesiliyor, ~29. saniyeden itibaren CORE2 hattından akıyor. Filtre: `icmp || ospf`.
