# Anadolu Makina A.Ş. — Python Destekli Ağ Otomasyonu

İki lokasyonlu (Merkez + Üretim Tesisi) kurumsal ağın 13 Cisco IOS cihazını tek komutla yapılandıran,
doğrulayan ve yedekleyen otomasyon. Ana doküman: `../design-project-yol-haritası.md` (Bölüm 8–11 bu klasörü tarif eder).

| Faz | İçerik | Durum | Kanıt |
|---|---|---|---|
| 4 | `deploy.py` + 12 Jinja2 şablonu | Tamam | `docs/checkpoints/faz4.md` |
| 5 | `validate.py` — Ağ Sağlık Raporu | Tamam | `docs/checkpoints/faz5.md` |
| 6 | `backup.py` + paket analizi | Tamam | `docs/checkpoints/faz6.md`, `docs/captures/` |
| + | Genişletme modülleri (5 adet) | Tamam | `docs/checkpoints/genisletme.md` |

Faz 0–3 (elle kurulum) asıl GNS3 projesinde yapılmıştır; buradaki şablonlar o fazların değişkenleştirilmiş hâlidir.

## Kurulum

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env      # NET_ENABLE (ve gerekirse NET_PASS, NET_OSPF_KEY) doldur
```

## Günlük kullanım

```powershell
$py = ".venv\Scripts\python"
& $py core\scripts\gen_inventory.py --api                 # konsol portlarını GNS3'ten al
& $py core\scripts\deploy.py --list
& $py core\scripts\deploy.py --phase 1 2 3 --dry-run      # yalnız üret
& $py core\scripts\deploy.py --phase 1 2 3                # bas (basış sonrası geri okuyup doğrular)
& $py core\scripts\validate.py                            # Ağ Sağlık Raporu
& $py core\scripts\backup.py --sanitize --diff            # yedek + önceki yedekle fark
& $py core\scripts\pcap_report.py docs\captures\*.pcap    # paket analizi (Markdown)
```

Çıkış kodları — `deploy.py`: 0 temiz, 1 bağlantı hatası, 2 IOS uyarısı veya cihaza girmeyen satır.
`validate.py`: 0 sağlıklı, 1 sorunlu. `drift.py`: 0 uyumlu, 1 sapma var.

## Yapı

```
core/                      Faz 4–6 çekirdeği
  inventory/devices.yaml   13 cihaz + ağ geneli değişkenler + beklenen durum (links, expected)
  inventory/consoles.yaml  konsol portları (gen_inventory.py üretir)
  configs/templates/       <rol>_faz<N>.j2
  configs/rendered/        üretilen config'ler (denetim izi)
  scripts/                 deploy, validate, backup, pcap_report, confcheck, gen_inventory, fake_ios
extensions/                çekirdeğe dokunmayan modüller
  tests/                   pytest: 31 çevrimdışı + 6 canlı test
  drift/                   şablon ↔ canlı config sapma raporu
  security-hardening/      Port Security, DHCP Snooping, OSPF MD5 (+ geri alma)
  config-history/          maskelenmiş yedeklerin yerel git geçmişi
  dashboard/               sağlık + sapma raporu tek HTML sayfada
