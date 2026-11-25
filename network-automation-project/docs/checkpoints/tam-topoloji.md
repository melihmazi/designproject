# Tam Topoloji Koşusu ve Kalan Modüller            Tarih: 2026-11-24

Önceki notlarda açık kalan her madde bu koşuda kapatıldı: 13 cihaz birlikte, gerçek GNS3 projesiyle karşılaştırma,
F1/F2/F5/F6/F8 demoları, saldırı testleri, canlı geri alma, Ansible, izleme, IPv6 ve panonun görsel kontrolü.

## Ortam
- 13 gerçek IOSv / IOSvL2 düğümü QEMU'da (TCG), yaklaşık 8 GB RAM. `lab/up.py` sıfırlar, başlatır, bootstrap eder (221 sn).
- 17 VPCS yerine `lab/hosts.py`: scapy ile benzetilen uçlar (ARP, ICMP, DHCP, TCP/UDP, SLAAC, ping6, kaçak DHCP sunucusu, MAC taşması).
- Her düğümde bant dışı yönetim portu (QEMU user-net): SSH `127.0.0.1:22xx`, SNMP `127.0.0.1:161xx`.
- Senaryo: `lab/full_test.py <aşama...>`; ham çıktılar `lab/logs/full_run*.txt`.

## Sonuç özeti

| Aşama | Kontrol | Sonuç |
|---|---|---|
| deploy, health, backup, e2e | 60 | 59 geçti; kalan A6 gerçek bir hataydı, düzeltildi ve geçti |
| failover (F1–F8), attack_before, harden, attack_after, rollback | 116 | 116 geçti |
| ipv6, ipv6_rollback | 26 | 26 geçti |
| monitor | 5 | 5'in 3'ü ilk turda geçti; kalan 2 test beklentisi hatasıydı (aşağıda), düzeltildi |
| Ansible | 3 koşu | changed=0, sonra 3 düzeltme, sonra yine changed=0 |

Çevrimdışı test sayısı 47'ye çıktı (6 canlı test ayrıca).

## Çekirdek (13 cihaz birlikte)
- Sıfırdan Faz 1+2+3: 513 sn, 0 hata. İkinci basış (idempotentlik): 298 sn, 0 hata.
- Sağlık raporu 13/13 (97 kontrol). 14 OSPF komşuluğu FULL, HSRP 4+3, STP beş erişim switch'inde doğru kök.
- DHCP: 7 uç kira aldı; FAB-PC1 kirası GRE üzerinden relay ile geldi (giaddr 172.18.10.1).
- NAT: SAT-PC1 ve FAB-PC1 internete çıkıyor, SNR çeviri tablosunda ikisi de var.
- ACL matrisi (Bölüm 12.3, 18 satır) canlıda 18/18; altı ACL'in sayaçları artıyor.

## Yük devretme ölçümleri

| Demo | Ne yapıldı | Sürekli ping kaybı | En uzun kesinti |
|---|---|---|---|
| F1 | CORE1 Po1'in bir üyesi kapatıldı | 0/80 | 0 sn |
| F2 | Po1'in tamamı kapatıldı; rota halkanın öbür yönüne döndü | 0/120 | 0 sn |
| F5 | ERS-SAT birincil uplink kapatıldı | 17/80 | 8,5 sn (RSTP) |
| F8 | ERS-SRV birincil uplink kapatıldı | 11/80 | 5,5 sn (RSTP) |
| F7 | GRE tüneli kapatıldı | Tesis izole, Merkez etkilenmedi | geri açınca düzeldi |
| F6 | SNR WAN portu kapatıldı | internet ve Tesis kesildi, Merkez içi sürdü | geri açınca düzeldi |
| F3 | CORE1 tamamen durduruldu | 118/200 | **59 sn** |
| F4 | DAG1 tamamen durduruldu | 130/200 | **65 sn** |

