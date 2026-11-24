# Faz 2 — L3 Routing ve Yüksek Erişilebilirlik            Doğrulama tarihi: 2026-11-25

Gerçek GNS3 projesinde betiklerle doğrulandı. Ham çıktılar: `lab/logs/gns3_kanit.txt`, `lab/logs/gns3_links.txt`,
`lab/logs/gns3_links_f7f6.txt`, `lab/logs/gns3_f3_sonra.txt`, `lab/logs/gns3_f4_sonra.txt`.

## Ne yapıldı
- OSPF: omurga alan 0 (CORE, DAG, SNR), kullanıcı VLAN'ları alan 100, Tesis alan 300 (totally stubby).
- HSRP: VLAN başına yük paylaşımı (DAG1 dört VLAN'da, DAG2 üç VLAN'da Active).
- İsteğe bağlı hızlandırma: OSPF hello 1 / dead 4, HSRP 1 / 3 (`extensions/fast-convergence`).

## Hangi komutla doğrulandı
| Komut | Sonuç |
|---|---|
| `show ip ospf neighbor` (CORE1, CORE2, DAG1, DAG2, SNR, FAB) | 14 komşuluk girişi, hepsi `FULL` |
| `show standby brief` (DAG1, DAG2) | 4 + 3 Active |
| `validate.py` | 13/13 sağlıklı, 97/97 |
| `lab/gns3_links.py`, `lab/gns3_failover.py` | Aşağıdaki arıza tablosu |

## Beklenen ↔ gerçek
| Kontrol | Beklenen | Gerçek |
|---|---|---|
| OSPF komşulukları | 14 giriş | CORE1 3, CORE2 3, DAG1 2, DAG2 2, SNR 3, FAB 1 = 14 |
| DAG1 Active | VLAN 10, 30, 50, 90 | Aynı (öncelik 110) |
| DAG2 Active | VLAN 20, 40, 60 | Aynı (öncelik 110) |
| VLAN'lar arası ping | Geçer | BIS-PC1 → SAT-PC1 4/4 |
| OSPF zamanlayıcıları (kayıt G3) | hello 1, dead 4 | Hello paketinde 1 / 4 |
| HSRP zamanlayıcıları (kayıt G4) | 1 / 3 | Hello paketinde 1 / 3 |

### Arıza senaryoları (gerçek VPCS'ten 0,5 sn aralıklı ping, hızlı zamanlayıcılar açık)
| # | Eylem | Kayıp | En uzun kesinti | Beklenen |
|---|---|---|---|---|
| F1 | CORE1 `Gi0/0` kapatıldı (Po1'in bir üyesi) | 0/160 | 0 sn | Kayıp yok |
| F2 | CORE1 `Gi0/0–1` kapatıldı (Po1 düştü) | 0/200 | 0 sn | Halkanın öbür yönünden devam |
| F3 | CORE1 durduruldu | – | 14,2 sn (önce 61,3 sn) | Kendiliğinden döner |
| F4 | DAG1 durduruldu | – | 14,2 sn (önce ~65 sn) | HSRP DAG2'ye geçer |
| F5 | DAG1 `Gi1/0` kapatıldı (ERS-SAT birincil uplink) | 6/160 | 9,6 sn | RSTP yedek porta geçer |
| F8 | DAG1 `Gi1/2` kapatıldı (ERS-SRV birincil uplink) | 14/160 | 6,6 sn | Sunucu erişimi sürer |
| F7 | SNR `Tunnel0` kapatıldı | Tesis izole, Merkez etkilenmedi | geri açınca 15 sn'de döndü | Aynı |
| F6 | SNR `Gi0/2` (WAN) kapatıldı | internet ve Tesis kesildi, Merkez içi sürdü | geri açınca 29 sn'de döndü | Aynı |

## Karşılaşılan sorun ve çözüm
- **Düğüm arızasında ~60 sn kesinti.** Sanal bağlantıda komşu port "down" olmuyor; arıza OSPF dead süresi dolunca
  anlaşılıyor. Hızlı zamanlayıcılarla 14 sn'ye indi. Daha kısası için BFD gerekir, IOSvL2 desteklemiyor.
- **F5 ve F8'de 6–10 sn kesinti.** Yol haritası 1–2 sn bekliyordu. Yazılım emülasyonunda RSTP geçişi ve MAC
  tablosunun yenilenmesi daha uzun sürüyor; gerçek donanımda süre farklı olur.
- **İlk koşuda F7 ve F6 "geri gelmedi" göründü.** Betik sabit süre bekliyordu ve o an ARP çözümlemesi sürüyordu.
  Betik yoklayarak ölçecek biçimde düzeltildi; ikinci koşuda 15 ve 29 sn.
- **F4 sırasında yeni DHCP kirası yok.** Tek DHCP sunucusu DAG1; tasarım değiştirilmedi.

## Sonraki faz için ayarlama
- Zamanlayıcılar linkin iki ucunda aynı olmalı; modül ikisini birlikte basar, `--rollback` ikisini birlikte geri alır.