backups/  reports/         çıktılar (backups/ git'e girmez)
docs/checkpoints/          faz notları        docs/captures/  pcap + analiz
../lab/                    GNS3 olmadan QEMU ile mini laboratuvar ve test senaryoları
```

## Genişletme modülleri

```powershell
& $py -m pytest extensions\tests                                   # çevrimdışı (cihaz gerekmez)
& $py -m pytest extensions\tests --live                            # + canlı ağ testleri
& $py extensions\drift\drift.py                                    # en son yedeğe göre sapma
& $py extensions\security-hardening\harden.py --dry-run            # sertleştirme (--rollback ile geri al)
& $py extensions\config-history\commit_backups.py                  # yedekleri git geçmişine işle
& $py extensions\dashboard\dashboard.py --serve                    # http://localhost:5000
& $py extensions\ipv6\ipv6.py --dry-run                            # IPv6 dual-stack (--verify, --rollback)
& $py extensions\monitoring\monitor.py --setup                     # SNMP config'ini bas
& $py extensions\monitoring\monitor.py --watch 30                  # 30 sn'de bir yokla, alarm üret
```

| Modül | Klasör | Ne yapar | Ek ayar (`.env`) |
|---|---|---|---|
| IPv6 dual-stack | `extensions/ipv6` | OSPFv3 (alanlar IPv4 ile aynı), SLAAC, IPv6 ACL; adres planı `plan.yaml` | — |
| İzleme | `extensions/monitoring` | SNMP v2c ile 13 cihazı yoklar; link ve erişim alarmı; pano "Canlı izleme" bölümü | `NET_SNMP_RO`, `NET_SNMP_STATION` |
| Ansible | `extensions/ansible` | Faz 1–2 hedefinin deklaratif karşılığı; envanter `devices.yaml`'dan üretilir | `NET_USER`, `NET_PASS`, `NET_ENABLE` |

**Ansible** Windows'ta kontrol düğümü olarak çalışmaz; Linux ya da WSL gerekir. Cihazlara SSH ile bağlanır
(`network_cli`), bu yüzden kontrol düğümü yönetim ağına (VLAN 90) erişebilmelidir:

```bash
cd extensions/ansible
export NET_USER=admin NET_PASS=... NET_ENABLE=...
ansible-playbook site.yml              # ikinci çalıştırmada changed=0 beklenir
ansible-playbook site.yml --check --diff
```

Laboratuvarda bunun için `..\lab\ansible_vm.py` RAM'de çalışan küçük bir Alpine Linux açar (`start`, `run`, `stop`).

**Pano ve laboratuvar aynı anda çalışırken** panoyu başka portta aç (`--port 5050`): lab konsolları 5000–5024 arasını kullanır.

## Rol ↔ şablon

| Rol | Cihazlar | Faz 1 | Faz 2 | Faz 3 |
|---|---|---|---|---|
| `core` | MRK-CORE1/2 | LACP routed Po | OSPF Area 0 | — |
| `dag` | MRK-DAG1/2 | VLAN, STP, Po, uplink | SVI, HSRP, OSPF | DHCP havuzları (yalnız DAG1), ACL |
| `access` | MRK-ERS-* | VLAN, trunk, access | Vlan90 yönetim | — |
| `branch_sw` | FAB-ERS-1 | — | — | VLAN 110, yönetim |
| `snr` | SNR-RTR | — | OSPF Area 0 | WAN, GRE, Area 300, NAT |
| `iss` | ISS-RTR | — | — | WAN arayüzleri |
| `fab` | FAB-RTR | — | — | WAN, GRE, Area 300, relay, ACL |

## Bilinmesi gerekenler

- **Konsol tek istemcilidir.** Betikler çalışırken GNS3 konsol pencerelerini kapat.
- **Bootstrap elle.** Faz 0-D (hostname, enable secret, kullanıcı) şablonda yoktur; lab için `../lab/console.py bootstrap` yapar.
- **Docker yok.** Devir notu uyarınca DHCP havuzları MRK-DAG1'de, FAB-RTR helper adresi `172.20.20.3`.
- **Basış sonrası doğrulama.** `deploy.py` her cihazda `show running-config`'i geri okur; girmemiş satırı bir kez daha basar, yine yoksa `EKSIK` olarak raporlar. Nedeni `faz6.md`'de.
- **Parolalar `.env`'de.** Depodaki `.env` lab için üretilmiş test değerleridir; asıl GNS3 projesinde kendi değerlerinle değiştir.

## Gerçek GNS3 projesinde çalıştırma

GNS3 2.2.61 bu bilgisayarda kurulu; proje `C:\Users\merts\GNS3\projects\DesignProject`. Adımlar ve sonuçlar
`docs/checkpoints/tam-topoloji.md` içinde ("Gerçek proje GNS3'te"). Kısaca: sağlık raporu enable parolası olmadan
`NET_NO_ENABLE=1` ile çalışır; `deploy.py`, `backup.py` ve genişletmeler için `.env`'e gerçek parolalar yazılmalıdır.
GNS3 ile QEMU lab aynı konsol portlarını kullanır, ikisi aynı anda çalıştırılmaz.

## GNS3 olmadan mini laboratuvar (`..\lab`)

GNS3 kurulu olmayan veya RAM'i az bir makinede gerçek IOSv / IOSvL2 imajlarını doğrudan QEMU ile çalıştırır.
Gerekenler: `winget install SoftwareFreedomConservancy.QEMU`, imajlar `..\lab\images` altında.

```powershell
$env:NET_CONSOLE_HOST = "127.0.0.1"
& $py ..\lab\lab.py start MRK-DAG1 MRK-DAG2
& $py ..\lab\console.py bootstrap MRK-DAG1 MRK-DAG2
& $py core\scripts\deploy.py --phase 1 2 3 --only MRK-DAG1 MRK-DAG2
& $py core\scripts\validate.py --only MRK-DAG1 MRK-DAG2 --partial
& $py ..\lab\lab.py stop
```

| Senaryo | Cihaz | RAM | Süre | Ne sınar |
|---|---|---|---|---|
| `validate_all.py` | 13, tek tek | 0,8 GB | ~1 saat | Faz 1–3 sözdizimi + idempotentlik |
| `pair_test.py` | DAG1+DAG2 | 1,5 GB | ~15 dk | LACP, OSPF, HSRP, STP, HSRP geçişi |
| `faz5_test.py` | DAG1+DAG2 | 1,5 GB | ~20 dk | Sağlık raporu yeşil → kırmızı → yeşil |
| `wan_test.py` | 3 router | 1,5 GB | ~10 dk | GRE, Area 300, NAT, tünel arızası |
| `big_test.py` | 9 cihaz | ~6,2 GB | ~50 dk | Uçtan uca: DHCP relay, ACL, sertleştirme, F3, F4 |
| `up.py` + `full_test.py` | 13 cihaz + 17 uç | ~8 GB | ~2,5 saat | Her şey: kurulum, F1–F8, saldırı testleri, geri alma, IPv6, izleme |

`$env:LAB_CAPTURE = "1"` ile başlatılan düğümlerin kablolu portları `..\lab\captures\*.pcap` olarak kaydedilir.
