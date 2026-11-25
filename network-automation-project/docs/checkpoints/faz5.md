# Faz 5 — Doğrulama ve "Ağ Sağlık Raporu"            Tarih: 2026-11-24

## Ne yapıldı
- `core/scripts/validate.py`: canlı durumu `devices.yaml`'daki beklenen durumla karşılaştırır, konsol tablosu + `reports/health_*.json` üretir. Çıkış kodu 0 sağlıklı, 1 sorunlu.
- Beklenen durum envantere eklendi: `links` (23 IOS–IOS kablo), `expected.etherchannel`, `expected.ospf` (14 giriş), `expected.tunnel`. HSRP beklentisi `network.svis`'ten türetilir.
- `--partial`: seçilmeyen cihazlara bakan beklentiler "ATLANDI" sayılır; topolojinin bir parçasıyla çalışmayı sağlar.
- TextFSM/ntc-templates kullanılmadı; çıktılar betiğin kendi düzenli ifadeleriyle ayrıştırılıyor (sürüm bağımlılığı yok).

## Kontroller
| Kontrol | Komut | Beklenen |
|---|---|---|
| Erişim | konsol bağlantısı | 13/13 |
| Kablolama | `show cdp neighbors detail` | 23 link, iki uçtan (46 giriş) |
| EtherChannel | `show etherchannel summary` | CORE: Po1/Po2 `RU`; DAG: Po1 `RU`, Po2 `SU`; üyeler `P` |
| OSPF | `show ip ospf neighbor` | 14 giriş `FULL`, doğru arayüzde |
| HSRP | `show standby brief` | DAG1 Active 10/30/50/90, DAG2 Active 20/40/60 |
| Tünel | `show interfaces Tunnel0` | `up/up` |

## Hangi komutla doğrulandı (gerçek IOSv/IOSvL2, QEMU lab)
| Senaryo (`lab/faz5_test.py`, DAG1+DAG2) | Rapor |
|---|---|
| 1. Sağlıklı durum | 2/2 sağlıklı, 24 OK, çıkış 0 |
| 2. DAG1 `Gi0/2` kapalı (LACP üye kaybı) | 0/2 sağlıklı, 6 HATA, çıkış 1 |
| 3. DAG1 `Gi0/2`+`Gi0/3` kapalı (Po2 düştü) | 15 HATA: CDP, EtherChannel `SD`, OSPF komşuluk yok, HSRP çift Active |
| 4. Portlar açıldı | 2/2 sağlıklı, çıkış 0 |

`lab/wan_test.py` (üç router): sağlıklı rapor; `Tunnel0` kapatılınca rapor kırmızı (Tunnel0 `administratively down`, iki uçta OSPF komşuluk yok).

Örnek kırmızı çıktı:
```
MRK-DAG1      SORUNLU     7    5    9
   x CDP Gi0/2            beklenen: MRK-DAG2 Gi0/2                   gercek: komsu yok
   x EtherChannel Po2     beklenen: Po2(SU) Gi0/2(P) Gi0/3(P)        gercek: Po2(SU) Gi0/2(D) Gi0/3(P)
   x HSRP Vlan20          beklenen: Standby                          gercek: Active
```

## Karşılaşılan sorun ve çözüm / bulgular
1. **Test betiği hatası (ürün değil).** İlk koşuda 2. ve 3. aşama yeşil kaldı; nedeni test betiğimin portu kapatamamasıydı. Kapatma adımı `deploy.push` üzerinden yapılınca rapor doğru şekilde kırmızıya döndü.
2. **Tek LACP üyesi kaybında geçici çift HSRP Active.** DAG1'de bir üye kapatıldığında DAG1 45 sn sonra hâlâ VLAN 20/40/60'ta kendini Active görüyordu. Olası neden: karşı uç linkin düştüğünü görmüyor (GNS3/QEMU sanal linkleri taşıyıcı kaybını iletmez) ve LACP yavaş zamanlayıcıyla (30 sn PDU, 90 sn zaman aşımı) üyeyi demette tutup trafiğin bir kısmını ölü linke gönderiyor. Bu neden doğrulanmadı. Yol haritasındaki F1 demosunda "kayıp yok" beklentisi bu yüzden tutmayabilir; `lacp rate fast` denenmeye değer.

## Sonraki faz için ayarlama
- 13 cihazlık tam rapor (46 CDP girişi, 14 OSPF, 14 HSRP) bu makinede alınamadı; en büyük koşu 9 cihazdı (bkz. `faz6.md`).
- `validate.py` çıktısı `extensions/tests` (pytest) ve `extensions/dashboard` tarafından girdi olarak kullanılıyor.