**F3 ve F4 bulgusu.** Düğüm tümden durunca komşu portlar "down" olmuyor (GNS3'te de sanal linkte durum böyle),
arıza ancak OSPF dead süresi (40 sn) dolunca anlaşılıyor. HSRP 10 sn'de devrediyor ama dönüş trafiği OSPF'i bekliyor.
Tasarım değiştirilmedi. İyileştirme isteyen için: transit arayüzlerde `ip ospf hello-interval 1` / `dead-interval 4`
ya da BFD. Ayrıca F4 sırasında DHCP yok: tek DHCP sunucusu DAG1.

## Bu koşuda bulunan gerçek hatalar

1. **`ip default-gateway` yok sayılıyor.** IOSvL2'de `ip routing` varsayılan açık olduğu için erişim switch'leri başka
   VLAN'dan yönetim adresinden yanıt veremiyordu (A6: BIS → 172.16.90.11). Şablonlara
   `ip route 0.0.0.0 0.0.0.0 <ağ geçidi>` eklendi. **Aynı kusur gerçek GNS3 projesinde de var** (6 L2 switch).
2. **Sertleştirme geri alma şablonu DHCP snooping'i kapatamıyordu.** Arayüz kipindeyken gönderilen
   `no ip dhcp snooping` arayüz komutu sanılıp reddediliyordu; uplink'lerden "trust" kalkmış, snooping açık kalmıştı
   (DHCP kesik). Şablona `exit` eklendi, regresyon testi yazıldı.
3. **Doğrulama yanlış alarmı.** `confcheck` `no switchport port-security ...` satırlarını ve büyük harfle yazılan
   IPv6 adreslerini "eksik" sayıyordu. İkisi de düzeltildi.
4. **Yeniden başlatılan switch routed Port-channel açıklamalarını kaybediyor.** Gerçek projede açıklamaların
   olmamasının nedeni bu. Sapma denetimi yakalıyor, `deploy.py` aynı şablonu basarak onarıyor (koşuda gösterildi:
   11/13 → 13/13).

## Güvenlik sertleştirme: saldırı testleri

| Test | Sertleştirme öncesi | Sertleştirme sonrası |
|---|---|---|
| Kaçak DHCP sunucusu (SAT-PC1) | Kurban iki Offer gördü: gerçek ve kaçak | Yalnız gerçek Offer; Discover güvenilmeyen porta hiç iletilmedi |
| MAC taşması (60 sahte MAC) | Portta 60 MAC öğrenildi | 2 MAC, ihlal sayacı 59, port açık kaldı (restrict) |

Sertleştirilmiş ağda uçtan uca testlerin tamamı yeniden geçti (DHCP relay dahil), OSPF MD5 ile 14 komşuluk FULL.
`--rollback` 13 cihazda hatasız; ardından sapma raporu 13/13.

## IPv6 dual-stack (`extensions/ipv6`)
- Plan: `2001:db8:acad:<vlan>::/64`, OSPFv3 IPv4 ile aynı alanlar, GRE tüneli IPv6 da taşıyor, ISS'e statik rota.
- Canlı: 14 OSPFv3 komşuluğu FULL, 6 uç SLAAC ile adres aldı, FAB-PC1 tünelden sunucuya ve internete erişti.
- Ağ geçidi seçimi: HSRP active olan DAG "High" tercihli RA yolluyor; uçlar onu seçti.
- IPv6 ACL: BIS → SAT geçer; SAT → PER, MSF → sunucu, MSF → DAG loopback, FAB → BIS engellenir; MSF → internet geçer.
- IPv4 etkilenmedi (sağlık 13/13). `--rollback` sonrası running-config'te IPv6 satırı kalmadı.
- Not: ilk turda "MSF → sunucu geçti" görünmüştü. ACL doğruydu; uç benzetimi switch'in "yasak" ICMPv6 hatasını
  ping yanıtı sanıyordu. Düzeltildi.

## İzleme (`extensions/monitoring`)
- SNMP v2c, salt okunur, ACL ile yalnız izleme istasyonuna açık. 13/13 cihaz okundu (çalışma süresi, CPU, arayüzler).
- CORE1 Gi0/0 kapatılınca: `ALARM MRK-CORE1: LINK`, olay kaydı `Gi0/0 up -> down`; açılınca alarm kalktı.
- Pano "Canlı izleme (SNMP)" bölümü tarayıcıda kontrol edildi.
- İlk turda kalan iki kontrol: ikinci `--setup`'ta IOS'un "Duplicate permit" uyarısı (artık zararsız sayılıyor) ve
  karşı ucun link kaybını görmesi beklentisi (lab linkleri UDP olduğu için görmez; beklenti kaldırıldı).
- Lab notu: QEMU user-net `restrict=on` iken UDP yanıtı dışarı çıkmıyor; yönetim ağında kısıt kaldırıldı.

## Ansible (`extensions/ansible`)
- Kontrol düğümü: QEMU'da RAM'den çalışan Alpine Linux (`lab/ansible_vm.py`), ansible-core 2.17, cisco.ios 11.7.
- Envanter `devices.yaml`'dan üretiliyor; bağlantı SSH `network_cli`.
- Koşu 1: `deploy.py`'nin kurduğu ağda 12 cihaz **changed=0** (iki araç aynı hedefi tarif ediyor).
- Koşu 2: elle bozulan üç ayar (port açıklaması, HSRP önceliği, OSPF passive) düzeltildi, changed=3.
- Koşu 3: yeniden changed=0.

## Gerçek GNS3 projesiyle karşılaştırma
`lab/extract_saved.py` taşınabilir projedeki 13 cihazın kayıtlı startup-config'ini çıkarır. Şablonlarla fark dört kalemdir:

| Fark | Cihaz | Açıklama |
|---|---|---|
| Routed Po açıklamaları yok | CORE1/2, DAG1/2 | Yeniden başlatmada kayboluyor (bulgu 4); şablon geri ekler |
| `ip helper-address 172.16.50.10` fazla | DAG1/2 SVI'ları | VPCS'e giden ölü relay artığı; zararsız |
| DHCP üst dışlama aralığı ve `domain-name` eksik | DAG1 | Şablonun eklediği iyileştirme |
| Statik varsayılan rota eksik | 6 L2 switch | Bulgu 1; gerçek projeye de uygulanmalı |

Geri kalan her satır birebir aynı (SNR-RTR, ISS-RTR, FAB-RTR tamamen uyumlu).

## Gerçek proje GNS3'te (aynı bilgisayar)

GNS3 2.2.61 (projenin sürümü) ve Npcap kuruldu. Taşınabilir proje `C:\Users\merts\GNS3\projects\DesignProject`
altına açıldı; özgün `.gns3project.zip` dosyasına dokunulmadı. GNS3 VM kullanılmıyor (VMware yok, Hyper-V açık):
düğümler yerel GNS3 sunucusunda QEMU 11 ile, donanım hızlandırma olmadan çalışıyor.

| Kontrol | Sonuç |
|---|---|
| Proje yükleme | 30 düğüm (13 Cisco + 17 VPCS), 40 bağlantı, hepsi başladı |
| `validate.py` (elle kurulmuş gerçek config üzerinde) | **13/13 sağlıklı, 97/97 kontrol** |
| `lab/gns3_vpcs.py` (gerçek VPCS uçlarından ping) | 7/7 beklenen sonuç |

- VPCS sonuçları: SAT-PC1 ağ geçidine, sunucuya ve internete erişiyor; Satış → Personel ACL ile engelleniyor;
  FAB-PC1 adresini DHCP relay ile aldı (172.18.10.100), tünelden sunucuya ve internete erişiyor.
- **Varsayılan rota bulgusu gerçek projede de doğrulandı:** düzeltmeden önce BIS-PC1 → 172.16.90.11
  (ERS-SAT yönetim adresi) 0/4.

### Switch parolaları ve düzeltmelerin basılması (24 Kasım, ikinci tur)

10 switch'in enable parolası belgelerde yoktu (kayıtlı özetler hiçbir bilinen değerle eşleşmedi), bu yüzden ilk turda
yalnız salt okunur kontroller koşabildi. İkinci turda parola şöyle sıfırlandı:

1. Switch'lerin disk katmanları (`hda_disk.qcow2`) `lab/gns3_disk_yedek/` altına taşındı (özgün hâlleri orada duruyor).
2. GNS3 her switch'i boş diskle açtı. `lab/gns3_reset_switch.py`, daha önce diskten çıkarılmış kayıtlı yapılandırmayı
   (`lab/gns3_export/saved/*.cfg`) konsoldan satır satır geri yazdı; yalnız `enable secret` ve `admin` parolası
   `lab/gns3_env.txt` içindeki yeni değerle değiştirildi (dosya git dışında).
3. Yüklenen yapılandırma özgün kayıtla satır satır karşılaştırıldı: **10 switch'te eksik satır 0.** Tek fark, yeni
   oluşturulan SVI'ların kapalı gelmesiydi (`no shutdown` ile açıldı).

Sonra `lab/gns3_fix.py` yalnız bulunan düzeltmeleri bastı (tüm fazı değil; satırlar çekirdek şablonlarından üretilir):

| Düzeltme | Cihaz | Sonuç |
|---|---|---|
| `ip route 0.0.0.0 0.0.0.0 <ağ geçidi>` | 5 erişim switch'i + FAB-ERS-1 | BIS-PC1 → 172.16.90.11 **0/4 → 4/4** |
| Routed Port-channel açıklamaları | CORE1, CORE2, DAG1, DAG2 | Girdi; yeniden başlatmada yine kayboluyor, `gns3_fix.py` tekrar basıyor |

| Kontrol (düzeltmelerden sonra) | Sonuç |
|---|---|
| `validate.py` | 13/13 sağlıklı, 97/97 |
| `lab/gns3_vpcs.py` | 8/8 (yönetim adresi ping'i artık beklenen sonuçlar arasında) |
| `backup.py` (13 cihaz, enable ile) | 13/13 |
| `drift.py` (gerçek yedek ↔ şablonlar) | 11/13 uyumlu; DAG1 ve DAG2'deki fark daha önce açıklanan iki kategori (DHCP havuzunda `domain-name` yok, SVI'larda fazladan `ip helper-address`) |

Router'lar yol haritasındaki parolayı kullanmaya devam ediyor. `lab/gns3_run.py sw|rtr <betik>` doğru parola grubunu
ortam değişkenlerine koyup betiği çalıştırır (değerler ekrana yazılmaz).

### Hızlı yakınsama (`extensions/fast-convergence`) ve gerçek GNS3'te ölçüm

Tam düğüm arızasındaki ~60 sn'lik kesinti OSPF dead süresinden (40 sn) geliyordu. İsteğe bağlı modül alan 0 transit
arayüzlerinde `hello 1 / dead 4`, DAG'lardaki 7 HSRP grubunda `timers 1 3` ayarlar (CORE1/2, DAG1/2, SNR-RTR;
`--rollback` ile geri alınır). Ölçüm `lab/gns3_failover.py` ile: gerçek SAT-PC1 (VPCS) internete 0,5 sn aralıkla ping
atarken düğüm GNS3 API'siyle durdurulur.

