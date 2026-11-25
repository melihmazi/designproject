# Python Destekli Kurumsal Ağ Otomasyonu ve Yüksek Erişilebilirlikli GNS3 Simülasyonu
## Ana Proje Dosyası (Master) — Topoloji + Cihaz Haritası + Artımlı Yol Haritası, GNS3 cihazlarına uyarlanmış


> **📌 GÜNCEL DURUM & DEVİR NOTU (Faz 0 – Faz 3 Tamamlandı | Sıradaki Adım: Faz 4)**
>
> * **Mevcut Durum:** Bu dokümandaki **Faz 0, Faz 1, Faz 2 ve Faz 3** adımlarının tamamı GNS3 topolojisi üzerinde kurulmuş, doğrulanmış ve kaydedilmiştir (`write memory` / VPCS `save`). Sıradaki çalışma **Bölüm 8 — Faz 4 (Python Otomasyon Çekirdeği)** ve **Bölüm 9** kapsamındadır[cite: 33].
> * **Kritik Mimari Değişiklik (Docker Yerine Cisco IOS DHCP):** Dokümandaki Faz 3-E bölümünde yer alan Docker (`snc-base`) kurulumu yerine, kaynak tüketimini düşük tutmak amacıyla dokümandaki yedek plan uygulanmıştır[cite: 33].
>   * `SNC-DHCP` dahil 5 sunucu düğümü (`172.16.50.10 – .14`) VPCS üzerinde statik IP ile bırakılmıştır[cite: 33].
>   * Tüm departmanların (`SAT, PER, BIS, YNT, MSF, FAB`) DHCP havuzları (`ip dhcp pool`) doğrudan **`MRK-DAG1`** üzerinde yapılandırılmıştır[cite: 33].
>   * Üretim tesisindeki (`FAB-RTR`) DHCP relay yönlendirmesi `ip helper-address 172.20.20.3` (`MRK-DAG1` Loopback0) olarak güncellenmiştir.
> * **Faz 4 Ekibi İçin Önemli Uyarı:** `deploy.py` için Jinja2 şablonları (`dag_faz3.j2` ve `fab_faz3.j2`) hazırlanırken Docker komutları atlanmalı; bunun yerine `MRK-DAG1` üzerindeki `ip dhcp excluded-address` / `ip dhcp pool` blokları ile `FAB-RTR` üzerindeki `172.20.20.3` helper adresi şablona dahil edilmelidir[cite: 33].

> **📌 GÜNCEL DURUM (24 Kasım 2026) — Faz 4, 5, 6 ve beş genişletme modülü tamamlandı**
>
> * Kod: `network-automation-project/` (README oradan başlar). Faz notları: `network-automation-project/docs/checkpoints/` (`faz4.md`, `faz5.md`, `faz6.md`, `genisletme.md`).
> * Test ortamı: bu makinede GNS3 olmadığı için `lab/` altındaki QEMU laboratuvarı kullanıldı (gerçek IOSv / IOSvL2 imajları). En büyük koşu 13 IOS cihazının 9'u birlikte.
> * Bu dokümandaki bloklara göre şablonlarda yapılan düzeltmeler: Faz 1-D'deki `no ip address` çıkarıldı; Port-channel açıklaması `no switchport`'tan sonraya alındı ve Faz 2'de yeniden yazılıyor; Faz 3-B'de `area 300 stub` tanımı tünel arayüzünden önce basılıyor.
> * Açık kalanlar: asıl GNS3 projesindeki elle kurulmuş config'lerle karşılaştırma, 13 cihazın tamamının birlikte koşusu, Ansible / izleme / IPv6 modülleri.

**Ders:** Design Project (araştırma görevlisi gözetiminde)
**Senaryo:** Anadolu Makina A.Ş. — Merkez Ofis (İstanbul) + Üretim Tesisi (Kocaeli)
**Platform:** GNS3 + GNS3 VM (IOSv L2 / IOSv L3 / VPCS / Docker), Python 3.x — **cloud platformu yok**
**Toplam düğüm:** 30 (13 IOS cihazı + 17 uç/sunucu düğümü)
**Bu dosyanın yerini aldığı kaynaklar:** `design-project-topoloji-v3.md`, `design-project-cihaz-haritasi.md`, `design-project-roadmap.md`

> **Bu dosya tek başına yeterlidir.** Üç eski dosyadaki her bilgi (envanter, VLAN/IP planı, OSPF/HSRP, 7 faz, 8 genişletme modülü, klasör yapısı, git ve checkpoint stratejisi) burada birleştirildi; port isimleri senin GNS3'ündeki gerçek port şemasına (`Gi0/0 … Gi3/3`) çevrildi ve kaynakta bulduğum hatalar düzeltildi. Düzeltmelerin tam listesi **Bölüm 1**'de, kısa günlüğü **Bölüm 15**'te.

---

## İçindekiler

0. Kısa Özet ve Okuma Rehberi
1. Mevcut GNS3 Durumuna Göre Kritik Uyarlamalar ve Düzeltmeler
2. Tam Cihaz Envanteri (30 düğüm)
3. Port Şeması ve Kablolama (40 link, GNS3 çizim kontrol listesi)
4. Topoloji Diyagramları
5. Adresleme Planı (VLAN, P2P, yönetim, HSRP, STP)
6. OSPF Alan Planı (düzeltilmiş)
7. Erişim Politikası (ACL matrisi) ve NAT
8. Artımlı Yol Haritası — Faz 0 … Faz 6
9. Python Otomasyon Projesi (kod iskeletleri)
10. Genişletme Modülleri (çekirdeğe dokunmadan)
11. Klasör Yapısı, Git Stratejisi, Checkpoint Stratejisi
12. Doğrulama ve Demo Senaryoları (failover testleri dahil)
13. Sorun Giderme (GNS3 / IOSv'ye özgü)
14. Kaynak / Performans Notları
15. Düzeltme Günlüğü ve Eski İsim Eşlemesi

---

## 0. Kısa Özet ve Okuma Rehberi

**Proje ne?** İki lokasyonlu (Merkez + Tesis) kurumsal bir ağın GNS3'te kurulması: 3 katmanlı (Core/Dağıtım/Erişim) Merkez, GRE tüneliyle bağlı Üretim Tesisi, simüle internet; üzerine Python (Netmiko) ile toplu config basma, otomatik doğrulama ("Ağ Sağlık Raporu") ve yedekleme.

**Yapım felsefesi:** Her faz kendi başına çalışan, `show` komutlarıyla kanıtlanabilir bir sonuç verir (artımlı teslimat, BDUF değil). Faz 0–6 bitince proje zaten tamdır; zaman kalırsa Bölüm 10'daki modüller `core/` klasörüne dokunmadan eklenir.

**Şu anki durumun (ekran görüntüsüne göre):** 30 düğüm sürükle-bırak ile konmuş ve isimlendirilmiş; **henüz hiç kablo ve config yok.** Yani sıradaki iş Faz 0'dır.

**Hızlı yol haritası:**

| Faz | Odak | Çıktı |
|---|---|---|
| 0 | Ortam, kablolama, bootstrap | 40 link çekili, 13 IOS cihazına konsoldan erişim, CDP ile kablolama doğrulandı |
| 1 | L2 omurga (VLAN, trunk, LACP, RSTP) | VLAN izolasyonu, EtherChannel'lar `SU/RU`, STP kök/blocking doğru yerde |
| 2 | L3 + HA (OSPF multi-area, HSRP) | Tüm ağ pingable, Core/Dağıtım failover'ı canlı gösterilebilir |
| 3 | Kenar & servisler (WAN, GRE, NAT, DHCP relay, ACL) | İnternete çıkış, Merkez↔Tesis tüneli, departman bazlı kısıtlar |
| 4 | Otomasyon çekirdeği | `python deploy.py` ile sıfırdan tam config |
| 5 | Doğrulama | Tek komutla "Ağ Sağlık Raporu" |
| 6 | Yedekleme & analiz | Tarih damgalı `backups/` + Wireshark analiz raporu |

**Okuma sırası önerisi:** Önce Bölüm 1 (neyin değiştiğini anla) → Bölüm 3 (kabloları çiz) → Bölüm 8 (fazları sırayla uygula). Bölüm 5–7 referans tablolarıdır, fazlarda sürekli bakacaksın.

---

## 1. Mevcut GNS3 Durumuna Göre Kritik Uyarlamalar ve Düzeltmeler

Bu bölüm en önemli kısım: kaynak dosyalar ile senin gerçek GNS3 projen arasındaki farklar ve kaynakta bulduğum hatalar. Her madde için **ne yaptığımı** ve **neden** yazdım.

### 1.1 Senin cihaz tiplerinden kaynaklanan uyarlamalar

| # | Konu | Kaynak dosyada | Senin GNS3'ünde | Bu dosyadaki karar |
|---|---|---|---|---|
| **U1** | **Switch port isimleri** | `Gi0/0 … Gi0/8` (tek slot) | `Gi0/0–0/3`, `Gi1/0–1/3`, `Gi2/0–2/3`, `Gi3/0–3/3` (16 port, `Gi0/4` yok) | Tüm port numaraları yeniden eşlendi: eski `Gi0/4→Gi1/0`, `0/5→1/1`, `0/6→1/2`, `0/7→1/3`, `0/8→2/0`. Bölüm 3'teki tablo **tek doğru kaynaktır.** |
| **U2** | **Router port isimleri** | `Gi0/0 … Gi0/2` | `Gi0/0–0/3` (4 port) | Yeterli: en kalabalık router (SNR-RTR) 3 port kullanıyor, 1 port boşta. |
| **U3** | **Sunucular (SNC-\*)** | "Docker container, gerçek servisler" | GNS3'te şu an **VPCS** ikonu görünüyor | **VPCS DHCP/DNS/Web sunucusu olamaz** (sadece istemci: `ip dhcp`, ping, trace). Önerim: önce sadece **SNC-DHCP**'yi Docker'a çevir (roadmap'in DHCP relay demosu buna bağlı), diğer 4'ü sonra. Ayrıntı: Bölüm 8, Faz 3-E. |
| **U4** | **KAP-1 (AP) ve MSF-DZ1** | KAP-1 trunk bağlantılı AP, MSF-DZ1 kablosuz bağlı | İkisi de **VPCS**; VPCS'in tek ağ kartı var, trunk yapamaz, iki bağlantı alamaz | Kablosuz GNS3'te zaten simüle edilemez. Karar: **KAP-1** = ERS-BIS'te VLAN 90 access (AP yönetim arayüzünü temsil eder, `172.16.90.16`); **MSF-DZ1** = ERS-BIS'te VLAN 60 access (kablosuz bağlantıyı temsilen kablolu). Raporda bu sınırlama açıkça yazılmalı. İstersen KAP-1'i GNS3'ün yerleşik "Ethernet switch" düğümüyle değiştirip gerçek bir ara cihaz yapabilirsin (isteğe bağlı). |
| **U5** | **FAB-ERS1 ismi** | `FAB-ERS1` | GNS3'te `FAB-ERS-1` | Bu dosyada senin etiketin kullanıldı: **FAB-ERS-1** (hostname da aynısı). |
| **U6** | **Yönetim erişimi (Python → cihaz)** | "SSH ile erişilebilir" (ama nasıl ulaşılacağı tanımsız) | Topolojide Cloud/NAT düğümü yok | Python'un cihazlara ulaşması için **GNS3 VM'in telnet konsol portları** kullanılır (`192.168.130.128:50xx`, ekran görüntüsündeki Topology Summary). Netmiko `cisco_ios_telnet` bunu destekler; ekstra düğüm gerekmez. İsteğe bağlı gerçek-SSH yolu: Ek A (Bölüm 8, Faz 0). |

### 1.2 Kaynak dosyalarda bulduğum tasarım hataları (düzeltildi)

