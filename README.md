# Design Project: Python Destekli Kurumsal Ağ Otomasyonu (GNS3)

"Anadolu Makina A.Ş." için üç katmanlı, yüksek erişilebilirlikli kurumsal ağ ve onu yöneten Python otomasyonu.
13 Cisco IOSv / IOSvL2 cihazı, 17 VPCS ucu, 40 bağlantı.

| Klasör / dosya | İçerik |
|---|---|
| `network-automation-project/` | Otomasyon çekirdeği (envanter, Jinja2 şablonları, `deploy.py`, `validate.py`, `backup.py`), dokuz genişletme modülü, belgeler |
| `lab/` | Test betikleri: gerçek GNS3 projesinde koşanlar (`gns3_*.py`) ve GNS3'süz QEMU laboratuvarı |
| `design-project-yol-haritasi.md` | Tasarım ve artımlı yol haritası (parolalar maskelenmiştir) |

Başlangıç noktaları:
- Kurulum ve kullanım: `network-automation-project/README.md`
- Faz bazında kanıt: `network-automation-project/docs/checkpoints/` (`faz0.md` … `faz6.md`, `tam-topoloji.md`)
- Canlı gösterim sırası: `network-automation-project/docs/sunum-rehberi.md`
- Paket kayıtları ve analizi: `network-automation-project/docs/captures/gercek/analiz.md`

Depoda parola, parola özeti ya da cihaz imajı yoktur. Parolalar `.env` ve `lab/gns3_env.txt` dosyalarından
okunur; ikisi de git dışındadır. Cisco imajları lisanslıdır ve depoya konmamıştır.
