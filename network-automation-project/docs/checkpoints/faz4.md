# Faz 4 — Python Otomasyon Çekirdeği            Tarih: 2026-11-24

## Ne yapıldı
- Klasör iskeleti, `devices.yaml` (13 IOS cihazı + ağ geneli değişkenler), `consoles.yaml` (GNS3 proje dosyasından, 13/13 port).
- Faz 1–3 için 12 Jinja2 şablonu (`<rol>_faz<N>.j2`).
- `deploy.py`: `--phase`, `--only`, `--dry-run`, `--workers`, `--list`; `.env` desteği; konsol uyandırma + 3 deneme; IOS hata satırını komutuyla raporlar.
- `gen_inventory.py` (konsol portları: GNS3 API veya proje dosyası), `fake_ios.py` (sahte konsol testi).
- `../lab/`: GNS3 olmadan IOSv/IOSvL2 imajlarını QEMU ile çalıştıran mini laboratuvar (`lab.py`, `console.py`, `validate_all.py`, `pair_test.py`).

## Test ortamı (önemli sınır)
Bu makinede GNS3/VMware yok ve boş RAM ~2 GB; 30 düğümlük topoloji açılamadı.
Testler **gerçek Cisco IOS imajlarında** (IOSvL2 15.2, IOSv 15.9(3)M6) ama **fabrika ayarında yeni cihazlarda** yapıldı:
cihazlar tek tek, yalnız iki dağıtım switch'i birlikte çalıştırıldı. Asıl GNS3 projesindeki kayıtlı config'lere dokunulmadı.

## Hangi komutla doğrulandı
| Komut | Sonuç |
|---|---|
| `deploy.py --phase 1 2 3 --dry-run` | 13 cihaz, 0 hata |
| `fake_ios.py --selftest` | BASARILI |
| `lab/validate_all.py` (13 cihaz, tek tek, gerçek IOS) | **13/13 TAMAM**: Faz 1–3 sıfır IOS hatası; ikinci basıştan sonra `show running-config` birebir aynı |
| `lab/pair_test.py` (DAG1 + DAG2 kablolu) | **11/11 kontrol geçti** (aşağıda) |

### İkili test ayrıntısı (`lab/logs/pair_test.txt`)
| Kontrol | Sonuç |
|---|---|
| İki cihaza Faz 1+2+3 basışı | 114 sn, 0 hata |
| LACP: DAG1 `Po2(SU)`, iki üye `(P)` | Geçti |
| OSPF: DAG1 komşusu 172.20.20.4 `FULL`, `Vlan254` üstünden | Geçti |
| DAG1 alan sınır yönlendiricisi (ABR 0/100) | Geçti |
| HSRP: DAG1 Active 10/30/50/90, DAG2 Active 20/40/60 | Geçti |
| STP: VLAN 10 kökü DAG1, VLAN 20 kökü DAG2 | Geçti |
| DAG1'de 6 DHCP havuzu | Geçti |
| DAG2 Lo0 → DAG1 Lo0 ping (OSPF rotası) | Geçti |
| F4 senaryosu: DAG1 durdurulunca DAG2 yedi VLAN'da Active | Geçti |

## Beklenen ↔ gerçek
| Madde (yol haritası Faz 4) | Durum |
|---|---|
| 1. Klasör, envanter, şablonlar | Tamam |
| 2. Tek cihazda `--dry-run`, sonra gerçek | Tamam (gerçek IOSvL2) |
| 3. İdempotentlik testi | Tamam, 13 cihazın hepsinde |
| 4. "Sıfır cihaz → config" demosu ve süre | **Kısmen**: sıfır cihazdan basış 13 cihazda tek tek yapıldı; 13'ü birlikte ölçülmedi. Ölçülen: cihaz başına faz ≈ 20–40 sn, iki DAG'a üç faz 114 sn |

## Karşılaşılan sorun ve çözüm
1. **Konsol takılması.** Netmiko çıkarken konsoldan `exit` yapıyor; sonraki bağlantıda IOS lisans metni basıyor ve ilk komut zaman aşımına uğruyordu. Çözüm: `wake_console()` + 3 deneme. Ara sıra bir IOS log satırı yine ilk denemeyi düşürüyor, ikinci deneme geçiyor.
2. **Kaybolan açıklama.** `no switchport` arayüz `description`'ını siliyor; ilk basışta Port-channel açıklaması kayboluyor, ikincide geliyordu (idempotentlik farkı olarak yakalandı). Şablonlarda açıklama `no switchport`'tan sonraya alındı.
3. **`no ip address`.** Dokümandaki Faz 1-D bloğunda vardı; Faz 2'den sonra Faz 1 yeniden basılırsa IP'leri silerdi. Şablondan çıkarıldı.

## Sonradan eklenenler (Faz 6'daki 9 cihazlı koşunun bulguları)
Bu notun yazıldığı sırada yalnız tek cihaz ve iki cihazlı testler vardı. Dokuz cihaz birlikte çalıştırılınca
`deploy.py` ve şablonlarda dört değişiklik daha gerekti; ayrıntı `faz6.md` "Karşılaşılan sorunlar" bölümünde:
- Stub alan tanımı tünel arayüzünden önceye alındı (`snr_faz3.j2`, `fab_faz3.j2`).
- `deploy.py` her basıştan sonra `running-config`'i geri okuyor, eksik satırı yeniden basıyor (`confcheck.py`).
- `%` ile başlayan tüm IOS yanıtları raporlanıyor (yalnız `% Invalid` değil).
- Routed Port-channel açıklaması Faz 2 şablonlarında yeniden yazılıyor.

Ölçülen süre: sıfırdan 9 cihaza Faz 1+2+3, doğrulama dâhil **583 sn** (doğrulamasız ilk koşuda 345 sn); donanım hızlandırmasız emülasyonda.

## Yapılmayanlar / sonraki adım için ayarlama
- Asıl GNS3 projesindeki (elle kurulan Faz 0–3) `running-config` ile şablon çıktısı **karşılaştırılmadı**; o projenin çalıştığı makine ve enable parolası gerekir. MRK-DAG1'de elle girilen DHCP havuz adları şablondakilerden (`SAT, PER, BIS, YNT, MSF, FAB`) farklıysa çakışabilir.
- Uçtan uca testler (GRE tüneli, NAT, DHCP relay, ACL matrisi, Core halkası) tam topoloji ister; yapılmadı.
- `.env` içindeki parolalar lab için üretilmiş test değerleridir; asıl projede kendi parolalarınla değiştir.
