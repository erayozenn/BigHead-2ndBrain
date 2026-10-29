# Your_2ndBRAIN

> Durum: pre-alpha (Faz 1a — iskelet). Henüz kullanılabilir değil. Çalışma adı; kesin isim v0.1'den önce verilecek.

**Claude Code + Obsidian** için kişisel bir ikinci beyin. Andrej Karpathy'nin "LLM Wiki"
desenine dayanır: sen değişmez ham kaynakları toplarsın, Claude bunlardan birbirine bağlı bir
wiki derler ve bakımını yapar; kısa bir şema dosyası ikinizi aynı kurallarda tutar.

[English](README.md)

## Neden

- **Wiki sohbet değil, derlenir.** Bilgi sohbet geçmişinde kaybolmaz; kaynaklı, bağlantılı
  sayfalarda birikir.
- **Tasarımı gereği dürüst.** Her iddia kaynağa bağlanır; kaynaksız, geçici ve tartışmalı
  iddialar işaretlenir; tarihli bilgiler tarihini taşır.
- **Obsidian'la birlikte yaşar.** Düz Markdown, wikilink, bağımlılık yok. Claude notlarını
  yeniden adlandırmaz, Obsidian ayarlarına dokunmaz.
- **Aboneliğe uygun.** Claude Pro/Max için tasarlandı; API key gerekmez.

## Nasıl çalışır

Bkz. [docs/architecture.md](docs/architecture.md) (İngilizce).

```
raw/     senin kaynakların (Claude için salt okunur)
wiki/    Claude'un yazdığı sayfalar: kaynaklar, kavramlar, varlıklar, sentezler
notes/   senin notların (Claude asla düzenlemez)
```

## Kurulum (v0.1 için planlanıyor)

```
/plugin install your-2ndbrain --marketplace <owner>/<repo>
```

Ardından boş bir klasörde init skill'ini çalıştır ve [docs/obsidian-setup.md](docs/obsidian-setup.md)
adımlarını izle.

## Gereksinimler

- Claude Code (Pro veya Max abonelik)
- Obsidian
- Git
- Python 3.10+ (hook'lar ve skill script'leri için)
- İsteğe bağlı: pypdf (`pip install pypdf`), 10 sayfadan uzun PDF'ler ve ucuz salt-metin okuma
  için. Kurulu değilse `ingest` 10 sayfaya kadar olan PDF'leri doğrudan okur.

## Skill'ler

| Skill | Ne yapar |
|---|---|
| `/your-2ndbrain:ingest <yol-veya-url> [text\|smart\|full]` | Bir kaynağı `raw/` içine alır, uygun maliyetle okur, seninle tartışır, wiki sayfalarını yazar, index/log/hot cache'i günceller, link ve alıntıları doğrular. |

## Teşekkür

- Andrej Karpathy — projenin dayandığı "LLM Wiki" deseni.
- Claude Code + Obsidian alanındaki diğer açık projelerden ilham alınan fikirler (v0.1 öncesi
  YAPILACAK: her projeyi linkiyle listele, lisanslarını doğrula).

## Lisans

[MIT](LICENSE)
