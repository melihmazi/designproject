# Sunum Rehberi (canlı gösterim için)

Bu sayfa, projeyi hocaya gösterirken izlenecek sırayı verir. Her adımın yanında beklenen sonuç ve kanıtın durduğu
dosya var. Komutlar PowerShell içindir, `network-automation-project` klasöründen çalıştırılır.

## 0. Hazırlık (sunumdan 15 dakika önce)

1. Oyun ve ağır programlar kapalı olsun. Cihazlar donanım hızlandırma olmadan çalışıyor; açılış ~10 dakika.
2. GNS3'ü aç, `DesignProject` projesini aç, yeşil **Start** düğmesine bas.
3. **GNS3 penceresini sunum bitene kadar kapatma.** Pencere kapanınca sunucu ve bütün cihazlar da kapanır.
4. Kısayollar:

```powershell
$py = ".venv\Scripts\python.exe"
$env:NET_CONSOLE_HOST = "127.0.0.1"; $env:NET_NO_ENABLE = "1"
```

5. Hazır mı kontrolü (13/13 görene kadar bir iki kez dene):

```powershell
& $py core\scripts\validate.py
```

## 1. Topoloji ve tasarım (2 dakika, GNS3 ekranı)

- Üç katman: çekirdek (CORE1, CORE2), dağıtım (DAG1, DAG2), erişim (5 switch). Kenarda SNR-RTR, internet için
  ISS-RTR, uzak Tesis için FAB-RTR.
- Her şey çift: iki çekirdek, iki dağıtım, her erişim switch'inde iki uplink, demetlenmiş (LACP) bağlantılar.
- Kanıt: `docs/checkpoints/faz0.md`, `faz1.md`.

## 2. Ağ Sağlık Raporu (2 dakika)

```powershell
& $py core\scripts\validate.py
& $py extensions\dashboard\dashboard.py      # reports\dashboard.html üretir, tarayıcıda aç
```

Beklenen: `13/13 cihaz saglikli | 97 OK`. Pano yeşil kartlarla aynı sonucu gösterir.
Söylenecek: rapor salt okunurdur; CDP, EtherChannel, STP, OSPF, HSRP, tünel ve NAT'ı tek komutla denetler.

## 3. Uçtan uca erişim ve ACL (3 dakika)

```powershell
& $py ..\lab\gns3_vpcs.py       # 8/8
& $py ..\lab\gns3_acl.py        # 16/16, ACL sayaçlarıyla
```

Elle göstermek istersen GNS3'te SAT-PC1 konsolunda:

```
ping 203.0.113.1          (internet, geçer)
ping 172.16.20.11         (Personel, "administratively prohibited")
```

Kanıt: `docs/checkpoints/faz3.md`.

## 4. Yük devretme (5 dakika, en etkileyici bölüm)

**Hafif senaryo (kayıp yok):** SAT-PC1 konsolunda `ping 203.0.113.1 -t` başlat. GNS3'te CORE1–CORE2 arasındaki iki
bağlantıdan birine sağ tıkla, **Suspend**. Ping kesilmez (LACP). Sonra **Resume**.

**Ağır senaryo (düğüm arızası):**

```powershell
python ..\lab\gns3_failover.py MRK-CORE1
```

Betik pingi başlatır, CORE1'i durdurur, en uzun kesintiyi yazar, CORE1'i geri açar. Beklenen: ~14 sn.
Söylenecek: varsayılan zamanlayıcılarla 61 sn sürüyordu; OSPF hello 1 / dead 4 ve HSRP 1 / 3 ile 14 sn'ye indi.
CORE1'in geri gelmesi 3–4 dakika sürer; bu arada sonraki bölüme geç.

Ölçülmüş bütün senaryolar: `docs/checkpoints/faz2.md` (F1–F8 tablosu).

## 5. Wireshark (3 dakika)

Canlı: GNS3'te SNR-RTR ↔ ISS-RTR bağlantısına sağ tıkla, **Start capture**. Filtreye `icmp || gre` yaz. SAT-PC1'den
internete ping at: kaynak adres 198.51.100.1 olarak görünür (NAT). FAB-PC1'den ping at: GRE içinde görünür.