| # | Hata | Neden sorun | Düzeltme |
|---|---|---|---|
| **D1** | **KAP-1 IP çakışması** — KAP-1 yönetim IP'si `172.16.60.2`, ama bu adres **MRK-DAG1'in VLAN 60 SVI IP'si** | İki cihaz aynı IP'yi kullanır, ARP çakışması | KAP-1 → `172.16.90.16` (VLAN 90 yönetim ağı) |
| **D2** | **OSPF Area 200 / 300 tutarsızlığı** — SNR-RTR'ın Area 0'da hiç arayüzü yok (Core linkleri Area 200, tünel Area 300) | SNR gerçek ABR olamaz; Area 300 omurgaya bağlı değil; virtual-link stub alandan geçemez; totally-stubby Area 200 içinde ASBR (SNR) default'u enjekte edemez | **Area 200 kaldırıldı.** SNR-RTR'ın Core'a giden 2 linki **Area 0**'a alındı. Tünel Area 300 (totally stubby) olarak kaldı; SNR bu sayede gerçek bir Area0↔Area300 ABR'si. Bölüm 6. |
| **D3** | **DAG1–DAG2 kenarı routed `/30` iken "RSTP yedek uplink = blocking" iddiası** | Dağıtım switch'leri arasında L2 bağlantı yoksa erişim switch'inin iki uplink'i arasında döngü oluşmaz; RSTP hiçbir şeyi bloklamaz (sadece VLAN 90 her uplink'te olduğu için karışık bir döngü oluşurdu). Kaynaktaki "birincil/yedek (blocking)" anlatımı ve Bölüm 7'deki "HSRP ↔ STP root hizalaması" fiilen çalışmazdı | DAG1–DAG2 **Po2'si L2 trunk** yapıldı (tüm VLAN'ları taşır) ve OSPF Area 0 komşuluğu bu trunk üzerinde **VLAN 254 SVI** (`172.20.254.12/30`) ile kuruldu. Böylece klasik "L2 interlink'li dağıtım üçgeni" oluşur: RSTP gerçekten bloklar, HSRP hello'ları DAG-DAG linkinden akar, kaynaktaki anlatım doğru hâle gelir. Halka (ring) topolojisi ve OSPF komşuluk sayısı **aynı** kaldı. |
| **D4** | **P2P adres notasyonu belirsiz** — tabloda "`.1 CORE1`, `.2 DAG1`" yazıyordu (alt ağ başlangıcına göre ofset mi, gerçek son oktet mi?) | `172.20.254.4/30` için `.1/.2` geçerli host değil; yanlış anlaşılırsa yanlış IP girilir | Bölüm 5.2'de **tam IP adresleri** yazıldı (ör. `172.20.254.5` ve `.6`). |
| **D5** | **Port-channel numaraları** — ASCII şemada Po1–Po4, tablolarda cihaz-yerel Po1/Po2 | Tutarsız | Cihaz-yerel numaralama kullanıldı: her Core/DAG'da Po1 ve Po2 (Bölüm 3.2). |
| **D6** | **FAB-RTR "VLAN 110 SVI"** — router'da SVI olmaz | Config yazılamaz | FAB-RTR Gi0/1 düz routed arayüz (`172.18.10.1/24`); FAB-ERS-1 portları VLAN 110 access, switch yönetimi `Vlan110` SVI'ında (`172.18.10.2`). |
| **D7** | **"idle-PC kalibrasyonu"** önerisi | idle-PC **Dynamips** (eski IOS) içindir; IOSv/IOSvL2 QEMU/KVM'de çalışır, idle-PC yok | Bölüm 14'te doğru kaynak notları: GNS3 VM RAM/CPU, KVM, başlatma sırası. |
| **D8** | **Roadmap'te VTP** (Faz 1 notunda zaten düzeltilmişti) | VTP v1/v2 tehlikeli | Tüm switch'lerde `vtp mode transparent` |
| **D9** | **Stateless ACL ile cevap trafiği** (kaynakta ACL politikası yoktu, ben tanımladım) | Gelen-yön ACL'ler dönüş paketlerini de keser | `established` / `echo-reply` satırları eklendi (Bölüm 7) |
| **D10** | **SNC-DHCP'nin cevap vermesi için ACL** | Sunucu çıkış ACL'i DHCP unicast yenilemeyi keserdi | `udp any host 172.16.50.10 eq 67` izni eklendi |

### 1.3 Roadmap'teki eski cihaz isimleri

Roadmap dosyası eski isimleri (`CORE-SW1`, `ACC-MUH`, `EDGE-RTR` …) kullanıyordu. Bu dosyada hepsi güncel isimlere çevrildi; eşleme tablosu Bölüm 15.2'de.

---

## 2. Tam Cihaz Envanteri (30 düğüm)

**Varsayım:** Switch düğümleri **IOSv L2 (vIOS-L2)**, router düğümleri **IOSv** imajı (portların `Gi0/0–3` / `Gi0/0–3…Gi3/3` yapısı bununla uyumlu). Farklıysa söyle, port planı etkilenmez ama komut ayrıntıları değişebilir.

| No | Hostname (GNS3 etiketi) | Rol | Katman | GNS3 düğüm tipi | Yönetim IP | Konsol (telnet) |
|---|---|---|---|---|---|---|
| 1 | MRK-CORE1 | Core anahtar 1 | Core | IOSvL2 + `ip routing` | Lo0 `172.20.20.1/32` | `192.168.130.128:____` |
| 2 | MRK-CORE2 | Core anahtar 2 | Core | IOSvL2 + `ip routing` | Lo0 `172.20.20.2/32` | `____` |
| 3 | MRK-DAG1 | Dağıtım anahtarı 1 | Dağıtım | IOSvL2 + `ip routing` | Lo0 `172.20.20.3/32` | `____` |
| 4 | MRK-DAG2 | Dağıtım anahtarı 2 | Dağıtım | IOSvL2 + `ip routing` | Lo0 `172.20.20.4/32` | `____` |
| 5 | MRK-ERS-SAT | Satış/Pazarlama erişim | Erişim | IOSvL2 (L2) | `172.16.90.11` (Vlan90) | `:5008` |
| 6 | MRK-ERS-PER | Personel erişim | Erişim | IOSvL2 (L2) | `172.16.90.12` | `:5010` |
| 7 | MRK-ERS-BIS | Bilgi İşlem erişim | Erişim | IOSvL2 (L2) | `172.16.90.13` | `____` |
| 8 | MRK-ERS-YNT | Üst Yönetim erişim | Erişim | IOSvL2 (L2) | `172.16.90.14` | `:5012` |
| 9 | MRK-ERS-SRV | Sunucu çiftliği erişim | Erişim | IOSvL2 (L2) | `172.16.90.15` | `:5014` |
| 10 | FAB-ERS-1 | Üretim Tesisi erişim | Şube | IOSvL2 (L2) | `172.18.10.2` (Vlan110) | `____` |
| 11 | SNR-RTR | Sınır (kenar) router | WAN | IOSv | Lo0 `172.20.20.5/32` | `:5020` |
| 12 | ISS-RTR | Simüle internet (ISS) | WAN | IOSv | — (OSPF dışı) | `____` |
| 13 | FAB-RTR | Tesis router'ı | WAN | IOSv | Lo0 `172.20.20.6/32` | `____` |
| 14 | SNC-DHCP | DHCP sunucusu | Sunucu | VPCS → **Docker** (isc-dhcp-server) | `172.16.50.10` | `:5048` |
| 15 | SNC-DNS | DNS sunucusu | Sunucu | VPCS → Docker (bind9) | `172.16.50.11` | `:5050` |
| 16 | SNC-WEB | Web sunucusu | Sunucu | VPCS → Docker (nginx) | `172.16.50.12` | `:5052` |
| 17 | SNC-POSTA | Posta sunucusu | Sunucu | VPCS → Docker (postfix+dovecot) | `172.16.50.13` | `:5054` |
| 18 | SNC-DOSYA | Dosya (FTP) sunucusu | Sunucu | VPCS → Docker (vsftpd) | `172.16.50.14` | `:5056` |
| 19 | KAP-1 | Misafir AP (yönetim arayüzü temsili) | Erişim | VPCS (statik) | `172.16.90.16` (VLAN 90) | `____` |
| 20 | SAT-PC1 | Satış PC 1 | Uç | VPCS | VLAN 10 – DHCP | `:5026` |
| 21 | SAT-PC2 | Satış PC 2 | Uç | VPCS | VLAN 10 – DHCP | `:5028` |
| 22 | PER-PC1 | Personel PC 1 | Uç | VPCS | VLAN 20 – DHCP | `:5034` |
| 23 | PER-PC2 | Personel PC 2 | Uç | VPCS | VLAN 20 – DHCP | `:5036` |
| 24 | BIS-PC1 | Bilgi İşlem PC 1 | Uç | VPCS | VLAN 30 – DHCP | `____` |
| 25 | BIS-PC2 | Bilgi İşlem PC 2 | Uç | VPCS | VLAN 30 – DHCP | `____` |
| 26 | BIS-YAZICI1 | Paylaşımlı yazıcı | Uç | VPCS (statik) | VLAN 30 – `172.16.30.5` | `____` |
| 27 | YNT-PC1 | Üst Yönetim PC 1 | Uç | VPCS | VLAN 40 – DHCP | `:5038` |
| 28 | YNT-TEL1 | IP telefon (temsili) | Uç | VPCS | VLAN 40 – DHCP | `:5058` |
| 29 | FAB-PC1 | Tesis PC 1 | Uç | VPCS | VLAN 110 – DHCP | `____` |
| 30 | MSF-DZ1 | Misafir dizüstü | Uç | VPCS | VLAN 60 – DHCP | `:5046` |

> **Konsol portları:** Ekran görüntüsündeki "Topology Summary"den okunabilen portlar yazıldı; `____` olanları panelde aşağı kaydırıp doldur (Bölüm 9'daki `inventory.yaml`'a da aynı değerler girilecek). Düğümü silip yeniden eklersen port değişir — Bölüm 9.1'de envanteri GNS3 REST API'sinden otomatik üreten bir yöntem de var.

**Katman sayım kontrolü:** Core 2 + Dağıtım 2 + Merkez erişim 5 + Şube switch 1 + Router 3 + Sunucu 5 + AP 1 + Uç cihaz 11 = **30** ✔

---

## 3. Port Şeması ve Kablolama

### 3.1 Port sıralama kuralı (senin switch'lerin için)

IOSvL2'de portlar 4'lü slotlar hâlinde sıralanır. "N. port" şöyle adlandırılır:

| Sıra | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Port | Gi0/0 | Gi0/1 | Gi0/2 | Gi0/3 | Gi1/0 | Gi1/1 | Gi1/2 | Gi1/3 | Gi2/0 | Gi2/1 | Gi2/2 | Gi2/3 | Gi3/0 | Gi3/1 | Gi3/2 | Gi3/3 |

Kaynak dosyadaki "5. port = `Gi0/4`" artık "5. port = `Gi1/0`" demektir. **Port kullanım özeti** (yeterli port var, en kalabalık cihaz 16 portun 9'unu kullanıyor):

| Cihaz | Kullanılan port | Boş |
|---|---|---|
| MRK-CORE1 / CORE2 | 5 | 11 |
| MRK-DAG1 / DAG2 | 9 | 7 |
| MRK-ERS-SAT / PER / YNT | 4 | 12 |
| MRK-ERS-BIS | 7 | 9 |
| MRK-ERS-SRV | 7 | 9 |
| FAB-ERS-1 | 2 | 14 |
| SNR-RTR | 3 (Gi0/0–0/2) | Gi0/3 |
| ISS-RTR / FAB-RTR | 2 | 2 |

### 3.2 Standart port şeması (kural)

- **Erişim switch'lerinde:** `Gi0/0` = birincil uplink, `Gi0/1` = yedek uplink, `Gi0/2`'den itibaren uç cihazlar.
- **Core/Dağıtımda:** `Gi0/0–Gi0/1` = Po1 (yukarı/yan), `Gi0/2–Gi0/3` = Po2, `Gi1/0`'dan itibaren tekil linkler.
- **Port-channel numaraları cihaz-yereldir:**

| Cihaz | Po1 | Po2 |
|---|---|---|
| MRK-CORE1 | → CORE2 (`Gi0/0–0/1`) | → DAG1 (`Gi0/2–0/3`) |
| MRK-CORE2 | → CORE1 (`Gi0/0–0/1`) | → DAG2 (`Gi0/2–0/3`) |
| MRK-DAG1 | → CORE1 (`Gi0/0–0/1`) | → DAG2 (`Gi0/2–0/3`) — **L2 trunk** |
| MRK-DAG2 | → CORE2 (`Gi0/0–0/1`) | → DAG1 (`Gi0/2–0/3`) — **L2 trunk** |

### 3.3 Tam link listesi — GNS3 çizim kontrol listesi (40 link)

GNS3'te kablo çekerken "Add a link" aracı bir cihaza tıklayınca port listesi açar; aşağıdaki sırayla çiz ve işaretle. **Çizimden sonra** `View → Show/Hide interface labels` ile etiketleri açıp tabloyla karşılaştır.

**A. Core / Dağıtım halkası (LACP demetleri: 8 fiziksel link)**

| Link | A tarafı | B tarafı | Not |
|---|---|---|---|
| L01 | MRK-CORE1 `Gi0/0` | MRK-CORE2 `Gi0/0` | Po1 (routed) |
| L02 | MRK-CORE1 `Gi0/1` | MRK-CORE2 `Gi0/1` | Po1 |
| L03 | MRK-CORE1 `Gi0/2` | MRK-DAG1 `Gi0/0` | CORE1 Po2 ↔ DAG1 Po1 (routed) |
| L04 | MRK-CORE1 `Gi0/3` | MRK-DAG1 `Gi0/1` | |
| L05 | MRK-CORE2 `Gi0/2` | MRK-DAG2 `Gi0/0` | CORE2 Po2 ↔ DAG2 Po1 (routed) |
| L06 | MRK-CORE2 `Gi0/3` | MRK-DAG2 `Gi0/1` | |
| L07 | MRK-DAG1 `Gi0/2` | MRK-DAG2 `Gi0/2` | DAG1 Po2 ↔ DAG2 Po2 (**L2 trunk**) |
| L08 | MRK-DAG1 `Gi0/3` | MRK-DAG2 `Gi0/3` | |

**B. Kenar / WAN (6 link)**

| Link | A tarafı | B tarafı | Not |
|---|---|---|---|
| L09 | MRK-CORE1 `Gi1/0` | SNR-RTR `Gi0/0` | `172.20.254.16/30`, Area 0 |
| L10 | MRK-CORE2 `Gi1/0` | SNR-RTR `Gi0/1` | `172.20.254.20/30`, Area 0 |
| L11 | SNR-RTR `Gi0/2` | ISS-RTR `Gi0/0` | `198.51.100.0/30` ("internet") |
| L12 | ISS-RTR `Gi0/1` | FAB-RTR `Gi0/0` | `198.51.100.4/30` ("internet") |
| L13 | FAB-RTR `Gi0/1` | FAB-ERS-1 `Gi0/0` | VLAN 110 (access) |
| L14 | FAB-ERS-1 `Gi0/1` | FAB-PC1 `e0` | VLAN 110 (access) |

**C. Erişim uplink'leri (10 link — her erişim switch'i iki Dağıtım'a bağlı)**

| Link | Dağıtım tarafı | Erişim tarafı | Rol |
|---|---|---|---|
| L15 | MRK-DAG1 `Gi1/0` | MRK-ERS-SAT `Gi0/0` | **Birincil** |
| L16 | MRK-DAG2 `Gi1/2` | MRK-ERS-SAT `Gi0/1` | Yedek |
| L17 | MRK-DAG1 `Gi1/1` | MRK-ERS-BIS `Gi0/0` | **Birincil** |
| L18 | MRK-DAG2 `Gi1/3` | MRK-ERS-BIS `Gi0/1` | Yedek |
| L19 | MRK-DAG1 `Gi1/2` | MRK-ERS-SRV `Gi0/0` | **Birincil** |
| L20 | MRK-DAG2 `Gi2/0` | MRK-ERS-SRV `Gi0/1` | Yedek |
| L21 | MRK-DAG2 `Gi1/0` | MRK-ERS-PER `Gi0/0` | **Birincil** |
| L22 | MRK-DAG1 `Gi1/3` | MRK-ERS-PER `Gi0/1` | Yedek |
| L23 | MRK-DAG2 `Gi1/1` | MRK-ERS-YNT `Gi0/0` | **Birincil** |
| L24 | MRK-DAG1 `Gi2/0` | MRK-ERS-YNT `Gi0/1` | Yedek |

**D. Uç cihaz bağlantıları (16 link)**

| Link | Switch portu | Uç cihaz | VLAN |
|---|---|---|---|
| L25 | MRK-ERS-SAT `Gi0/2` | SAT-PC1 `e0` | 10 |
| L26 | MRK-ERS-SAT `Gi0/3` | SAT-PC2 `e0` | 10 |
| L27 | MRK-ERS-PER `Gi0/2` | PER-PC1 `e0` | 20 |
| L28 | MRK-ERS-PER `Gi0/3` | PER-PC2 `e0` | 20 |
| L29 | MRK-ERS-BIS `Gi0/2` | BIS-PC1 `e0` | 30 |
| L30 | MRK-ERS-BIS `Gi0/3` | BIS-PC2 `e0` | 30 |
| L31 | MRK-ERS-BIS `Gi1/0` | BIS-YAZICI1 `e0` | 30 |
| L32 | MRK-ERS-BIS `Gi1/1` | KAP-1 `e0` | 90 (U4) |
| L33 | MRK-ERS-BIS `Gi1/2` | MSF-DZ1 `e0` | 60 (U4) |
| L34 | MRK-ERS-YNT `Gi0/2` | YNT-PC1 `e0` | 40 |
| L35 | MRK-ERS-YNT `Gi0/3` | YNT-TEL1 `e0` | 40 |
| L36 | MRK-ERS-SRV `Gi0/2` | SNC-DHCP | 50 |
| L37 | MRK-ERS-SRV `Gi0/3` | SNC-DNS | 50 |
| L38 | MRK-ERS-SRV `Gi1/0` | SNC-WEB | 50 |
| L39 | MRK-ERS-SRV `Gi1/1` | SNC-POSTA | 50 |
| L40 | MRK-ERS-SRV `Gi1/2` | SNC-DOSYA | 50 |

**Sayım:** 8 + 6 + 10 + 16 = **40 link** ✔ (Core/DAG tarafı 14, erişim tarafı 26).

### 3.4 Erişim uplink matrisi (birincil / yedek bir bakışta)

| Erişim switch | Birincil → | Yedek → | Neden birincil bu? (HSRP active) |
|---|---|---|---|
| ERS-SAT (VLAN 10) | DAG1 `Gi1/0` | DAG2 `Gi1/2` | VLAN 10 active = DAG1 |
| ERS-BIS (VLAN 30, 60) | DAG1 `Gi1/1` | DAG2 `Gi1/3` | VLAN 30 active = DAG1 (VLAN 60 active DAG2, aşağıdaki nota bak) |
| ERS-SRV (VLAN 50) | DAG1 `Gi1/2` | DAG2 `Gi2/0` | VLAN 50 active = DAG1 |
| ERS-PER (VLAN 20) | DAG2 `Gi1/0` | DAG1 `Gi1/3` | VLAN 20 active = DAG2 |
| ERS-YNT (VLAN 40) | DAG2 `Gi1/1` | DAG1 `Gi2/0` | VLAN 40 active = DAG2 |

> **Not (VLAN başına STP):** RSTP burada **Rapid-PVST+** olarak çalışır, yani kök ve blocking kararı **VLAN başınadır.** ERS-BIS'te VLAN 30'un kökü DAG1, VLAN 60'ın kökü DAG2 olduğundan `Gi0/0` VLAN 30'u, `Gi0/1` VLAN 60'ı taşır; ERS-PER ve ERS-YNT'de yönetim VLAN'ı 90'ın kökü DAG1 olduğundan VLAN 90 `Gi0/1`'den akar. Bu bir hata değil, VLAN başına yük paylaşımıdır; beklenen STP çıktıları Faz 1'de tablolandı.

---

## 4. Topoloji Diyagramları

### 4.1 Genel görünüm (cihaz numaraları envanterle birebir aynı)

```
                                   +--------------------+
                                   |    [12] ISS-RTR    |
                                   | Lo0 203.0.113.1/32 |
                                   +--------------------+
                                   Gi0/0              Gi0/1
                    198.51.100.0/30  |                  |  198.51.100.4/30
                                   Gi0/2              Gi0/0
 MERKEZ (İSTANBUL)          +----------------+   +----------------+        TESİS (KOCAELİ)
                            | [11] SNR-RTR   |<==|  GRE Tunnel0   |==>   +----------------+
                            | Lo0 .20.5      |   | 172.20.200.0/30|      | [13] FAB-RTR   |
                            +----------------+   | Area 300       |      | Lo0 .20.6      |
                             Gi0/0       Gi0/1   +----------------+      +----------------+
                               |           |                               Gi0/1
                             Gi1/0       Gi1/0                               |
                      +------------+  +------------+                       Gi0/0
                      |[01]CORE1   |==|[02]CORE2   |                  +----------------+
                      |Lo0 .20.1   |Po1|Lo0 .20.2  |                  | [10] FAB-ERS-1 |
                      +------------+  +------------+                  +----------------+
                         Po2 ||           || Po2                            Gi0/1
                         Po1 ||           || Po1                              |
                      +------------+  +------------+                  +----------------+
                      |[03]DAG1    |==|[04]DAG2    |                  | [29] FAB-PC1   |
                      |Lo0 .20.3   |Po2|Lo0 .20.4  |                  | VLAN 110       |
                      +------------+  +------------+                  +----------------+
                       HSRP act:       HSRP act:
                       V10 V30         V20 V40
                       V50 V90         V60
                       (Gi1/0 ...)     (Gi1/0 ...)
```

- Core + Dağıtım birlikte **dörtgen halka** kurar: CORE1 — CORE2 — DAG2 — DAG1 — CORE1; her kenar 2×1GE LACP.
- Halkanın 3 kenarı (Core-Core, Core-DAG ×2) **routed**; DAG1–DAG2 kenarı **L2 trunk** + VLAN 254 SVI (düzeltme D3).
- Merkez ↔ Tesis'in gerçek bağlantısı "internet" (ISS-RTR) üzerinden kurulan **GRE tüneli**dir.

### 4.2 Erişim katmanı (portlarla)

```
               +------------------------------------+       +------------------------------------+
               |            [03] MRK-DAG1           |=Po2===|            [04] MRK-DAG2           |
               |  HSRP active: V10, V30, V50, V90   | L2    |  HSRP active: V20, V40, V60        |
               +------------------------------------+ trunk +------------------------------------+
                 Gi1/0   Gi1/1   Gi1/2   Gi1/3   Gi2/0         Gi1/2   Gi1/3   Gi2/0   Gi1/0   Gi1/1
                   |P      |P      |P      :Y      :Y            :Y      :Y      :Y      |P      |P
                   |       |       |       :       :             :       :       :       |       |
              Gi0/0|  Gi0/0|  Gi0/0|  Gi0/1:  Gi0/1:        Gi0/1:  Gi0/1:  Gi0/1:  Gi0/0|  Gi0/0|
          +---------+ +---------+ +---------+ +---------+  (yedek uplink'ler)  +---------+ +---------+
          | ERS-SAT | | ERS-BIS | | ERS-SRV | | ERS-PER |                      | ERS-PER | | ERS-YNT |
          +---------+ +---------+ +---------+ +---------+                      +---------+ +---------+
```
> Yukarıdaki şema kalabalık olduğu için **kesin bağlantılar için Bölüm 3.3-C ve 3.4 tablosunu kullan.** Kural basit: *düz çizgi (P) = o VLAN'ın HSRP active'ine giden uplink; noktalı (Y) = diğer Dağıtıma giden yedek uplink.*

**Her erişim switch'inin altı:**

```
 ERS-SAT : Gi0/2 SAT-PC1   Gi0/3 SAT-PC2                                       (VLAN 10)
 ERS-PER : Gi0/2 PER-PC1   Gi0/3 PER-PC2                                       (VLAN 20)
 ERS-BIS : Gi0/2 BIS-PC1   Gi0/3 BIS-PC2   Gi1/0 BIS-YAZICI1                   (VLAN 30)
           Gi1/1 KAP-1 (VLAN 90)           Gi1/2 MSF-DZ1 (VLAN 60)
 ERS-YNT : Gi0/2 YNT-PC1   Gi0/3 YNT-TEL1                                      (VLAN 40)
 ERS-SRV : Gi0/2 SNC-DHCP  Gi0/3 SNC-DNS   Gi1/0 SNC-WEB  Gi1/1 SNC-POSTA  Gi1/2 SNC-DOSYA   (VLAN 50)
 FAB-ERS-1: Gi0/0 → FAB-RTR (VLAN 110)   Gi0/1 FAB-PC1 (VLAN 110)
```

### 4.3 Örnek paket yolları (haritayı okuma alıştırması)

| Akış | Yol |
|---|---|
| **SAT-PC1 → internet** | SAT-PC1 → ERS-SAT `Gi0/2` → `Gi0/0` → DAG1 `Gi1/0` (VIP `172.16.10.1` active) → DAG1 `Po1` → CORE1 `Po2` → CORE1 `Gi1/0` → SNR-RTR `Gi0/0` → NAT/PAT → `Gi0/2` → ISS-RTR → `203.0.113.1` |
| **PER-PC1 → SNC-WEB** | PER-PC1 → ERS-PER → DAG2 `Gi1/0` (VLAN 20 active) → ACL kontrolü → DAG2 SVI50 → ERS-SRV (DAG2 `Gi2/0` yedek uplink üstünden veya Po2 → DAG1 → `Gi1/2`, STP durumuna göre) → SNC-WEB |
| **FAB-PC1 DHCP** | FAB-PC1 broadcast → FAB-ERS-1 → FAB-RTR (`ip helper-address 172.16.50.10`) → GRE tüneli → SNR-RTR → CORE → DAG → SNC-DHCP; cevap aynı yolun tersi |
| **SAT-PC1 → FAB-PC1** | ... → DAG1 → CORE → SNR-RTR → **Tunnel0** (GRE) → FAB-RTR → FAB-ERS-1 → FAB-PC1. (NAT'a girmez: çıkış arayüzü Tunnel0) |
| **DAG1 arızasında (SAT-PC1)** | HSRP VLAN 10 active DAG2'ye geçer; ERS-SAT'ın STP'de blocking olan `Gi0/1`'i forwarding'e döner; yol DAG2 üzerinden devam eder |

---

## 5. Adresleme Planı

### 5.1 VLAN planı

| VLAN | Ad | Subnet | Gateway (HSRP VIP) | MRK-DAG1 gerçek IP | MRK-DAG2 gerçek IP | Yaşadığı yer |
|---|---|---|---|---|---|---|
| 10 | SAT | 172.16.10.0/24 | 172.16.10.1 | 172.16.10.2 | 172.16.10.3 | ERS-SAT |
| 20 | PER | 172.16.20.0/24 | 172.16.20.1 | 172.16.20.2 | 172.16.20.3 | ERS-PER |
| 30 | BIS | 172.16.30.0/24 | 172.16.30.1 | 172.16.30.2 | 172.16.30.3 | ERS-BIS |
| 40 | YNT | 172.16.40.0/24 | 172.16.40.1 | 172.16.40.2 | 172.16.40.3 | ERS-YNT |
| 50 | SRV | 172.16.50.0/24 | 172.16.50.1 | 172.16.50.2 | 172.16.50.3 | ERS-SRV |
| 60 | MSF (misafir) | 172.16.60.0/24 | 172.16.60.1 | 172.16.60.2 | 172.16.60.3 | ERS-BIS (MSF-DZ1 portu) |
| 90 | YNTM (yönetim / native) | 172.16.90.0/24 | 172.16.90.1 | 172.16.90.2 | 172.16.90.3 | Tüm erişim switch'leri + KAP-1 |
| 110 | FAB-LAN | 172.18.10.0/24 | 172.18.10.1 (FAB-RTR, HSRP yok) | — | — | FAB-ERS-1 |
| 254 | DAG-ARA (yalnızca DAG1–DAG2 transit) | 172.20.254.12/30 | — | 172.20.254.13 | 172.20.254.14 | **Sadece** DAG1 ve DAG2 (Po2 trunk) |

**Sunucular (VLAN 50, statik):** SNC-DHCP `.10`, SNC-DNS `.11`, SNC-WEB `.12`, SNC-POSTA `.13`, SNC-DOSYA `.14`.
**Statik uç cihazlar:** BIS-YAZICI1 `172.16.30.5`, KAP-1 `172.16.90.16` (D1 düzeltmesi).
**DHCP aralıkları (SNC-DHCP'de):** her kullanıcı VLAN'ında `.100 – .200` (VLAN 10, 20, 30, 40, 60, 110).

### 5.2 Link (P2P) adres tablosu — **tam adresler** (D4 düzeltmesi)

| Bağlantı | Subnet | Taraf A | Taraf B | Tip |
|---|---|---|---|---|
| CORE1 `Po1` — CORE2 `Po1` | 172.20.254.0/30 | CORE1 **.1** | CORE2 **.2** | Routed Po |
| CORE1 `Po2` — DAG1 `Po1` | 172.20.254.4/30 | CORE1 **.5** | DAG1 **.6** | Routed Po |
| CORE2 `Po2` — DAG2 `Po1` | 172.20.254.8/30 | CORE2 **.9** | DAG2 **.10** | Routed Po |
| DAG1 `Vlan254` — DAG2 `Vlan254` (Po2 trunk üstünde) | 172.20.254.12/30 | DAG1 **.13** | DAG2 **.14** | SVI (L2 trunk üstünde) |
| CORE1 `Gi1/0` — SNR `Gi0/0` | 172.20.254.16/30 | CORE1 **.17** | SNR **.18** | Routed port |
| CORE2 `Gi1/0` — SNR `Gi0/1` | 172.20.254.20/30 | CORE2 **.21** | SNR **.22** | Routed port |
| SNR `Gi0/2` — ISS `Gi0/0` | 198.51.100.0/30 | SNR **.1** | ISS **.2** | "İnternet" |
| ISS `Gi0/1` — FAB-RTR `Gi0/0` | 198.51.100.4/30 | ISS **.5** | FAB **.6** | "İnternet" |
| SNR `Tunnel0` — FAB-RTR `Tunnel0` (GRE) | 172.20.200.0/30 | SNR **.1** | FAB **.2** | GRE, Area 300 |
| FAB-RTR `Gi0/1` — FAB-ERS-1 `Gi0/0` | 172.18.10.0/24 | FAB-RTR **.1** | FAB-ERS-1 `Vlan110` **.2** | Routed / access |

> `198.51.100.0/24` (TEST-NET-2) ve `203.0.113.0/24` (TEST-NET-3) belgeleme amaçlı ayrılmış aralıklardır; "internet"i temsil etmek için kullanıldı, gerçek ağda asla kullanılmaz. Raporda küçük bir dipnot yaz.

### 5.3 Yönetim adresleri

| Cihaz | Yönetim arayüzü | Adres | Default gateway |
|---|---|---|---|
| MRK-CORE1/2, DAG1/2 | Loopback0 | 172.20.20.1 / .2 / .3 / .4 (/32) | — (OSPF) |
| SNR-RTR / FAB-RTR | Loopback0 | 172.20.20.5 / .6 (/32) | — (OSPF) |
| ERS-SAT / PER / BIS / YNT / SRV | Vlan90 | 172.16.90.11 / .12 / .13 / .14 / .15 | 172.16.90.1 (HSRP VIP) |
| FAB-ERS-1 | Vlan110 | 172.18.10.2 | 172.18.10.1 |
| KAP-1 (VPCS) | e0 | 172.16.90.16 | 172.16.90.1 |

### 5.4 HSRP planı (VLAN başına yük dengeleme)

| VLAN | Grup | VIP | Active (pri 110) | Standby (pri 90) |
|---|---|---|---|---|
| 10 | 10 | 172.16.10.1 | MRK-DAG1 | MRK-DAG2 |
| 20 | 20 | 172.16.20.1 | MRK-DAG2 | MRK-DAG1 |
| 30 | 30 | 172.16.30.1 | MRK-DAG1 | MRK-DAG2 |
| 40 | 40 | 172.16.40.1 | MRK-DAG2 | MRK-DAG1 |
| 50 | 50 | 172.16.50.1 | MRK-DAG1 | MRK-DAG2 |
| 60 | 60 | 172.16.60.1 | MRK-DAG2 | MRK-DAG1 |
| 90 | 90 | 172.16.90.1 | MRK-DAG1 | MRK-DAG2 |

DAG1 active: **10, 30, 50, 90** (4 grup) · DAG2 active: **20, 40, 60** (3 grup). Her ikisinde `preempt` açık.

### 5.5 STP (Rapid-PVST+) planı

| | VLAN 10, 30, 50, 90, 254 | VLAN 20, 40, 60 |
|---|---|---|
| **MRK-DAG1** | priority **4096** (kök) | priority **8192** (ikincil kök) |
| **MRK-DAG2** | priority **8192** | priority **4096** (kök) |
| Erişim switch'leri | varsayılan (32768) | varsayılan (32768) |

Kural: bir VLAN'ın STP kökü = o VLAN'ın HSRP active'i. L2 yolu ile L3 gateway aynı switch'te buluşur (trombon etkisi yok).

**Erişim portlarında standart:** `portfast` + `bpduguard`. **Tüm switch'lerde:** `vtp mode transparent`.

### 5.6 VPCS IP planı

| Faz | Adres kaynağı |
|---|---|
| Faz 1–2 (DHCP henüz yok) | **Statik**, test için: SAT-PC1 `172.16.10.11`, SAT-PC2 `.12`, PER-PC1 `172.16.20.11`, PER-PC2 `.12`, BIS-PC1 `172.16.30.11`, BIS-PC2 `.12`, YNT-PC1 `172.16.40.11`, YNT-TEL1 `.12`, MSF-DZ1 `172.16.60.11`, FAB-PC1 `172.18.10.11` (gateway = ilgili VIP/`.1`) |
| Faz 3 sonrası | `ip dhcp` (SNC-DHCP'den `.100–.200`) |
| Her zaman statik | BIS-YAZICI1, KAP-1, sunucular |

---

## 6. OSPF Alan Planı (düzeltilmiş — D2)

```
                               [ AREA 300 — totally stubby ]
                                 SNR ----Tunnel0---- FAB-RTR
                                  |  (SNR = ABR 0/300)  (172.18.10.0/24 buradan gelir)
                                  |
          [ AREA 0 — backbone ]   |
   SNR-RTR --Gi0/0-- CORE1 ====Po1==== CORE2 --Gi0/1-- SNR-RTR
                       ||                ||
                       Po2               Po2
                       ||                ||
                      DAG1 ====Vlan254==== DAG2        <-- DAG1/DAG2 = ABR 0/100
                       |                  |
          [ AREA 100 — standart: DAG SVI'ları 10/20/30/40/50/60/90, passive ]
```

| Alan | Tip | Kapsam | Rol |
|---|---|---|---|
| **Area 0** | Backbone | CORE1, CORE2, DAG1, DAG2 halkası (Po1, Po2'ler, `Vlan254`), CORE↔SNR linkleri (`172.20.254.16/30`, `.20/30`), tüm Loopback0'lar (SNR dahil) | Ring: tek link/tek node arızasında diğer yönden yeniden yönlenir |
| **Area 100** | Standart | DAG1/DAG2'deki VLAN 10/20/30/40/50/60/90 SVI'ları (**passive**) | DAG1/DAG2 = **ABR (0/100)** |
| **Area 300** | Totally stubby | SNR `Tunnel0` ↔ FAB-RTR `Tunnel0`, FAB-RTR Lo0 ve `Gi0/1` (172.18.10.0/24) | SNR = **ABR (0/300)**; FAB-RTR sadece ABR'nin ürettiği default rotayı alır |
| **ISS-RTR** | — | OSPF dışı | Statik/connected |

**Ek kurallar:**
- Router-ID'ler = Loopback0 adresleri (`172.20.20.1 … .6`).
- `auto-cost reference-bandwidth 10000` tüm OSPF cihazlarında (aksi hâlde 1G ve 2G LACP maliyetleri aynı çıkar).
- `passive-interface default`; sadece P2P transit arayüzlerinde `no passive-interface`.
- Transit linklerde `ip ospf network point-to-point` (DR/BDR seçimi yok, hızlı komşuluk).
- **Default rota:** SNR-RTR'da `ip route 0.0.0.0 0.0.0.0 198.51.100.2` + OSPF'te `default-information originate` (Area 0'da Type-5 default olarak Core/DAG'a yayılır; Area 300'e totally-stubby ABR olarak SNR kendisi default üretir).
- **Rekürsif yönlendirme koruması:** Tünel hedef adresleri (`198.51.100.x`) tünelin *içinden* öğrenilmemeli: FAB-RTR'da `ip route 198.51.100.0 255.255.255.252 198.51.100.5` (daha spesifik statik) bunu garanti eder.

**Beklenen OSPF komşuluk sayıları** (Faz 2 / Faz 5 doğrulaması):

| Cihaz | Komşular | Sayı |
|---|---|---|
| MRK-CORE1 | CORE2 (Po1), DAG1 (Po2), SNR (Gi1/0) | 3 |
| MRK-CORE2 | CORE1 (Po1), DAG2 (Po2), SNR (Gi1/0) | 3 |
| MRK-DAG1 | CORE1 (Po1), DAG2 (Vlan254) | 2 |
| MRK-DAG2 | CORE2 (Po1), DAG1 (Vlan254) | 2 |
| SNR-RTR | CORE1, CORE2, FAB-RTR (Tunnel0) | 3 |
| FAB-RTR | SNR-RTR (Tunnel0) | 1 |
| **Toplam giriş** | 7 komşuluk × 2 uç | **14** |

---

## 7. Erişim Politikası (ACL) ve NAT

> Kaynak dosyalarda net bir ACL politikası yoktu (sadece "departman bazlı kısıt" ve "misafir sunucuya erişemez" cümleleri). Aşağıdaki matris **önerilen** politikadır — kendi senaryona göre değiştirebilirsin; hoca sunumunda "neden böyle" sorusuna cevabın hazır olsun.

### 7.1 Politika matrisi (kaynak satır → hedef sütun)

| Kaynak ↓ / Hedef → | SAT 10 | PER 20 | BIS 30 | YNT 40 | SRV 50 | MSF 60 | YNTM 90 | FAB 110 | İnternet |
|---|---|---|---|---|---|---|---|---|---|
| **SAT 10** | – | ✗ | ✗ | ✗ | S | ✗ | ✗ | ✓ | ✓ |
| **PER 20** | ✗ | – | ✗ | ✗ | S | ✗ | ✗ | ✓ | ✓ |
| **BIS 30** (Bilgi İşlem) | ✓ | ✓ | – | ✓ | ✓ tam | ✗* | ✓ | ✓ | ✓ |
| **YNT 40** (Üst yönetim) | ✓ | ✓ | ✓ | – | S | ✗* | ✓ | ✓ | ✓ |
| **MSF 60** (misafir) | ✗ | ✗ | ✗ | ✗ | yalnız DNS+DHCP | – | ✗ | ✗ | ✓ |
| **FAB 110** | ✗ | ✗ | ✗ | ✗ | S | ✗ | ✗ | – | ✓ |

**S** = sadece servis portları (DNS 53, Web 80/443, SMTP 25 / POP3 110 / IMAP 143, FTP 21, DHCP 67, ICMP echo).
**\*** BIS/YNT'den misafir ağına istek gidebilir ama misafir ACL'i kasıtlı olarak sıkı olduğu için dönüş paketi kesilir → fiilen ✗ (stateless ACL sınırlaması).

### 7.2 ACL'ler (DAG1 **ve** DAG2 SVI'larında aynı uygulanır)

```
! ---- VLAN 10 (SAT) giriş ACL'i — VLAN 20 için 10<->20 yer değiştirerek aynısı ----
ip access-list extended ACL-V10-IN
 permit udp any eq bootpc any eq bootps
 permit tcp 172.16.10.0 0.0.0.255 any established
 permit icmp 172.16.10.0 0.0.0.255 any echo-reply
 deny   ip 172.16.10.0 0.0.0.255 172.16.20.0 0.0.0.255
 deny   ip 172.16.10.0 0.0.0.255 172.16.30.0 0.0.0.255
 deny   ip 172.16.10.0 0.0.0.255 172.16.40.0 0.0.0.255
 deny   ip 172.16.10.0 0.0.0.255 172.16.60.0 0.0.0.255
 deny   ip 172.16.10.0 0.0.0.255 172.16.90.0 0.0.0.255
 deny   ip 172.16.10.0 0.0.0.255 172.20.0.0 0.0.255.255
 permit ip 172.16.10.0 0.0.0.255 any
!
interface Vlan10
 ip access-group ACL-V10-IN in

! ---- VLAN 60 (misafir) giriş ACL'i ----
ip access-list extended ACL-V60-IN
 permit udp any eq bootpc any eq bootps
 permit udp 172.16.60.0 0.0.0.255 host 172.16.50.11 eq 53
 permit tcp 172.16.60.0 0.0.0.255 host 172.16.50.11 eq 53
 deny   ip 172.16.60.0 0.0.0.255 172.16.0.0 0.15.255.255
 permit ip 172.16.60.0 0.0.0.255 any
!
interface Vlan60
 ip access-group ACL-V60-IN in

! ---- VLAN 50 (sunucular) çıkış ACL'i: sunuculara giden trafiği süzer ----
ip access-list extended ACL-SRV-OUT
 permit ip 172.16.30.0 0.0.0.255 172.16.50.0 0.0.0.255
 permit udp any host 172.16.50.10 eq 67
 permit udp any host 172.16.50.11 eq 53
 permit tcp any host 172.16.50.11 eq 53
 permit tcp any host 172.16.50.12 eq 80
 permit tcp any host 172.16.50.12 eq 443
 permit tcp any host 172.16.50.13 eq 25
 permit tcp any host 172.16.50.13 eq 110
 permit tcp any host 172.16.50.13 eq 143
 permit tcp any host 172.16.50.14 eq 21
 permit icmp any 172.16.50.0 0.0.0.255 echo
 deny   ip any any log
!
interface Vlan50
 ip access-group ACL-SRV-OUT out

! ---- VLAN 90 (yönetim) çıkış ACL'i: sadece BIS, YNT ve altyapı erişir ----
ip access-list extended ACL-V90-OUT
 permit ip 172.16.30.0 0.0.0.255 172.16.90.0 0.0.0.255
 permit ip 172.16.40.0 0.0.0.255 172.16.90.0 0.0.0.255
 permit ip 172.20.0.0 0.0.255.255 172.16.90.0 0.0.0.255
 deny   ip any any
!
interface Vlan90
 ip access-group ACL-V90-OUT out
```

**VLAN 20:** `ACL-V20-IN` = V10 ACL'inin kopyası (kaynak `172.16.20.0`, `172.16.10.0` yasak).
**FAB-RTR `Gi0/1` girişi:** `ACL-FAB-IN` aynı mantık (kaynak `172.18.10.0/24`; SAT/PER/BIS/YNT/MSF/YNTM/altyapı yasak; DHCP, DNS, web, mail, FTP, `permit ip ... any` internet için).

**ACL'lerle ilgili iki dürüst not (raporuna yaz):**
1. ACL'ler **stateless**'tir; `established` satırı sahte ACK paketlerini de geçirir. Gerçek ortamda reflexive ACL / ZBF / firewall kullanılırdı. IOSvL2'de ZBF yok; bu yüzden kasıtlı sadeleştirme.
2. Router'ın kendi ürettiği paketler (DHCP relay unicast, HSRP/OSPF hello) çıkış ACL'inden geçmez; bu yüzden DHCP relay `ACL-SRV-OUT`'tan etkilenmez.

### 7.3 NAT/PAT (SNR-RTR)

```
ip access-list standard NAT-INSIDE
 permit 172.16.0.0 0.0.255.255
 permit 172.18.10.0 0.0.0.255
!
interface GigabitEthernet0/0
 ip nat inside
interface GigabitEthernet0/1
 ip nat inside
interface Tunnel0
 ip nat inside
interface GigabitEthernet0/2
 ip nat outside
!
ip nat inside source list NAT-INSIDE interface GigabitEthernet0/2 overload
```

Neden Tunnel0 da `inside`: FAB-LAN'daki kullanıcıların internete çıkışı tünel → SNR → NAT yolundan olur. Merkez ↔ Tesis trafiği Tunnel0'dan çıkar, `Gi0/2`'den çıkmadığı için NAT'a girmez.

---

## 8. Artımlı Yol Haritası — Faz 0 … Faz 6

**Çalışma disiplini (her faz için aynı):**
1. Fazı uygula → 2. "Doğrulama" komutlarını çalıştır → 3. Ekran görüntüsü al → 4. 1 sayfalık checkpoint notu yaz (Bölüm 11.3) → 5. `startup-config`'leri kaydet (`write memory`) → 6. GNS3'te **snapshot** al (sağ tık yok; `File → Snapshots`) → 7. `git commit` + `git tag faz-N`.

**Faz bağımlılık zinciri:** 0 → 1 → 2 → 3 → 4 → 5 → 6. Faz N+1, Faz N tamamlanmadan başlamaz; Faz N+1'in detayları Faz N'de öğrendiklerine göre küçük ayarlanabilir.

---

### FAZ 0 — Ortam ve İskelet

**Amaç:** 40 kablo çekili, 13 IOS cihazı ayakta ve konsoldan erişilebilir, kablolama CDP ile kanıtlı.

#### 0-A. GNS3 ön kontrol

- [ ] GNS3 VM çalışıyor (`192.168.130.128`), sağ panelde yeşil.
- [ ] Her IOSvL2 düğümünde adaptör sayısı 16, her IOSv router'da 4 (zaten öyle).
- [ ] Konsol tipi **telnet** (düğüm Configure → General → Console type).
- [ ] RAM planı (Bölüm 14): 13 IOS düğümü + Docker birlikte çalışacak; GNS3 VM'e yeterli RAM ve CPU ver, nested virtualization / KVM açık olsun.
- [ ] Çizim yerleşimi: ekran görüntüsündeki dizilimi koru (üstte ISS/SNR/FAB, ortada CORE/DAG, altta erişim, en altta uç cihazlar). Cihazlar arası mesafeyi biraz aç ki kablo etiketleri okunsun.

#### 0-B. Kablolama

Bölüm 3.3'teki **L01 … L40** tablosunu sırayla çiz ve işaretle. Her kabloyu çizdikten sonra GNS3'te linkin iki ucundaki noktanın **yeşil** olduğundan emin olmak için düğümleri başlatana kadar bekle (kırmızı = cihaz kapalı).

> **İpucu:** Önce L01–L14 (omurga + WAN), sonra L15–L24 (erişim uplink'leri), en son L25–L40 (uç cihazlar). Bu sırada çiz; hata yaparsan kolay bulursun.

#### 0-C. Başlatma sırası

Tek seferde 30 düğümü başlatma. Önerilen sıra (her adımda 2–3 dakika bekle, `Servers Summary`'de CPU/RAM'e bak):

1. ISS-RTR, SNR-RTR, FAB-RTR
2. MRK-CORE1, MRK-CORE2, MRK-DAG1, MRK-DAG2
3. Beş erişim switch'i + FAB-ERS-1
4. VPCS düğümleri (hafif)
5. Docker sunucuları (kurulduktan sonra)

#### 0-D. Bootstrap konfigürasyonu (13 IOS cihazına, konsoldan, tek seferlik)

Aşağıdaki iskeleti her cihaza `<HOSTNAME>` değiştirerek yapıştır. (Roadmap'in "SSH erişimi — Faz 4'ün ön koşulu" maddesi.) **Parolaları buraya gerçek hâliyle yazma, repoya koyma** (Bölüm 9.5).

```
enable
configure terminal
no ip domain-lookup
hostname <HOSTNAME>
ip domain-name anadolumakina.local
service password-encryption
enable secret <ENABLE_PAROLASI>
username admin privilege 15 secret <KULLANICI_PAROLASI>
!
line con 0
 exec-timeout 0 0
 logging synchronous
line vty 0 4
 login local
 transport input ssh
 exec-timeout 30 0
!
ip ssh version 2
crypto key generate rsa modulus 2048
end
write memory
```

**Sadece router'lara (ISS-RTR, SNR-RTR, FAB-RTR) ek olarak:** (IOSv router arayüzleri varsayılan kapalıdır; CDP için açılmalı)

```
configure terminal
interface range GigabitEthernet0/0 - 3
 no shutdown
end
write memory
```

**Sadece L2 erişim switch'lerine** (5 MRK-ERS-* ve FAB-ERS-1): `no ip routing` zaten varsayılan; **Core/Dağıtım switch'lerinde** (`MRK-CORE1/2`, `MRK-DAG1/2`) `ip routing`'i Faz 2'de açacağız.

**Hostname tablosu:**

| Cihaz | `hostname` |
|---|---|
| 1–4 | `MRK-CORE1`, `MRK-CORE2`, `MRK-DAG1`, `MRK-DAG2` |
| 5–9 | `MRK-ERS-SAT`, `MRK-ERS-PER`, `MRK-ERS-BIS`, `MRK-ERS-YNT`, `MRK-ERS-SRV` |
| 10 | `FAB-ERS-1` |
| 11–13 | `SNR-RTR`, `ISS-RTR`, `FAB-RTR` |

#### 0-E. VPCS cihazlarını isimle doğrula

Her VPCS konsolunda `set pcname <İSİM>` yazıp `save` yap (SAT-PC1 gibi). Faz 1'e kadar IP vermiyoruz.

#### 0-F. Doğrulama — CDP ile kablolama kanıtı

Her IOS cihazında `show cdp neighbors`. CDP ID'leri `HOSTNAME.anadolumakina.local` şeklinde görünebilir; sorun değil. Beklenen komşu sayıları:

| Cihaz | Beklenen CDP girişi |
|---|---|
| MRK-CORE1 | CORE2 ×2 (`Gi0/0`,`Gi0/1`), DAG1 ×2 (`Gi0/2`,`Gi0/3`), SNR-RTR (`Gi1/0`) = **5** |
| MRK-CORE2 | CORE1 ×2, DAG2 ×2, SNR-RTR = **5** |
| MRK-DAG1 | CORE1 ×2, DAG2 ×2, ERS-SAT, ERS-BIS, ERS-SRV, ERS-PER, ERS-YNT = **9** |
| MRK-DAG2 | CORE2 ×2, DAG1 ×2, ERS-PER, ERS-YNT, ERS-SAT, ERS-BIS, ERS-SRV = **9** |
| MRK-ERS-SAT / PER / YNT / BIS / SRV | DAG1 + DAG2 = **2** (VPCS CDP konuşmaz) |
| SNR-RTR | CORE1 (`Gi0/0`), CORE2 (`Gi0/1`), ISS-RTR (`Gi0/2`) = **3** |
| ISS-RTR | SNR-RTR, FAB-RTR = **2** |
| FAB-RTR | ISS-RTR, FAB-ERS-1 = **2** |
| FAB-ERS-1 | FAB-RTR = **1** |

Tek bir CDP girişi bile yanlış porttan görünüyorsa kabloyu Bölüm 3.3'e göre düzelt. **Faz 4'te bu kontrolü Python ile otomatikleştireceğiz** (CDP çıktısı → beklenen komşuluk sözlüğü).

#### 0-G. Ek A (isteğe bağlı) — Gerçek SSH ile yönetim

Varsayılan yöntem konsol telnet'tir (ek düğüm gerekmez). Gerçek in-band SSH istersen:
1. Topolojiye bir **Cloud** düğümü ekle, GNS3 VM'in ikinci ağ kartına bağla (VM'e 2. adaptör eklemen önerilir; yönetim kartını köprülemek sorun çıkarabilir).
2. Cloud'u MRK-ERS-BIS'in boş bir portuna (ör. `Gi1/3`) bağla; o portu `access VLAN 90` yap.
3. Windows tarafında ilgili VMnet adaptörüne ikincil IP ver: `172.16.90.250/24`.
4. Yönetim erişimi için ACL-V90-OUT'a (Bölüm 7.2) `permit ip host 172.16.90.250 172.16.90.0 0.0.0.255` ekle.

> Bu yol ortama (VMware/VirtualBox, VMnet tipi) bağlı olduğu için **denenerek doğrulanmalı**; garanti etmiyorum. Proje için zorunlu değil.

**Faz 0 Çıktısı:** 40 link çekili, 13 cihaza konsoldan erişim, CDP tablosu beklenenle birebir.

---

### FAZ 1 — L2 Omurga

**Amaç:** VLAN'lar, trunk'lar, LACP demetleri ve Rapid-PVST+; departmanlar birbirini L2'de görmez; redundant linkler döngü yapmaz ve **doğru port blocking'e düşer**.

#### 1-A. Hangi switch hangi VLAN'ı biliyor

| Switch | Tanımlanacak VLAN'lar |
|---|---|
| MRK-ERS-SAT | 10, 90 |
| MRK-ERS-PER | 20, 90 |
| MRK-ERS-BIS | 30, 60, 90 |
| MRK-ERS-YNT | 40, 90 |
| MRK-ERS-SRV | 50, 90 |
| MRK-DAG1 / DAG2 | 10, 20, 30, 40, 50, 60, 90, 254 |
| MRK-CORE1 / CORE2 | (VLAN yok — sadece routed linkler) |
| FAB-ERS-1 | 110 |

VLAN adları: `10 SAT`, `20 PER`, `30 BIS`, `40 YNT`, `50 SRV`, `60 MSF`, `90 YNTM`, `110 FAB-LAN`, `254 DAG-ARA`.

#### 1-B. Erişim switch'i konfigürasyonu (ERS-SAT örneği — diğerleri tablodan)

```
configure terminal
vtp mode transparent
spanning-tree mode rapid-pvst
!
vlan 10
 name SAT
vlan 90
 name YNTM
!
interface range GigabitEthernet0/0 - 1
 description UPLINK-DAG
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 10,90
 no shutdown
!
interface range GigabitEthernet0/2 - 3
 description UC-CIHAZ
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast
 spanning-tree bpduguard enable
 no shutdown
end
write memory
```
> `switchport trunk encapsulation dot1q` komutunu IOSvL2 kabul etmezse (zaten dot1q) atla.

**Her erişim switch'i için değişkenler:**

| Switch | Trunk izinli VLAN (Gi0/0–0/1) | Access portlar | Yönetim IP (Faz 2) |
|---|---|---|---|
| ERS-SAT | 10,90 | `Gi0/2–0/3` → VLAN 10 | 172.16.90.11 |
| ERS-PER | 20,90 | `Gi0/2–0/3` → VLAN 20 | 172.16.90.12 |
| ERS-BIS | 30,60,90 | `Gi0/2–0/3` ve `Gi1/0` → VLAN 30; `Gi1/1` (KAP-1) → VLAN 90; `Gi1/2` (MSF-DZ1) → VLAN 60 | 172.16.90.13 |
| ERS-YNT | 40,90 | `Gi0/2–0/3` → VLAN 40 | 172.16.90.14 |
| ERS-SRV | 50,90 | `Gi0/2–0/3`, `Gi1/0–1/2` → VLAN 50 | 172.16.90.15 |

#### 1-C. Dağıtım switch'i L2 konfigürasyonu (DAG1 örneği)

```
configure terminal
vtp mode transparent
spanning-tree mode rapid-pvst
!
vlan 10
 name SAT
vlan 20
 name PER
vlan 30
 name BIS
vlan 40
 name YNT
vlan 50
 name SRV
vlan 60
 name MSF
vlan 90
 name YNTM
vlan 254
 name DAG-ARA
!
spanning-tree vlan 10,30,50,90,254 priority 4096
spanning-tree vlan 20,40,60 priority 8192
!
! --- DAG1 <-> DAG2 : L2 trunk LACP demeti (Po2) ---
interface Port-channel2
 description PO2-TO-DAG2-L2TRUNK
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 10,20,30,40,50,60,90,254
interface range GigabitEthernet0/2 - 3
 description TO-DAG2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 10,20,30,40,50,60,90,254
 channel-group 2 mode active
 no shutdown
!
! --- Erişim uplink'leri ---
interface GigabitEthernet1/0
 description TO-ERS-SAT-Gi0/0 (P)
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 10,90
 no shutdown
interface GigabitEthernet1/1
 description TO-ERS-BIS-Gi0/0 (P)
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 30,60,90
 no shutdown
interface GigabitEthernet1/2
 description TO-ERS-SRV-Gi0/0 (P)
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 50,90
 no shutdown
interface GigabitEthernet1/3
 description TO-ERS-PER-Gi0/1 (Y)
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 20,90
 no shutdown
interface GigabitEthernet2/0
 description TO-ERS-YNT-Gi0/1 (Y)
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan 40,90
 no shutdown
end
write memory
```

**DAG2'de farklı olanlar:**
- STP öncelikleri **tersine:** `vlan 20,40,60,… priority 4096` ve `vlan 10,30,50,90,254 priority 8192` (Bölüm 5.5).
- Erişim uplink portları:

| DAG2 portu | Erişim switch | İzinli VLAN | Rol |
|---|---|---|---|
| `Gi1/0` | ERS-PER `Gi0/0` | 20,90 | P |
| `Gi1/1` | ERS-YNT `Gi0/0` | 40,90 | P |
| `Gi1/2` | ERS-SAT `Gi0/1` | 10,90 | Y |
| `Gi1/3` | ERS-BIS `Gi0/1` | 30,60,90 | Y |
| `Gi2/0` | ERS-SRV `Gi0/1` | 50,90 | Y |

#### 1-D. Core/Dağıtım routed port-channel'lar (IP'siz, sadece demet)

**MRK-CORE1** (CORE2'de aynı, sadece DAG2 yönü):

```
configure terminal
interface Port-channel1
 description PO1-TO-CORE2
 no switchport
 no ip address
interface range GigabitEthernet0/0 - 1
 no switchport
 no ip address
 channel-group 1 mode active
 no shutdown
!
interface Port-channel2
 description PO2-TO-DAG1
 no switchport
 no ip address
interface range GigabitEthernet0/2 - 3
 no switchport
 no ip address
 channel-group 2 mode active
 no shutdown
end
write memory
```

**MRK-DAG1** (DAG2'de CORE2 yönü):

```
configure terminal
interface Port-channel1
 description PO1-TO-CORE1
 no switchport
 no ip address
interface range GigabitEthernet0/0 - 1
 no switchport
 no ip address
 channel-group 1 mode active
 no shutdown
end
write memory
```

> **Sıra önemlidir:** önce `interface Port-channelX` + `no switchport`, sonra üye portlarda `no switchport` + `channel-group`. Aksi hâlde "port-channel mode mismatch" hatası alırsın. Demet 30–60 sn içinde `P` olur.
> **Yedek plan:** IOSvL2 sürümün routed port-channel'ı kabul etmezse Core/DAG arası demetleri L2 trunk yap, her demet için ayrı bir transit VLAN + SVI kullan (ör. VLAN 201–203, `172.20.254.x/30`); OSPF mantığı aynı kalır.

#### 1-E. Doğrulama

**Her switch:** `show vlan brief`, `show interfaces trunk`, `show etherchannel summary`, `show spanning-tree vlan <N>`.

| Kontrol | Beklenen |
|---|---|
| `show etherchannel summary` (CORE1) | `Po1(RU)` ve `Po2(RU)`, üyeler `Gi0/0(P) Gi0/1(P)` / `Gi0/2(P) Gi0/3(P)` |
| `show etherchannel summary` (DAG1) | `Po1(RU)` (routed), `Po2(SU)` (L2) |
| `show spanning-tree vlan 10` (DAG1) | "This bridge is the root" |
| `show spanning-tree vlan 20` (DAG2) | "This bridge is the root" |
| `show spanning-tree vlan 10` (ERS-SAT) | `Gi0/0` **Root FWD**, `Gi0/1` **Altn BLK** |
| `show spanning-tree vlan 20` (ERS-PER) | `Gi0/0` **Root FWD** (→DAG2), `Gi0/1` **Altn BLK** |
| `show spanning-tree vlan 30` (ERS-BIS) | `Gi0/0` Root FWD, `Gi0/1` Altn BLK |
| `show spanning-tree vlan 60` (ERS-BIS) | `Gi0/1` Root FWD (→DAG2), `Gi0/0` Altn BLK |
| `show spanning-tree vlan 90` (ERS-PER) | `Gi0/1` Root FWD (→DAG1, VLAN 90 kökü DAG1), `Gi0/0` Altn BLK |

**VPCS ile VLAN izolasyonu testi** (statik IP, Bölüm 5.6):

```
SAT-PC1> ip 172.16.10.11/24 172.16.10.1
SAT-PC2> ip 172.16.10.12/24 172.16.10.1
PER-PC1> ip 172.16.20.11/24 172.16.20.1

SAT-PC1> ping 172.16.10.12      <- başarılı (aynı VLAN)
SAT-PC1> ping 172.16.20.11      <- BAŞARISIZ (farklı VLAN, henüz L3 yok) = izolasyon kanıtı
```

**Faz 1 Çıktısı:** `show etherchannel summary`, `show spanning-tree`, `show vlan brief` ekran görüntüleri; "departmanlar L2'de izole, linkler döngü yapmıyor" kanıtı.

---

### FAZ 2 — L3 Routing ve Yüksek Erişilebilirlik

**Amaç:** OSPF (Area 0/100), HSRP, tüm ağ pingable, Core/DAG failover çalışır.

#### 2-A. Core switch'leri (CORE1 örneği)

```
configure terminal
ip routing
!
interface Loopback0
 ip address 172.20.20.1 255.255.255.255
 ip ospf 1 area 0
!
interface Port-channel1
 ip address 172.20.254.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
interface Port-channel2
 ip address 172.20.254.5 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
interface GigabitEthernet1/0
 description TO-SNR-RTR-Gi0/0
 no switchport
 ip address 172.20.254.17 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
!
router ospf 1
 router-id 172.20.20.1
 auto-cost reference-bandwidth 10000
 passive-interface default
 no passive-interface Port-channel1
 no passive-interface Port-channel2
 no passive-interface GigabitEthernet1/0
end
write memory
```

**Değişkenler (Core/DAG):**

| | CORE1 | CORE2 | DAG1 | DAG2 |
|---|---|---|---|---|
| Router-ID / Lo0 | 172.20.20.1 | 172.20.20.2 | 172.20.20.3 | 172.20.20.4 |
| Po1 IP | 172.20.254.1/30 | 172.20.254.2/30 | 172.20.254.6/30 | 172.20.254.10/30 |
| Po2 IP | 172.20.254.5/30 | 172.20.254.9/30 | (L2 trunk, IP yok) | (L2 trunk, IP yok) |
| `Vlan254` IP | — | — | 172.20.254.13/30 | 172.20.254.14/30 |
| `Gi1/0` (SNR yönü) | 172.20.254.17/30 | 172.20.254.21/30 | — | — |

#### 2-B. Dağıtım switch'leri — L3 + HSRP (DAG1)

```
configure terminal
ip routing
!
interface Loopback0
 ip address 172.20.20.3 255.255.255.255
 ip ospf 1 area 0
!
interface Port-channel1
 ip address 172.20.254.6 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
!
interface Vlan254
 description DAG1-DAG2-TRANSIT
 ip address 172.20.254.13 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
!
interface Vlan10
 description SAT
 ip address 172.16.10.2 255.255.255.0
 standby 10 ip 172.16.10.1
 standby 10 priority 110
 standby 10 preempt
 ip ospf 1 area 100
 no shutdown
! ... VLAN 20, 30, 40, 50, 60, 90 aynı kalıpla (aşağıdaki tablo)
!
router ospf 1
 router-id 172.20.20.3
 auto-cost reference-bandwidth 10000
 passive-interface default
 no passive-interface Port-channel1
 no passive-interface Vlan254
end
write memory
```

**SVI değişkenleri:**

| SVI | DAG1 IP | DAG2 IP | VIP | DAG1 pri | DAG2 pri |
|---|---|---|---|---|---|
| Vlan10 | 172.16.10.2 | 172.16.10.3 | 172.16.10.1 | **110** | 90 |
| Vlan20 | 172.16.20.2 | 172.16.20.3 | 172.16.20.1 | 90 | **110** |
| Vlan30 | 172.16.30.2 | 172.16.30.3 | 172.16.30.1 | **110** | 90 |
| Vlan40 | 172.16.40.2 | 172.16.40.3 | 172.16.40.1 | 90 | **110** |
| Vlan50 | 172.16.50.2 | 172.16.50.3 | 172.16.50.1 | **110** | 90 |
| Vlan60 | 172.16.60.2 | 172.16.60.3 | 172.16.60.1 | 90 | **110** |
| Vlan90 | 172.16.90.2 | 172.16.90.3 | 172.16.90.1 | **110** | 90 |

Her SVI'da `standby N ip <VIP>`, `standby N priority <pri>`, `standby N preempt`, `ip ospf 1 area 100`.

> **İsteğe bağlı dönüş yolu ayarı:** Standby taraftaki SVI'lara `ip ospf cost 10` verirsen Core, VLAN'ın dönüş trafiğini HSRP active DAG'a yönlendirir (varsayılanda iki DAG eşit maliyette, ECMP olur; fonksiyonel olarak sorun yok, sadece simetrik yol istersen).

#### 2-C. Erişim switch'lerinde yönetim arayüzü

```
configure terminal
interface Vlan90
 ip address 172.16.90.11 255.255.255.0
 no shutdown
ip default-gateway 172.16.90.1
end
write memory
```
(`.11–.15` tabloya göre; FAB-ERS-1 için Faz 3-B'de `Vlan110`.)

#### 2-D. SNR-RTR — Core'a bağlanan kısım

```
configure terminal
interface Loopback0
 ip address 172.20.20.5 255.255.255.255
 ip ospf 1 area 0
interface GigabitEthernet0/0
 description TO-MRK-CORE1-Gi1/0
 ip address 172.20.254.18 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
interface GigabitEthernet0/1
 description TO-MRK-CORE2-Gi1/0
 ip address 172.20.254.22 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
!
router ospf 1
 router-id 172.20.20.5
 auto-cost reference-bandwidth 10000
 passive-interface default
 no passive-interface GigabitEthernet0/0
 no passive-interface GigabitEthernet0/1
end
write memory
```
(**Area 200 yok** — D2 düzeltmesi.)

#### 2-E. Doğrulama

| Komut | Beklenen |
|---|---|
| `show ip ospf neighbor` (CORE1) | 3 komşu `FULL/-` (CORE2, DAG1, SNR) |
| `show ip ospf neighbor` (DAG1) | 2 komşu `FULL/-` (CORE1, DAG2) |
| `show ip ospf` (DAG1) | "It is an area border router" |
| `show ip route ospf` (CORE1) | 172.16.x.0/24 rotaları `O IA` olarak, DAG'lerden |
| `show standby brief` (DAG1) | Vlan10/30/50/90 **Active**, Vlan20/40/60 **Standby** |
| `show standby brief` (DAG2) | Vlan20/40/60 **Active**, Vlan10/30/50/90 **Standby** |
| `show ip interface brief` (DAG1) | tüm SVI'lar `up/up` |

**VPCS ile uçtan uca test** (DHCP henüz yok → statik):

```
SAT-PC1> ip 172.16.10.11/24 172.16.10.1
PER-PC1> ip 172.16.20.11/24 172.16.20.1
SAT-PC1> ping 172.16.20.11     <- ARTIK başarılı (VLAN'lar arası, DAG üzerinden)
SAT-PC1> trace 172.16.20.11    <- 172.16.10.1 (VIP) → ... → 172.16.20.x
```

**Canlı demo (hoca için):** `ping -t` benzeri sürekli ping (`ping 172.16.20.11 -t`) çalışırken MRK-CORE1'i durdur → ping 1–2 paket kaybıyla devam eder; DAG1'i durdur → HSRP geçişi + STP. Ayrıntılı senaryolar Bölüm 12'de.

**Faz 2 Çıktısı:** `show ip ospf neighbor`, `show standby brief` ekran görüntüleri; çalışan failover demosunun kısa kaydı/ekran görüntüsü.

---

### FAZ 3 — Kenar, WAN ve Servisler

**Amaç:** Simüle internet, GRE tüneli, Area 300, NAT/PAT, DHCP relay ve ACL politikası.

#### 3-A. Simüle internet ve WAN underlay

**ISS-RTR:**
```
configure terminal
interface GigabitEthernet0/0
 description TO-SNR-RTR-Gi0/2
 ip address 198.51.100.2 255.255.255.252
 no shutdown
interface GigabitEthernet0/1
 description TO-FAB-RTR-Gi0/0
 ip address 198.51.100.5 255.255.255.252
 no shutdown
interface Loopback0
 description SIMULE-INTERNET-HEDEFI
 ip address 203.0.113.1 255.255.255.255
end
write memory
```
**SNR-RTR:**
```
configure terminal
interface GigabitEthernet0/2
 description TO-ISS-RTR-Gi0/0
 ip address 198.51.100.1 255.255.255.252
 no shutdown
ip route 0.0.0.0 0.0.0.0 198.51.100.2
end
write memory
```
**FAB-RTR:**
```
configure terminal
interface GigabitEthernet0/0
 description TO-ISS-RTR-Gi0/1
 ip address 198.51.100.6 255.255.255.252
 no shutdown
ip route 198.51.100.0 255.255.255.252 198.51.100.5
end
write memory
```
**Doğrulama:** `ping 198.51.100.2` (SNR'dan), `ping 198.51.100.6` (SNR'dan ISS üzerinden; **başarılı olmalı**: ISS iki alt ağı da bağlı görüyor ve SNR default'u ISS'e).

#### 3-B. GRE tüneli, Area 300 ve Tesis LAN'ı

**SNR-RTR:**
```
configure terminal
interface Tunnel0
 description GRE-TO-FAB-RTR
 ip address 172.20.200.1 255.255.255.252
 tunnel source GigabitEthernet0/2
 tunnel destination 198.51.100.6
 ip mtu 1400
 ip tcp adjust-mss 1360
 ip ospf network point-to-point
 ip ospf 1 area 300
!
router ospf 1
 no passive-interface Tunnel0
 area 300 stub no-summary
 default-information originate
end
write memory
```
**FAB-RTR:**
```
configure terminal
interface Loopback0
 ip address 172.20.20.6 255.255.255.255
 ip ospf 1 area 300
!
interface GigabitEthernet0/1
 description FAB-LAN-VLAN110
 ip address 172.18.10.1 255.255.255.0
 ip ospf 1 area 300
 no shutdown
!
interface Tunnel0
 description GRE-TO-SNR-RTR
 ip address 172.20.200.2 255.255.255.252
 tunnel source GigabitEthernet0/0
 tunnel destination 198.51.100.1
 ip mtu 1400
 ip tcp adjust-mss 1360
 ip ospf network point-to-point
 ip ospf 1 area 300
!
router ospf 1
 router-id 172.20.20.6
 auto-cost reference-bandwidth 10000
 area 300 stub
 passive-interface default
 no passive-interface Tunnel0
end
write memory
```
**FAB-ERS-1:**
```
configure terminal
vtp mode transparent
spanning-tree mode rapid-pvst
vlan 110
 name FAB-LAN
interface range GigabitEthernet0/0 - 1
 switchport mode access
 switchport access vlan 110
 spanning-tree portfast
 no shutdown
interface Vlan110
 ip address 172.18.10.2 255.255.255.0
 no shutdown
ip default-gateway 172.18.10.1
end
write memory
```

**Doğrulama:**

| Komut | Beklenen |
|---|---|
| `show interfaces tunnel0` (SNR) | `line protocol is up` |
| `show ip ospf neighbor` (SNR) | 3 komşu: CORE1, CORE2, FAB-RTR (`Tunnel0`) |
| `show ip route ospf` (FAB-RTR) | `O*IA 0.0.0.0/0` (ABR'den gelen default) |
| `show ip route 172.18.10.0` (CORE1) | `O IA`, çıkış SNR yönü |
| `FAB-PC1> ip 172.18.10.11/24 172.18.10.1` sonra `ping 172.16.10.1` | başarılı (tünel + OSPF) |
| `SAT-PC1> ping 172.18.10.11` | başarılı (SNR → Tunnel0 → FAB) |

> **Tünel çalışmazsa:** `ping 198.51.100.6 source GigabitEthernet0/2` ile underlay'i kontrol et; `show ip route 198.51.100.0` FAB'da **Tunnel0 değil `Gi0/0`** göstermeli (rekürsif yönlendirme sorunu).

#### 3-C. NAT/PAT (SNR-RTR)

Bölüm 7.3'teki konfigürasyonu uygula. **Doğrulama:**
```
SAT-PC1> ping 203.0.113.1              <- başarılı
SNR-RTR# show ip nat translations      <- 172.16.10.11 → 198.51.100.1 (ICMP)
SNR-RTR# show ip nat statistics
SAT-PC1> ping 172.18.10.11             <- NAT'a GİRMEMELİ (translations tablosunda yok)
```

#### 3-D. DHCP relay konfigürasyonu

**MRK-DAG1 ve DAG2 — SVI 10, 20, 30, 40, 60 üzerinde** (SVI 50 ve 90'da yok):
```
interface Vlan10
 ip helper-address 172.16.50.10
interface Vlan20
 ip helper-address 172.16.50.10
interface Vlan30
 ip helper-address 172.16.50.10
interface Vlan40
 ip helper-address 172.16.50.10
interface Vlan60
 ip helper-address 172.16.50.10
```
**FAB-RTR:**
```
interface GigabitEthernet0/1
 ip helper-address 172.16.50.10
```

#### 3-E. Sunucular: VPCS'ten Docker'a geçiş (önce SNC-DHCP)

**Neden gerekli:** VPCS'te DHCP/DNS/Web servisi çalıştırılamaz; roadmap'in "DHCP relay demosu" gerçek bir DHCP sunucusu ister. **Öncelik:** SNC-DHCP (zorunlu) → SNC-DNS, SNC-WEB → SNC-POSTA, SNC-DOSYA (isteğe bağlı).

**Geçiş planı (artımlı):**
1. SNC-DHCP'yi Docker ile değiştir; diğer 4 sunucu şimdilik VPCS statik IP (`ip 172.16.50.11/24 172.16.50.1` vb.) — ping testi için yeterli.
2. Kaynak yetiyorsa SNC-DNS ve SNC-WEB'i Docker yap; en sona POSTA/DOSYA.
3. **Kaynak yetmiyorsa:** 5 container yerine 2–3 çok-servisli container (mimari bozulmaz).
4. **En kötü durum (yedek plan):** DHCP'yi DAG'larda `ip dhcp pool` ile ver (relay demosu kaybolur, projenin geri kalanı çalışır).

**Tek "snc-base" imajı yaklaşımı (önerilen):** GNS3 VM'de bir kez derle, 5 düğümde aynı imajı kullan, hangi servisi çalıştıracağını konsoldan belirle.

```dockerfile
# GNS3 VM üzerinde: docker build -t snc-base .
FROM debian:12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ifupdown iproute2 iputils-ping net-tools procps dnsutils curl tcpdump \
      isc-dhcp-server bind9 nginx vsftpd postfix dovecot-imapd \
 && rm -rf /var/lib/apt/lists/*
CMD ["/bin/bash"]
```
> GNS3 Docker düğümü ağ ayarını `/etc/network/interfaces` üzerinden uygular; bu yüzden imajda `ifupdown` var. GNS3 sürümüne göre ayrıntılar değişebilir; imaj adlarını ve paketleri kendi VM'inde doğrula.

**GNS3'te:** `Edit → Preferences → Docker containers → New` → imaj `snc-base`, adaptör sayısı 1, konsol tipi telnet. Düğümü topolojiye ekleyip `SNC-DHCP` olarak adlandır, VPCS'i sil, `ERS-SRV Gi0/2`'ye (L36) bağla. Düğüm özelliklerinde **"Edit network configuration"**:

```
auto eth0
iface eth0 inet static
    address 172.16.50.10
    netmask 255.255.255.0
    gateway 172.16.50.1
```
Kalıcılık için düğüm ayarında "additional persistent directories" alanına `/etc/dhcp` ekle.

**SNC-DHCP'de `/etc/dhcp/dhcpd.conf`:**
```
default-lease-time 3600;
max-lease-time 7200;
authoritative;
option domain-name "anadolumakina.local";
option domain-name-servers 172.16.50.11;

subnet 172.16.50.0 netmask 255.255.255.0 { }

subnet 172.16.10.0 netmask 255.255.255.0 {
  range 172.16.10.100 172.16.10.200;
  option routers 172.16.10.1;
}
subnet 172.16.20.0 netmask 255.255.255.0 {
  range 172.16.20.100 172.16.20.200;
  option routers 172.16.20.1;
}
subnet 172.16.30.0 netmask 255.255.255.0 {
  range 172.16.30.100 172.16.30.200;
  option routers 172.16.30.1;
}
subnet 172.16.40.0 netmask 255.255.255.0 {
  range 172.16.40.100 172.16.40.200;
  option routers 172.16.40.1;
}
subnet 172.16.60.0 netmask 255.255.255.0 {
  range 172.16.60.100 172.16.60.200;
  option routers 172.16.60.1;
}
subnet 172.18.10.0 netmask 255.255.255.0 {
  range 172.18.10.100 172.18.10.200;
  option routers 172.18.10.1;
}
```
Başlatma (konsoldan): `touch /var/lib/dhcp/dhcpd.leases && dhcpd -4 -cf /etc/dhcp/dhcpd.conf eth0`; kontrol: `ps aux | grep dhcpd`.

**Diğer servisler (özet, Docker'a geçtikçe):**

| Sunucu | Servis | Hızlı test |
|---|---|---|
| SNC-DNS `.11` | bind9, `anadolumakina.local` zone'u (A kayıtları: dhcp, dns, web, posta, dosya) | `dig @172.16.50.11 web.anadolumakina.local` |
| SNC-WEB `.12` | nginx (sabit bir `index.html`) | `curl http://172.16.50.12` |
| SNC-POSTA `.13` | postfix (SMTP 25) + dovecot (IMAP 143) | `nc -vz 172.16.50.13 25` |
| SNC-DOSYA `.14` | vsftpd (FTP 21) | `nc -vz 172.16.50.14 21` |

**VPCS istemcilerini DHCP'ye geçir:**
```
SAT-PC1> ip dhcp
DORA IP 172.16.10.100/24 GW 172.16.10.1
FAB-PC1> ip dhcp
DORA IP 172.18.10.100/24 GW 172.18.10.1     <- GRE tüneli üstünden relay kanıtı
```

> **DHCP relay + erişim switch'inde snooping uyarısı (Güvenlik modülü eklenince):** DHCP Snooping açarsan Option 82 ekleme sorun çıkarır; erişim switch'lerinde `no ip dhcp snooping information option` ver (en basit çözüm) ya da DAG SVI'larında `ip dhcp relay information trusted` kullan.

#### 3-F. ACL politikasını uygula

Bölüm 7.2'deki ACL'leri DAG1 **ve** DAG2'ye, `ACL-FAB-IN`'i FAB-RTR'a uygula. **Bundan sonra** Bölüm 12.3'teki ACL test tablosunu çalıştır (BIS-PC1 her yere erişir, SAT-PC1 PER'e erişemez, MSF-DZ1 sadece internet ve DNS).

**Faz 3 Çıktısı:** NAT tablosu, tünel `up`, `show ip route` (FAB'da default), DHCP'den adres alan PC'ler ve ACL test sonuçları.

---

### FAZ 4 — Python Otomasyon Çekirdeği

**Amaç:** `python deploy.py --phase N` ile cihazlara toplu, tekrarlanabilir config basmak. Bölüm 9'da kod iskeletleri var; burada iş akışı.

1. Bölüm 9.1–9.3'teki klasör, `devices.yaml` ve Jinja2 şablonlarını hazırla. Şablonlar, Faz 1–3'te elle yaptığın konfigürasyonların **değişkenleştirilmiş hâlidir** (hostname, IP, VLAN listesi dışarıdan gelir).
2. **Önce tek cihazda dene:** `python deploy.py --phase 1 --only MRK-ERS-SAT --dry-run` (sadece üretir), sonra `--dry-run` olmadan.
3. **İdempotentlik testi:** aynı komutu **ikinci kez** çalıştır — hata vermemeli, `show run` değişmemeli. (IOS komutlarının büyük çoğunluğu zaten idempotenttir; riskli olanlar `crypto key generate`, `channel-group` sırası → bunlar yalnız bootstrap şablonundadır.)
4. **"Sıfır cihaz → saniyeler içinde config" demosu:** 13 IOS cihazında `write erase` + `reload` yap (VLAN dosyaları için `delete vlan.dat`), sonra bootstrap'tan sonra `python deploy.py --phase 1`, `--phase 2`, `--phase 3` çalıştır. Süreyi ölç; raporda "elle X dakika, otomasyonla Y saniye" karşılaştırması güçlü bir sonuçtur.

> **Netmiko ve Paramiko notu:** Netmiko zaten Paramiko'yu alt katmanda kullanır; raporunda Netmiko'yu ana kütüphane, Paramiko'yu sadece SCP/dosya transferi gibi düşük seviye ihtiyaçlar için ek konumlandır.

**Faz 4 Çıktısı:** 13 IOS cihazı tek komutla yapılandırılıyor; ikinci çalıştırmada hata yok.

---

### FAZ 5 — Doğrulama ve "Ağ Sağlık Raporu"

**Amaç:** Ağın anlık sağlığını tek komutla rapor etmek (`python validate.py`).

Rapor şunları kontrol eder (hepsi bu dosyada tanımlı "beklenen durum"la karşılaştırılır):

| Kontrol | Komut | Beklenen |
|---|---|---|
| Cihaz ulaşılabilir mi | bağlantı denemesi | 13/13 |
| Kablolama (CDP) | `show cdp neighbors` | Faz 0-F tablosu |
| EtherChannel | `show etherchannel summary` | CORE: Po1/Po2 `RU`; DAG: Po1 `RU`, Po2 `SU` |
| OSPF komşuluk | `show ip ospf neighbor` | CORE1/2: 3, DAG1/2: 2, SNR: 3, FAB-RTR: 1 → toplam 14 |
| HSRP | `show standby brief` | DAG1 active: 10/30/50/90; DAG2 active: 20/40/60 |
| Tünel | `show interfaces tunnel0` | `up/up` |
| Çıktı | JSON + konsol tablosu | `reports/health_YYYYMMDD_HHMMSS.json` |

Kod iskeleti: Bölüm 9.4. Bu parça projenin "mühendislik" tarafını en güçlü gösteren kısımdır; hoca sunumunda öne çıkar.

**Faz 5 Çıktısı:** Tek komutla yeşil/kırmızı sağlık raporu; bir linki bilerek kapatınca raporun kırmızıya döndüğünü gösteren ekran görüntüsü.

---

### FAZ 6 — Yedekleme ve Wireshark Analizi

**Amaç:** Config geçmişi ve paket analizi.

**6-A. Yedekleme:** `python backup.py` her cihazın `show running-config` çıktısını `backups/YYYY-MM-DD_HHMM/<hostname>.cfg` olarak kaydeder. Zamanlama için cron (Linux) / Görev Zamanlayıcı (Windows) veya Python `schedule` kütüphanesi (Bölüm 9.5).

**6-B. Wireshark analizi** (GNS3'te link üzerinde sağ tık → **Start capture**; Wireshark kurulu olmalı):

| Ne yakalanır | Hangi linkte | Görüntüleme filtresi | Raporda ne anlatılır |
|---|---|---|---|
| OSPF Hello/DBD/LSU | L09 (CORE1 `Gi1/0` – SNR `Gi0/0`) | `ospf` | Hello/dead aralığı, komşuluk durum geçişleri (Init → 2-Way → ExStart → Full) |
| HSRP hello | L15 (DAG1 `Gi1/0` – ERS-SAT `Gi0/0`) | `udp.port == 1985` | Active/Standby hello'ları, priority, VIP, failover anı |
| LACP PDU | L01 (CORE1 `Gi0/0` – CORE2 `Gi0/0`) | `slow` (LACP) | Actor/Partner bilgisi, `active` mod |
| GRE (dış paket) | L11 (SNR `Gi0/2` – ISS `Gi0/0`) | `gre` | Dış IP 198.51.100.1→.6, içindeki iç paket (OSPF/ICMP) |
| DHCP DORA (relay) | L36 (ERS-SRV `Gi0/2` – SNC-DHCP) | `bootp` | `giaddr` alanı, relay'in unicast iletmesi |
| STP BPDU | L15–L16 | `stp` | Kök bridge ID, port rolleri |
| Konsol telnet trafiği (Netmiko) | GNS3 VM'e yakalama | `tcp.port >= 5000` (VM tarafında) | Otomasyon sırasında gönderilen komutlar |

Kısa analiz raporu: her satır için 1 ekran görüntüsü + 2–3 cümle.

**Faz 6 Çıktısı:** Dolu `backups/` klasörü + birkaç sayfalık paket analizi. **Bu noktada proje çekirdek olarak tamamdır** (7 faz bitti); Bölüm 10'daki modüller yalnızca "zaman kalırsa".

---

## 9. Python Otomasyon Projesi (kod iskeletleri)

### 9.1 Kurulum ve envanter

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install netmiko pyyaml jinja2 schedule requests
```

**`core/inventory/devices.yaml`** — 13 IOS cihazı (konsol portlarını GNS3 Topology Summary'den doldur):

```yaml
defaults:
  device_type: cisco_ios_telnet     # GNS3 konsolu (telnet); SSH için: cisco_ios
  console_host: 192.168.130.128     # GNS3 VM
  domain: anadolumakina.local

devices:
  # ---------- Core / Dağıtım (L3 switch) ----------
  - {name: MRK-CORE1, role: core, console_port: null, router_id: 172.20.20.1}
  - {name: MRK-CORE2, role: core, console_port: null, router_id: 172.20.20.2}
  - {name: MRK-DAG1,  role: dag,  console_port: null, router_id: 172.20.20.3, stp_root_vlans: "10,30,50,90,254", stp_sec_vlans: "20,40,60"}
  - {name: MRK-DAG2,  role: dag,  console_port: null, router_id: 172.20.20.4, stp_root_vlans: "20,40,60",       stp_sec_vlans: "10,30,50,90,254"}

  # ---------- Erişim (L2 switch) ----------
  - name: MRK-ERS-SAT
    role: access
    console_port: 5008
    mgmt_ip: 172.16.90.11
    vlans: [{id: 10, name: SAT}, {id: 90, name: YNTM}]
    trunk_allowed: "10,90"
    access_ports: [{range: "GigabitEthernet0/2 - 3", vlan: 10}]
  - name: MRK-ERS-PER
    role: access
    console_port: 5010
    mgmt_ip: 172.16.90.12
    vlans: [{id: 20, name: PER}, {id: 90, name: YNTM}]
    trunk_allowed: "20,90"
    access_ports: [{range: "GigabitEthernet0/2 - 3", vlan: 20}]
  - name: MRK-ERS-BIS
    role: access
    console_port: null
    mgmt_ip: 172.16.90.13
    vlans: [{id: 30, name: BIS}, {id: 60, name: MSF}, {id: 90, name: YNTM}]
    trunk_allowed: "30,60,90"
    access_ports:
      - {range: "GigabitEthernet0/2 - 3", vlan: 30}
      - {range: "GigabitEthernet1/0",     vlan: 30}
      - {range: "GigabitEthernet1/1",     vlan: 90}   # KAP-1
      - {range: "GigabitEthernet1/2",     vlan: 60}   # MSF-DZ1
  - name: MRK-ERS-YNT
    role: access
    console_port: 5012
    mgmt_ip: 172.16.90.14
    vlans: [{id: 40, name: YNT}, {id: 90, name: YNTM}]
    trunk_allowed: "40,90"
    access_ports: [{range: "GigabitEthernet0/2 - 3", vlan: 40}]
  - name: MRK-ERS-SRV
    role: access
    console_port: 5014
    mgmt_ip: 172.16.90.15
    vlans: [{id: 50, name: SRV}, {id: 90, name: YNTM}]
    trunk_allowed: "50,90"
    access_ports:
      - {range: "GigabitEthernet0/2 - 3", vlan: 50}
      - {range: "GigabitEthernet1/0 - 2", vlan: 50}

  # ---------- Şube ----------
  - {name: FAB-ERS-1, role: branch_sw, console_port: null, mgmt_ip: 172.18.10.2}

  # ---------- Router'lar ----------
  - {name: SNR-RTR, role: snr, console_port: 5020, router_id: 172.20.20.5}
  - {name: ISS-RTR, role: iss, console_port: null}
  - {name: FAB-RTR, role: fab, console_port: null, router_id: 172.20.20.6}
```

**İsteğe bağlı: envanteri GNS3 REST API'sinden üret** (konsol portları değişirse elle düzeltmek yerine):

```python
# core/scripts/gen_inventory.py — GNS3 API sürümüne göre /v2 veya /v3 olabilir, kimlik doğrulama gerekebilir
import requests
VM = "http://192.168.130.128:3080"
proj = next(p for p in requests.get(f"{VM}/v2/projects").json() if p["name"] == "DesignProject")
for n in requests.get(f"{VM}/v2/projects/{proj['project_id']}/nodes").json():
    print(n["name"], n.get("console"))
```

### 9.2 Jinja2 şablon örneği — `core/configs/templates/access_faz1.j2`

```jinja
vtp mode transparent
spanning-tree mode rapid-pvst
{% for v in vlans %}
vlan {{ v.id }}
 name {{ v.name }}
{% endfor %}
interface range GigabitEthernet0/0 - 1
 description UPLINK-DAG
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 90
 switchport trunk allowed vlan {{ trunk_allowed }}
 no shutdown
{% for p in access_ports %}
interface range {{ p.range }}
 switchport mode access
 switchport access vlan {{ p.vlan }}
 spanning-tree portfast
 spanning-tree bpduguard enable
 no shutdown
{% endfor %}
```
Şablon isimlendirme kuralı: **`<role>_faz<N>.j2`**. Faz 1–3'teki diğer konfigürasyonlar (dag, core, snr, fab, iss, branch_sw) aynı mantıkla bu dosyanın Bölüm 8'deki bloklarından türetilir; `configure terminal`, `end`, `write memory` satırları şablonda **yok** (Netmiko ekler).

### 9.3 `core/scripts/deploy.py`

```python
#!/usr/bin/env python3
"""Şablondan config üretip Netmiko ile basar.
   python deploy.py --phase 1
   python deploy.py --phase 1 --only MRK-ERS-SAT MRK-DAG1
   python deploy.py --phase 1 --dry-run
"""
import argparse, logging, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
from netmiko import ConnectHandler

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "inventory" / "devices.yaml"
TEMPLATES = ROOT / "configs" / "templates"
RENDERED = ROOT / "configs" / "rendered"
ERROR_MARKERS = ("% Invalid", "% Incomplete", "% Ambiguous", "% Unknown", "Command rejected")

log = logging.getLogger("deploy")


def load_inventory():
    data = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    return [{**data.get("defaults", {}), **d} for d in data["devices"]]


def conn_params(dev):
    return {
        "device_type": dev["device_type"],
        "host": dev["console_host"],
        "port": dev["console_port"],
        "username": os.getenv("NET_USER", "admin"),
        "password": os.getenv("NET_PASS", ""),
        "secret": os.getenv("NET_ENABLE", ""),
        "global_delay_factor": 2,     # IOSv konsolu yavaş; takılırsa 4 yap
        "fast_cli": False,
        "timeout": 60,
    }


def render(dev, phase):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    text = env.get_template(f"{dev['role']}_faz{phase}.j2").render(**dev)
    return [l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("!")]


def push(dev, lines):
    with ConnectHandler(**conn_params(dev)) as conn:
        if not conn.check_enable_mode():
            conn.enable()
        out = conn.send_config_set(lines, cmd_verify=False, read_timeout=120)
        conn.save_config()
    errors = [l for l in out.splitlines() if any(m in l for m in ERROR_MARKERS)]
    return out, errors


def worker(dev, phase, dry_run):
    try:
        lines = render(dev, phase)
    except TemplateNotFound:
        return dev["name"], "ATLANDI (bu faz için şablon yok)", []
    RENDERED.mkdir(parents=True, exist_ok=True)
    (RENDERED / f"{dev['name']}_faz{phase}.cfg").write_text("\n".join(lines), encoding="utf-8")
    if dry_run:
        return dev["name"], f"DRY-RUN ({len(lines)} satır üretildi)", []
    if dev.get("console_port") is None:
        return dev["name"], "HATA: console_port tanımsız", []
    try:
        _, errors = push(dev, lines)
        return dev["name"], ("UYARI" if errors else "TAMAM"), errors
    except Exception as exc:                       # bağlantı/zaman aşımı vb.
        return dev["name"], f"HATA: {exc}", []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)   # GNS3 VM'i yormamak için düşük tut
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    devices = [d for d in load_inventory() if not args.only or d["name"] in args.only]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker, d, args.phase, args.dry_run) for d in devices]
        failed = 0
        for f in as_completed(futures):
            name, status, errors = f.result()
            log.info("%-12s %s", name, status)
            for e in errors:
                log.info("    %s", e)
            failed += status.startswith("HATA")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
```

**Notlar:**
- GNS3 konsolu genellikle **tek istemciyi** kabul eder: Python çalışırken GNS3'ün kendi konsol pencerelerini kapat.
- Konsolda kullanıcı doğrulaması yoksa (`line con 0` yalnızca `exec-timeout`/`logging synchronous`) Netmiko doğrudan prompt'u görür; takılırsa `global_delay_factor`'u artır veya o cihazda önce manuel bir Enter bırak.
- **Parolalar ortam değişkenlerinde:** `NET_USER`, `NET_PASS`, `NET_ENABLE` (asla repoya yazma, `.env` dosyası `.gitignore`'da olsun).

### 9.4 `core/scripts/validate.py` ("Ağ Sağlık Raporu")

```python
#!/usr/bin/env python3
"""Beklenen durumu cihazlardan okuyup karşılaştırır, JSON + konsol raporu üretir."""
import json, re, sys
from datetime import datetime
from pathlib import Path
from netmiko import ConnectHandler
sys.path.insert(0, str(Path(__file__).parent))
from deploy import load_inventory, conn_params          # bağlantı kodunu yeniden kullan

EXPECTED_OSPF = {"MRK-CORE1": 3, "MRK-CORE2": 3, "MRK-DAG1": 2, "MRK-DAG2": 2,
                 "SNR-RTR": 3, "FAB-RTR": 1}
EXPECTED_HSRP_ACTIVE = {"MRK-DAG1": {10, 30, 50, 90}, "MRK-DAG2": {20, 40, 60}}
EXPECTED_PO = {  # port-channel -> beklenen bayrak
    "MRK-CORE1": {1: "RU", 2: "RU"}, "MRK-CORE2": {1: "RU", 2: "RU"},
    "MRK-DAG1": {1: "RU", 2: "SU"},  "MRK-DAG2": {1: "RU", 2: "SU"},
}
EXPECTED_CDP = {"MRK-CORE1": 5, "MRK-CORE2": 5, "MRK-DAG1": 9, "MRK-DAG2": 9,
                "MRK-ERS-SAT": 2, "MRK-ERS-PER": 2, "MRK-ERS-BIS": 2, "MRK-ERS-YNT": 2,
                "MRK-ERS-SRV": 2, "SNR-RTR": 3, "ISS-RTR": 2, "FAB-RTR": 2, "FAB-ERS-1": 1}
HSRP_RE = re.compile(r"^\S+\s+(\d+)\s+\d+\s+(?:P\s+)?(Active|Standby|Init|Listen|Speak|Learn)\b", re.M)


def check(conn, name):
    res = {}
    # CDP
    cdp = conn.send_command("show cdp neighbors", use_textfsm=True)
    if isinstance(cdp, list) and name in EXPECTED_CDP:
        res["cdp"] = {"beklenen": EXPECTED_CDP[name], "gercek": len(cdp),
                      "ok": len(cdp) == EXPECTED_CDP[name]}
    # OSPF
    if name in EXPECTED_OSPF:
        out = conn.send_command("show ip ospf neighbor")
        n = len(re.findall(r"\bFULL/", out))
        res["ospf"] = {"beklenen": EXPECTED_OSPF[name], "gercek": n, "ok": n == EXPECTED_OSPF[name]}
    # HSRP
    if name in EXPECTED_HSRP_ACTIVE:
        out = conn.send_command("show standby brief")
        active = {int(g) for g, st in HSRP_RE.findall(out) if st == "Active"}
        exp = EXPECTED_HSRP_ACTIVE[name]
        res["hsrp"] = {"beklenen_active": sorted(exp), "gercek_active": sorted(active), "ok": active == exp}
    # EtherChannel
    if name in EXPECTED_PO:
        out = conn.send_command("show etherchannel summary")
        found = {int(n): flag for n, flag in re.findall(r"Po(\d+)\((\w+)\)", out)}
        res["etherchannel"] = {"beklenen": EXPECTED_PO[name], "gercek": found,
                               "ok": found == EXPECTED_PO[name]}
    # Tünel
    if name in ("SNR-RTR", "FAB-RTR"):
        out = conn.send_command("show interfaces tunnel0")
        up = "line protocol is up" in out
        res["tunnel"] = {"ok": up}
    return res


def main():
    report, bad = {}, 0
    for dev in load_inventory():
        name = dev["name"]
        try:
            with ConnectHandler(**conn_params(dev)) as conn:
                if not conn.check_enable_mode():
                    conn.enable()
                report[name] = check(conn, name)
        except Exception as exc:
            report[name] = {"ulasilamadi": str(exc)}
            bad += 1
            continue
        failed = [k for k, v in report[name].items() if isinstance(v, dict) and not v.get("ok", True)]
        bad += bool(failed)
        print(f"{name:<14}", "SAĞLIKLI" if not failed else f"SORUN: {', '.join(failed)}")

    out_dir = Path(__file__).resolve().parents[2] / "reports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"health_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRapor: {path}   |   sorunlu cihaz: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
```
> TextFSM şablon alan adları `ntc-templates` sürümüne göre değişebilir; sadece satır sayısı kullanıldığı için sorun çıkmaz. `show standby brief` regex'i sürüme göre ayarlanabilir; ilk çalıştırmada ham çıktıyı bir kez `print` edip doğrula.

### 9.5 `core/scripts/backup.py` ve zamanlama

```python
#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
from netmiko import ConnectHandler
from deploy import load_inventory, conn_params

def backup_all():
    stamp = f"{datetime.now():%Y-%m-%d_%H%M}"
    out_dir = Path(__file__).resolve().parents[2] / "backups" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    for dev in load_inventory():
        if dev.get("console_port") is None:
            continue
        try:
            with ConnectHandler(**conn_params(dev)) as conn:
                if not conn.check_enable_mode():
                    conn.enable()
                cfg = conn.send_command("show running-config")
            (out_dir / f"{dev['name']}.cfg").write_text(cfg, encoding="utf-8")
            print("OK  ", dev["name"])
        except Exception as exc:
            print("HATA", dev["name"], exc)

if __name__ == "__main__":
    backup_all()
```
**Zamanlama (Python `schedule`):**
```python
import schedule, time
from backup import backup_all
schedule.every().day.at("02:00").do(backup_all)
while True:
    schedule.run_pending(); time.sleep(30)
```
**Güvenlik notu:** `backups/` içinde parolalar (hash'li de olsa) bulunur → `backups/` ve `.env` dosyası `.gitignore`'a; Git'e atmak için Bölüm 10, Modül 4'teki "sanitize" adımını kullan.

---

## 10. Genişletme Modülleri (çekirdeğe dokunmadan)

**Ortak kural:** Hiçbiri `core/` klasörüne dokunmaz. Her biri `extensions/<modül>/` altında yaşar, çekirdeğin ürettiği config/rapor/inventory'yi **girdi** olarak kullanır ama üzerine yazmaz. Her modül ayrı git branch'inde geliştirilir; zaman kalırsa `main`'e merge edilir.

| # | Modül | Bu projede ne yapar | Girdi (core'dan) | Kabul kriteri |
|---|---|---|---|---|
| 1 | **Ansible katmanı** | Netmiko script'iyle aynı hedefi deklaratif playbook'larla yeniden üretir (`cisco.ios` koleksiyonu, `network_cli`/telnet bağlantı); "imperative vs declarative" karşılaştırması | `devices.yaml` → Ansible inventory | Aynı playbook 2. çalıştırmada `changed=0` |
| 2 | **NAPALM ile config drift** | `get_facts` / `compare_config` ile canlı config ↔ golden template farkı raporu | `configs/rendered/*.cfg`, Faz 6 yedekleri | Bir arayüze elle açıklama ekleyince drift raporunda görünür |
| 3 | **NetDevOps test katmanı (pytest)** | Her deploy sonrası ağın beklenen duruma ulaştığını doğrular (ör. `test_ospf_neighbors.py`, `test_hsrp_roles.py`, `test_acl_matrix.py`) | `validate.py` mantığı, Bölüm 7.1 matrisi | `pytest` tüm testlerde yeşil; bir kablo çıkarınca kırmızı |
| 4 | **Git tabanlı config versiyonlama** | Yedekleri yerel git deposuna (veya Gitea) commit'ler; **sanitize** adımı parola/hash satırlarını (`secret`, `password`) maskeler | `backups/` | `git log -p` ile bir cihazın değişim geçmişi okunur |
| 5 | **Self-hosted izleme (LibreNMS / Zabbix / Grafana+Prometheus)** | SNMP tabanlı canlı panel; GNS3 içinde Docker/VM (cloud değil) | Cihaz yönetim IP'leri (Loopback0 / Vlan90) | Panelde 13 cihaz, bir linki kapatınca alarm |
| 6 | **IPv6 dual-stack** | Mevcut IPv4'ün üstüne OSPFv3 + IPv6 ACL; yapıyı bozmadan paralel adres ailesi | Bölüm 5 adres planı (`2001:db8::/32` dokümantasyon aralığı) | `ping ipv6` + `show ipv6 ospf neighbor` |
| 7 | **Güvenlik sertleştirme** | Port Security, DHCP Snooping, DAI, `native vlan 999`, kullanılmayan portları kapatma, OSPF MD5 kimlik doğrulama; opsiyonel 802.1X/FreeRADIUS | Erişim switch'leri (Bölüm 5) | Kaçak DHCP sunucusu ve MAC taşması testleri engellenir |
| 8 | **Minimal web dashboard (Flask)** | `validate.py` JSON çıktısını tarayıcıda gösterir | `reports/health_*.json` | `localhost:5000`'de yeşil/kırmızı cihaz kartları |

**Çalışma sırası önerisi (iş başvurusu değeri + risk):** 3 (pytest) → 2 (NAPALM drift) → 7 (güvenlik) → 1 (Ansible) → 4 (git/sanitize) → 8 → 5 → 6.

**Güvenlik modülü için sana özgü notlar:**
- VPCS 802.1X desteklemez; 802.1X'i ancak bir IOS istemcisiyle gösterebilirsin.
- DHCP Snooping'de uplink'ler (`Gi0/0–0/1`) `trust`; Faz 3-D'deki Option 82 uyarısına dikkat.
- Native VLAN'ı 90'dan boş bir VLAN'a (ör. 999) çekmek, tüm trunk'larda **eşzamanlı** yapılmalı; önce Netmiko ile hepsine bas.

---

## 11. Klasör Yapısı, Git Stratejisi, Checkpoint Stratejisi

### 11.1 Klasör yapısı

```
network-automation-project/
├── core/                          # Faz 0–6 — bitince DOKUNULMAZ
│   ├── inventory/
│   │   └── devices.yaml
│   ├── scripts/                   # deploy.py, validate.py, backup.py
│   └── configs/
│       ├── templates/             # access_faz1.j2, dag_faz1.j2, ... (golden templates)
│       └── rendered/              # üretilen config'ler (denetim izi)
├── extensions/                    # her modül kendi klasöründe
│   ├── ansible/
│   ├── napalm-drift/
│   ├── tests/
│   ├── monitoring/
│   ├── ipv6/
│   ├── security-hardening/
│   └── dashboard/
├── backups/                       # .gitignore'da (veya sanitize edilmiş)
├── reports/                       # health_*.json
├── docs/
│   ├── PROJE.md                   # bu dosya
│   ├── checkpoints/               # faz0.md … faz6.md + ekran görüntüleri
│   ├── topology/                  # GNS3 .gns3project dışa aktarımı, çizimler
│   └── captures/                  # Wireshark .pcapng + analiz raporu
├── .gitignore                     # .env, backups/, .venv/
└── README.md
```

### 11.2 Git stratejisi

- **`main` = tamamlanmış çekirdek (Faz 0–6).** Her fazın sonunda commit + tag: `faz-0 … faz-6`.
- Her genişletme modülü kendi **feature branch**'inde: `ext/ansible`, `ext/napalm-drift`, `ext/pytest`, `ext/security`, … Zaman kalırsa `main`'e merge edilir.
- Commit mesajı kalıbı: `faz2: OSPF + HSRP çalışıyor (show ip ospf neighbor ekran görüntüsü docs/checkpoints/faz2.md)`.
- Bu, hocaya "**planlı, kontrollü genişleme**" olarak sunulur — BDUF'un tersi, adaptif mühendislik disiplini.
- GNS3 projesini her fazda `File → Export portable project` ile `docs/topology/` altına dışa aktar (config'ler dâhil).

### 11.3 Hocaya sunum / checkpoint stratejisi

Her fazın sonunda **1 sayfalık checkpoint notu** (`docs/checkpoints/fazN.md`):

```
# Faz N — <ad>            Tarih: ____
## Ne yapıldı        (3–5 madde)
## Hangi komutla doğrulandı   (komut + ekran görüntüsü)
## Beklenen ↔ gerçek   (tablo)
## Karşılaşılan sorun ve çözüm
## Sonraki faz için ayarlama
```
Bu hem BDUF yapılmadığının kanıtıdır, hem de erken bitme riskine karşı hocanın zamanında "şu modülü de ekle" diyebilmesini sağlar.

---

## 12. Doğrulama ve Demo Senaryoları

### 12.1 Faz sonu hızlı sağlık kontrol listesi

| Faz | Mutlaka yeşil olması gerekenler |
|---|---|
| 0 | 40 link yeşil · CDP sayıları (Faz 0-F) · 13 cihaza konsol erişimi |
| 1 | `show etherchannel summary` (Po'lar `RU`/`SU`, üyeler `P`) · `show spanning-tree` (kök + `Altn BLK` doğru yerde) · aynı VLAN'da ping başarılı, farklı VLAN'da başarısız |
| 2 | 14 OSPF komşuluk girişi · `show standby brief` (4 + 3 active) · VLAN'lar arası ping başarılı |
| 3 | Tünel `up/up` · FAB'da `O*IA` default · NAT tablosu doluyor · DHCP'den adres (FAB-PC1 dâhil) · ACL matrisi |
| 4 | `deploy.py` 2. çalıştırmada hatasız · sıfırdan 13 cihaz tek komutla |
| 5 | `validate.py` 13/13 sağlıklı, link kapatınca kırmızı |
| 6 | `backups/` dolu · 5+ Wireshark yakalaması analiz edilmiş |

### 12.2 Failover / dayanıklılık demoları (canlı sunum için)

Her demoda önce sürekli ping başlat (`SAT-PC1> ping 172.16.20.11 -t`) ve hedef cihazı GNS3'ten durdur ya da ilgili portu `shutdown` et.

| # | Senaryo | Eylem | Beklenen davranış | Kanıt komutu |
|---|---|---|---|---|
| F1 | **LACP üyesi kaybı** | CORE1 `Gi0/0`'ı kapat | Po1 `RU` kalır (tek üye `P`), OSPF komşuluğu kopmaz, kayıp yok | `show etherchannel summary` |
| F2 | **Tüm demet kaybı (ring tek kenar)** | CORE1 `Gi0/0` + `Gi0/1` kapat (Po1 düşer) | OSPF halkanın öbür yönünden yeniden yönlenir (CORE1 → DAG1 → DAG2 → CORE2) | `show ip route 172.20.20.2`, `traceroute` |
| F3 | **Core düğüm arızası** | MRK-CORE1'i durdur | Çıkış CORE2 → SNR üzerinden; DAG1 komşuluğu `Vlan254` üstünden devam; birkaç paket kaybı | `show ip ospf neighbor` (DAG1, SNR) |
| F4 | **Dağıtım düğüm arızası (HSRP)** | MRK-DAG1'i durdur | VLAN 10/30/50/90 HSRP'si DAG2'ye geçer (varsayılan hold ~10 sn); ERS-SAT'ın `Gi0/1`'i RSTP ile forwarding | `show standby brief` (DAG2) |
| F5 | **Erişim uplink kaybı** | L15 (DAG1 `Gi1/0` – ERS-SAT `Gi0/0`) kapat | ERS-SAT `Gi0/1` ~1–2 sn içinde forwarding; HSRP active hâlâ DAG1 → trafik DAG2 üzerinden **Po2 L2 trunk'ı** geçip DAG1'e ulaşır (L2 interlink'in neden gerekli olduğunun kanıtı) | `show spanning-tree vlan 10` |
| F6 | **ISS / WAN kaybı** | L11 (SNR `Gi0/2`) kapat | İnternet kesilir, default rota OSPF'ten kalkar; GRE tüneli (underlay) düşer → Tesis izole | `show ip route 0.0.0.0` (CORE1), `show interfaces tunnel0` |
| F7 | **Tünel arızası** | SNR `Tunnel0` `shutdown` | Tesis LAN'ı (172.18.10.0/24) rotası kaybolur, Merkez içi trafik etkilenmez | `show ip route 172.18.10.0` |
| F8 | **Sunucu uplink kaybı** | L19 (DAG1 `Gi1/2` – ERS-SRV `Gi0/0`) kapat | ERS-SRV `Gi0/1` forwarding; sunuculara erişim devam | `show spanning-tree vlan 50` |

> **HSRP hızlandırma (isteğe bağlı):** F4'teki ~10 sn kesintiyi azaltmak için SVI'larda `standby <grup> timers 1 3` (hello 1 sn, hold 3 sn) kullan; raporda "tuning" olarak anlat. İki taraftaki zamanlayıcılar aynı olmalı.

### 12.3 ACL test tablosu (Faz 3-F)

| # | Kaynak → Hedef | Beklenen | Neden |
|---|---|---|---|
| A1 | BIS-PC1 → SAT-PC1 `ping` | ✓ | BIS yönetici; SAT'ın dönüş paketi `echo-reply` izniyle geçer |
| A2 | SAT-PC1 → PER-PC1 `ping` | ✗ | `ACL-V10-IN` 10→20 yasak |
| A3 | SAT-PC1 → SNC-WEB `curl http://172.16.50.12` | ✓ (Docker'dan sonra) | 80 izinli |
| A4 | SAT-PC1 → SNC-DOSYA `ping` | ✓ | `icmp echo` izinli; ama FTP dışı portlar ✗ |
| A5 | SAT-PC1 → 172.16.90.11 (switch yönetimi) | ✗ | 10→90 yasak, `ACL-V90-OUT` |
| A6 | BIS-PC1 → 172.16.90.11 | ✓ | BIS yönetim VLAN'ına erişebilir |
| A7 | MSF-DZ1 → SNC-DNS (UDP 53) | ✓ | misafir DNS izni |
| A8 | MSF-DZ1 → SNC-WEB `ping` | ✗ | misafir → 172.16.0.0/12 yasak |
| A9 | MSF-DZ1 → `203.0.113.1` | ✓ | internet serbest |
| A10 | FAB-PC1 → SNC-WEB | ✓ | FAB → servisler (S) |
| A11 | FAB-PC1 → BIS-PC1 | ✗ | `ACL-FAB-IN` |
| A12 | SAT-PC1 → FAB-PC1 | ✓ | 10→110 izinli; dönüş `ACL-FAB-IN`'deki `echo-reply`/`established` ile geçer |

Her ACL satırında `show access-lists` içindeki `(N matches)` sayaçlarının arttığını ekran görüntüsüyle kanıtla.

### 12.4 DHCP testleri

| Test | Beklenen |
|---|---|
| `SAT-PC1> ip dhcp` | `DORA IP 172.16.10.1xx/24 GW 172.16.10.1` |
| `FAB-PC1> ip dhcp` | `172.18.10.1xx/24` (GRE üstünden relay) |
| `MSF-DZ1> ip dhcp` | `172.16.60.1xx/24` |
| SNC-DHCP `cat /var/lib/dhcp/dhcpd.leases` | 3+ kiralama kaydı |
| Wireshark (L36) | `giaddr` = ilgili VLAN'ın DAG SVI IP'si |

---

## 13. Sorun Giderme (GNS3 / IOSv'ye özgü)

| Belirti | Olası neden | Çözüm |
|---|---|---|
| IOSvL2 ilk açılışta 5–10 dk yanıt vermiyor | Normal; ilk boot yavaş, VM kaynak yetersiz olabilir | Bekle; `Servers Summary`'de CPU/RAM'e bak; düğümleri kademeli başlat |
| Port-channel `SD` / üyeler `I` (stand-alone) | Üç yaygın neden: (1) iki uçta mod uyuşmazlığı (biri `on`), (2) bir tarafta `no switchport` var, diğerinde yok, (3) üye portlarda farklı ayar | İki uçta `channel-group N mode active`, aynı switchport/routed modu; `show lacp neighbor` |
| Routed Po'da `no switchport` hatası | IOSvL2 sürümü kısıtı | Bölüm 8, Faz 1-D'deki yedek plan |
| OSPF `EXSTART/EXCHANGE`'de takılı | MTU uyuşmazlığı (tünel `ip mtu 1400` iki uçta aynı olmalı) | İki tünel ucunda aynı `ip mtu`; geçici `ip ospf mtu-ignore` |
| OSPF komşu yok | `passive-interface` kalmış, alan numarası/stub bayrağı uyuşmuyor, `network` tipi farklı | `show ip ospf interface brief`, `area 300 stub` iki uçta |
| SVI `up/down` | VLAN o switch'te yok veya o VLAN'ı taşıyan hiçbir aktif/forwarding port yok | `show vlan brief`, trunk `allowed vlan` listesi |
| HSRP iki DAG'da da `Active` | DAG'lar arası L2 yolu kopuk (Po2 trunk'ta VLAN izinli değil) | `show interfaces trunk` — Po2'de VLAN 10–90 izinli olmalı |
| HSRP sürekli flap | STP yeniden yakınsıyor veya çift IP | `show standby`, `show spanning-tree` |
| Tünel `up` ama OSPF komşu yok | Tünel endpoint'i tünelin içinden öğreniliyor (rekürsif) | FAB'da `/30` statik rota; `show ip route 198.51.100.0` |
| İnternete çıkış yok | NAT `inside/outside` yanlış, ISS-RTR bağlantısı | `show ip nat statistics`, `ping 198.51.100.2` |
| VPCS `ip dhcp` cevap alamıyor | Relay `ip helper-address` eksik, sunucu çalışmıyor, ACL DHCP'yi kesiyor, sunucunun default gateway'i yok | Sırayla: SVI helper → `ps aux \| grep dhcpd` → `show access-lists` sayaçları → Wireshark (L36) |
| Netmiko konsolda takılıyor | Başka bir telnet oturumu açık (GNS3 konsol penceresi), cihaz Enter bekliyor, yavaş konsol | GNS3 konsol pencerelerini kapat, `global_delay_factor` artır, cihaza manuel Enter gönder |
| Konsol portu değişti | Düğüm silinip yeniden eklendi / proje yeniden açıldı | `devices.yaml`'ı güncelle (veya `gen_inventory.py`) |
| VLAN'lar silinmiyor/kayboluyor | Switch `vlan.dat`'ta tutar, `write erase` yetmez | `delete vlan.dat` + `reload` |

---

## 14. Kaynak / Performans Notları

- **Düğüm sayısı:** 30 düğüm (13 IOS, 5 Docker, 12 VPCS). Asıl yük 13 IOS düğümüdür.
- **Bellek tahmini:** IOSv router ≈ 0,5 GB, IOSvL2 ≈ 0,75 GB varsayılan (kendi şablonundaki RAM değerine bak) → 3 × 0,5 + 10 × 0,75 ≈ **9 GB** + Docker sunucular + VPCS. GNS3 VM'e **en az 12–16 GB RAM** ve 4+ vCPU öner; ekran görüntüsünde VM RAM'inin boştayken %27 olduğunu gördüm, ama topoloji tam açıldığında bu hızla artacak. Yerel makinen için de tarafında RAM payı bırak.
- **Hızlandırıcı:** IOSv/IOSvL2 **QEMU/KVM** ile çalışır: GNS3 VM'de KVM (nested virtualization) açık olmalı. **idle-PC ayarı yok** — o yalnızca Dynamips içindir (eski kaynak dosyadaki öneri düzeltildi, D7).
- **Kaynak yetmezse (mimari bozulmadan):** (1) sunucuları 5'ten 2–3 çok-servisli container'a indir, (2) HQ'da 3 yerine 2 erişim switch'iyle gösterim yap ama bunu en son çare tut, (3) ağır konfigürasyonları (Wireshark yakalamaları) yalnız gerektiğinde çalıştır.
- **Python eşzamanlılığı:** `--workers 3–5` ile sınırla; 13 konsolu aynı anda zorlamak IOSv'yi yavaşlatır.
- **Yedek al:** Her faz sonunda GNS3 snapshot + `write memory` + `git tag`.

---

## 15. Düzeltme Günlüğü ve Eski İsim Eşlemesi

### 15.1 Düzeltme günlüğü (özet)

| Kod | Düzeltme | Nerede |
|---|---|---|
| U1 | Port isimleri `Gi0/4+` → `Gi1/0+` (16 portluk IOSvL2 şeması) | Bölüm 3 |
| U3 | Sunucular VPCS → Docker (önce SNC-DHCP) | Faz 3-E |
| U4 | KAP-1 / MSF-DZ1'in VPCS ile modellenmesi (KAP-1 = VLAN 90 access, MSF-DZ1 = VLAN 60 access) | Bölüm 1, Bölüm 3 |
| U5 | `FAB-ERS1` → `FAB-ERS-1` | Tüm doküman |
| U6 | Yönetim yolu: konsol telnet (Netmiko `cisco_ios_telnet`) | Bölüm 1, 9 |
| D1 | KAP-1 IP çakışması (`172.16.60.2` ↔ DAG1 SVI) → `172.16.90.16` | Bölüm 5 |
| D2 | OSPF Area 200 kaldırıldı; SNR↔Core linkleri Area 0; SNR gerçek ABR | Bölüm 6 |
| D3 | DAG1–DAG2 kenarı L2 trunk + `Vlan254` (RSTP/HSRP anlatımının tutarlı olması için) | Bölüm 3, 5, 6, Faz 1–2 |
| D4 | P2P adreslerinin tam yazılması | Bölüm 5.2 |
| D5 | Port-channel numaralarının cihaz-yerel standardizasyonu | Bölüm 3.2 |
| D6 | FAB-RTR "SVI" → routed arayüz; FAB-ERS-1 access + `Vlan110` yönetim | Faz 3-B |
| D7 | idle-PC önerisi düzeltildi (IOSv için geçersiz) | Bölüm 14 |
| D8 | VTP → `vtp mode transparent` | Faz 1 |
| D9 | Stateless ACL dönüş trafiği (`established`/`echo-reply`) | Bölüm 7 |
| D10 | DHCP unicast yenileme için `ACL-SRV-OUT` izni | Bölüm 7 |
| — | Netmiko/Paramiko konumlandırma notu | Faz 4 |
| — | Tünel için rekürsif yönlendirme koruması (`/30` statik) | Bölüm 6, Faz 3-A |
| — | Router interface'lerinin varsayılan `shutdown` olması (bootstrap'a `no shutdown`) | Faz 0-D |

**Tasarım kararı olarak bilerek korunanlar:** Core/Dağıtım **halka (ring) + LACP** (tam mesh değil), tüm erişim switch'lerinin çift uplink'i, VLAN başına yük dengeli HSRP (4 + 3), sunucu çiftliğinin VLAN 50'de tek switch'te toplanması, misafir Wi-Fi'nin Bilgi İşlem switch'inden çıkması, `198.51.100.0/24` ve `203.0.113.0/24` dokümantasyon aralıklarının "internet" için kullanımı.

### 15.2 Eski isim eşlemesi (roadmap dosyasından)

| Eski (roadmap) | Yeni (bu dosya / GNS3) |
|---|---|
| CORE-SW1 / CORE-SW2 | MRK-CORE1 / MRK-CORE2 |
| DIST-SW1 / DIST-SW2 | MRK-DAG1 / MRK-DAG2 |
| ACC-MUH | MRK-ERS-SAT (Satış/Pazarlama) |
| ACC-IK | MRK-ERS-PER (Personel) |
| ACC-IT | MRK-ERS-BIS (Bilgi İşlem) |
| ACC-YON | MRK-ERS-YNT (Üst Yönetim) |
| ACC-SRV | MRK-ERS-SRV |
| EDGE-RTR | SNR-RTR |
| ISP-RTR | ISS-RTR |
| BRANCH-RTR | FAB-RTR (+ FAB-ERS-1) |

### 15.3 Açık kalan kararların (senin onayına bağlı)

1. **KAP-1/MSF-DZ1 modellemesi** (U4): varsayılan VPCS+access; istersen KAP-1'i GNS3 "Ethernet switch" düğümüne çevir.
2. **Sunucu geçişi sırası** (U3): SNC-DHCP zorunlu, diğerleri kaynak durumuna göre.
3. **ACL politikası** (Bölüm 7.1): önerilen matristir, değiştirilebilir.
4. **Gerçek SSH yolu** (Ek A): isteğe bağlı; varsayılan konsol telnet.

---

*Son not: Bu belge, projenin **canlı referansıdır.** Her faz bittikçe "beklenen ↔ gerçek" farklarını docs/checkpoints altına işle; Bölüm 1'deki kararlar değişirse bu dosyada tek yerden güncelle.*