| Senaryo | Önce | Sonra |
|---|---|---|
| CORE1 tamamen durdu | **61,3 sn** | **14,2 sn** |
| DAG1 tamamen durdu | 65 sn (QEMU lab ölçümü) | **14,2 sn** |

Kalan ~14 sn: dead süresi (4 sn) + SPF bekleme süreleri + VPCS'in kayıp ping başına zaman aşımı. Daha da kısaltmak
için `timers throttle spf` ya da BFD gerekir (IOSvL2 BFD'yi desteklemiyor).

Paket kaydı (`docs/captures/`, Wireshark ile açılır): CORE1 durdurulurken SNR-RTR'nin iki uplink'i yakalandı.
`core1_snr.pcap` içinde ICMP istekleri ~16. saniyede kesiliyor; `core2_snr.pcap` içinde ~29. saniyeden itibaren aynı
akış CORE2 üzerinden devam ediyor. Önerilen görüntü filtresi: `icmp || ospf`.

GNS3 2.2.61 (Windows) notu: bir düğüm durdurulup yeniden başlatılınca konsol sarmalayıcısı bağlantıları düşürüyor
(WinError 10053). `POST /v2/projects/<id>/nodes/<id>/console/reset` düzeltir; `gns3_failover.py` bunu kendisi yapar.

Çalıştırma (GNS3 arayüzü açık olmadan da olur):

```powershell
& "C:\Program Files\GNS3\gns3server.exe" --local --host 127.0.0.1 --port 3080      # ayrı pencerede bırak
curl.exe -X POST http://127.0.0.1:3080/v2/projects/load -H "Content-Type: application/json" -d '{\"path\": \"C:/Users/merts/GNS3/projects/DesignProject/DesignProject.gns3\"}'
$env:NET_CONSOLE_HOST = "127.0.0.1"; $env:NET_NO_ENABLE = "1"
& $py core\scripts\validate.py
& $py ..\lab\gns3_vpcs.py
python ..\lab\gns3_run.py sw core\scripts\backup.py --only '@grup'      # enable isteyen işler (sw ya da rtr)
python ..\lab\gns3_failover.py MRK-CORE1                                 # arıza ölçümü
```

Arayüzle açmak için GNS3'ü başlat ve `DesignProject` projesini aç (önce arka plandaki `gns3server` kapatılmalı).
Dikkat: proje yüklenirken 5000–5058 arası konsol portları boş olmalı (QEMU lab kapalı); doluysa GNS3 portları
sessizce kaydırır ve öyle kaydeder.

### Üçüncü tur (25 Kasım): yol haritasının kalan kabul ölçütleri gerçek projede

Bu turda her şey gerçek GNS3 projesinde ve gerçek VPCS uçlarıyla koşuldu. Faz bazında kanıt: `faz0.md` … `faz3.md`.

| Ne | Betik | Sonuç |
|---|---|---|
| Bağlantı arızaları F1, F2, F5, F8, F7, F6 | `lab/gns3_links.py` | 15/15 (F7 ve F6'nın dönüş kontrolü ikinci koşuda; aşağıda) |
| ACL tablosu A1–A12 + DHCP (yol haritası 12.3, 12.4) | `lab/gns3_acl.py` | 16/16; altı ACL'in sayaçları arttı |
| Beş paket kaydı | `lab/gns3_capture.py` | `docs/captures/gercek/analiz.md` |
| Canlı pytest | `pytest extensions/tests --live` | 53 geçti |
| IPv6 dual-stack | `extensions/ipv6/ipv6.py` | 7 cihaza basıldı; OSPFv3 komşulukları 14/14 FULL |
| Güvenlik sertleştirme | `extensions/security-hardening/harden.py` | 12 cihaza basıldı, 0 hata |
| Sertleştirme sonrası sağlık, VPCS, ACL/DHCP | `validate.py`, `gns3_vpcs.py`, `gns3_acl.py` | 13/13 (97/97), 8/8, 16/16 |
| Yapılandırma geçmişi | `backup.py --sanitize` + `commit_backups.py` | 13/13 yedek, yerel geçmiş deposuna işlendi |
| Sapma raporu (şablon + üç genişletme) | `drift.py --also ...` | 11/13 uyumlu (aşağıda) |
| Son yapılandırmayla CORE1 arızası | `lab/gns3_failover.py MRK-CORE1` | en uzun kesinti 14,2 sn |

**Ölçülen arıza süreleri** (hızlı zamanlayıcılar açık, 0,5 sn aralıklı ping):

| # | Eylem | Kayıp | En uzun kesinti |
|---|---|---|---|
| F1 | CORE1 `Gi0/0` kapatıldı | 0/160 | 0 sn |
| F2 | CORE1 `Gi0/0–1` kapatıldı | 0/200 | 0 sn |
| F5 | DAG1 `Gi1/0` kapatıldı | 6/160 | 9,6 sn |
| F8 | DAG1 `Gi1/2` kapatıldı | 14/160 | 6,6 sn |
| F7 | SNR `Tunnel0` kapatıldı | Tesis izole, Merkez etkilenmedi | geri açınca 15 sn'de döndü |
| F6 | SNR `Gi0/2` kapatıldı | internet ve Tesis kesildi, Merkez içi sürdü | geri açınca 29 sn'de döndü |

İlk koşuda F7 ve F6'nın "geri geldi" kontrolü kaldı: betik sabit süre bekleyip tek ping deniyordu. Ağ o an dönmüştü
(hemen ardından `gns3_vpcs.py` 8/8). Betik yoklayarak süreyi ölçecek biçimde değiştirildi, ikinci koşu 7/7.

**IPv6, gerçek VPCS'ten** (`lab/logs/gns3_ipv6_vpcs.txt`):
- SAT-PC1 `ip auto` ile `2001:db8:acad:10::/64` içinden, FAB-PC1 `2001:db8:acad:110::/64` içinden adres aldı (SLAAC).
- SAT-PC1 → `2001:db8:ffff::1` (simüle IPv6 internet) 3/4; FAB-PC1 → aynı hedef 4/4 (tünelden).
- MSF-DZ1 → `2001:db8:acad:10::2` engellendi: ICMPv6 tip 1 kod 5 (misafir IPv6 ACL'i).
- Sunucu VPCS'lerine IPv6 adresi verilmedi; `2001:db8:acad:50::11` pingi yanıtsız. Beklenen durum.
- VPCS, RA'daki yönlendirici tercihini (High) dikkate almıyor: SAT-PC1 ağ geçidi olarak DAG2'yi seçti. Erişim etkilenmiyor.

**Sapma raporunda yapılan temizlik:**
- DAG1 DHCP havuzları şablonla eşitlendi: `.201–.254` dışlaması ve `domain-name` eklendi (`lab/gns3_fix.py`).
- Hızlı yakınsama modülü ürettiği satırları `extensions/fast-convergence/rendered/` altına yazıyor; sapma raporuna
  `--also` ile verilince "fazla" görünmüyor.
- Port Security'nin kendi öğrendiği `mac-address sticky <MAC>` satırları artık sapma sayılmıyor.
- Kalan tek fark, DAG1 ve DAG2 SVI'larındaki `ip helper-address 172.16.50.10`. Yol haritasındaki SNC-DHCP (Docker)
  planından kalma; sunucu VPCS olduğu için etkisiz. Bilerek silinmedi.

**Gerçek projenin şu anki durumu:** çekirdek Faz 1–3 + iki düzeltme + hızlı yakınsama + IPv6 + sertleştirme uygulanmış
ve kayıtlı (`write memory`). Geri almak için sırayla (her biri önce `sw`, sonra `rtr` ile):

```powershell
python ..\lab\gns3_run.py sw extensions\security-hardening\harden.py --rollback --only '@grup'
python ..\lab\gns3_run.py sw extensions\ipv6\ipv6.py --rollback --only '@grup'
python ..\lab\gns3_run.py sw extensions\fast-convergence\hizli.py --rollback --only '@grup'
```

Canlı gösterim sırası: `docs/sunum-rehberi.md`.

### Arayüzde canlı Wireshark (25 Kasım, öğlen)

Proje GNS3 arayüzünden açıldı, 13 cihaz arayüzden başlatıldı (sağlık 13/13), SNR-RTR `Gi0/2` ↔ ISS-RTR `Gi0/0`
bağlantısında **Start capture** ile canlı kayıt açıldı, filtre `icmp || gre`. Ekran görüntüsü:
`docs/captures/gercek/canli-wireshark.jpg`. Görülenler:
- SAT-PC1'in internete pingi WAN'da 198.51.100.1 kaynak adresiyle (NAT).
- FAB-PC1'in pingi önce GRE içinde 172.18.10.100 kaynak adresiyle, hemen ardından NAT'lı olarak 198.51.100.1 ile.
- FAB-PC1'in DHCP Discover ve Offer paketleri GRE içinde (relay).

Arayüz tuzağı: arayüzün QEMU tercihinde "Require hardware acceleration" işaretliydi; bu bilgisayarda hızlandırma
olmadığı için düğümler "HAXM acceleration support is not installed" hatasıyla başlamıyordu. Tercihler penceresindeki
değişiklik sunucuya ulaşmadı; `%APPDATA%\GNS3.2\gns3_gui.ini` içinde iki ayar `false` yapıldı.

## Doğrulanamayanlar
- Zaman ölçümleri TCG (yazılım emülasyonu) altında alındı; gerçek donanımda ya da KVM'li GNS3 VM'de süreler farklı olur.
- Gerçek GNS3 projesinde sınanmayanlar: saldırı testleri (kaçak DHCP, MAC taşması), SNMP izleme ve Ansible. Bunlar
  saldırgan uç, bant dışı yönetim portu ve Linux denetim makinesi ister; QEMU lab'da sınandı (yukarıda).
- Sunucular VPCS: HTTP, DNS, FTP, posta servislerinin kendisi sınanmadı, yalnız port bazlı erişim kuralları.
- Gerçek projede her arıza senaryosu birer kez ölçüldü; süreler koşudan koşuya birkaç saniye oynar.
- QEMU lab'da uçlar VPCS değil, benzetimdi; gerçek VPCS davranışı üçüncü turda gerçek projede sınandı.
- Son izleme tekrar koşusu, bilgisayar başka bir işle yüklüyken konsol zaman aşımına düştü; izleme sonuçları bir önceki
  temiz turdan (13/13, alarm, olay, alarmın kalkması) alınmıştır.