Hazır kayıtlar (canlı gösterim aksarsa): `docs\captures\gercek\*.pcap`, açıklaması `docs\captures\gercek\analiz.md`.
En çarpıcı ikisi:
- `G2_...pcap`, filtre `dhcp`: tünelin içinden geçen DHCP relay, `giaddr` 172.18.10.1.
- `..\core1_snr.pcap` ve `..\core2_snr.pcap`, filtre `icmp`: arıza anında trafiğin öbür hatta geçişi.

## 6. Otomasyon (3 dakika)

```powershell
& $py core\scripts\deploy.py --phase 1 2 3 --dry-run                   # şablonlardan üretilen yapılandırma
python ..\lab\gns3_run.py sw core\scripts\backup.py --only '@grup'      # switch yedekleri
python ..\lab\gns3_run.py rtr core\scripts\backup.py --only '@grup'     # router yedekleri
& $py extensions\drift\drift.py                                        # yedek ↔ şablon farkı
& $py -m pytest extensions\tests -q                                    # 47 çevrimdışı test
```

Söylenecek: 13 cihazın yapılandırması tek envanter dosyasından ve 12 şablondan üretiliyor; aynı komut ikinci kez
çalışınca hiçbir şey değiştirmiyor; sapma raporu elle yapılan değişikliği yakalıyor.

## 7. Genişletmeler (2 dakika, sadece sayarak)

| Modül | Tek cümle | Kanıt |
|---|---|---|
| pytest | Sağlık raporunun her kontrol grubu bir test | `genisletme.md` |
| Sapma raporu | Canlı yapılandırma ↔ şablon | `tam-topoloji.md` |
| Güvenlik sertleştirme | Port Security, DHCP Snooping, OSPF MD5; kaçak DHCP ve MAC taşması engellendi | `tam-topoloji.md` |
| Yapılandırma geçmişi | Maskelenmiş yedekler yerel git deposunda | `genisletme.md` |
| Pano | Sağlık raporu tarayıcıda | `reports\dashboard.html` |
| Ansible | Aynı hedef deklaratif; ikinci koşuda `changed=0` | `tam-topoloji.md` |
| SNMP izleme | 13 cihaz, link kapanınca alarm | `tam-topoloji.md` |
| IPv6 | OSPFv3 + IPv6 ACL, IPv4'e dokunmadan | `tam-topoloji.md` |
| Hızlı yakınsama | 61 sn → 14 sn | `faz2.md` |

## Olası sorular

- **Neden iki DAG arasında L2 trunk var?** Bir erişim switch'inin birincil uplink'i koparsa trafik yedek uplink'ten
  öbür DAG'a gider; HSRP Active hâlâ ilk DAG'dadır, oraya bu trunk'tan ulaşır (F5).
- **Neden hâlâ 14 sn?** Dead süresi 4 sn, üstüne SPF bekleme süreleri ve pingin kendi zaman aşımı. Daha kısası için
  BFD gerekir; IOSvL2 desteklemiyor.
- **F4'te DHCP neden yok?** Tek DHCP sunucusu DAG1. İyileştirme: havuzları iki DAG'a bölmek ya da ayrı sunucu.
- **Sunucular gerçek mi?** Hayır, VPCS. Port bazlı ACL'ler sınandı, servislerin kendisi sınanmadı.
- **Süreler gerçek donanımda aynı mı?** Hayır. Ölçümler yazılım emülasyonunda alındı.

## Bir şey ters giderse

| Belirti | Çözüm |
|---|---|
| Betik "WinError 10053" veriyor | Düğüm yeni yeniden başlamış. GNS3'te düğüme sağ tıkla, konsolu kapatıp aç ya da 1 dakika bekle |
| Sağlık raporu kırmızı, cihazlar yeni açıldı | OSPF ve STP oturana kadar 2–3 dakika bekle, tekrar koş |
| Port-channel açıklaması sapma raporunda | `python ..\lab\gns3_run.py sw ..\lab\gns3_fix.py` |
| Zamanlayıcıları eski hâline almak | `python ..\lab\gns3_run.py sw extensions\fast-convergence\hizli.py --rollback --only '@grup'`, sonra aynısı `rtr` ile |
