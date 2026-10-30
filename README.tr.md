# Your 2ndBrain

![Your 2ndBrain — kaynakların girer, bağlantılı ve kaynaklı bir wiki çıkar](docs/images/hero.svg)

> Durum: v0.1 hazırlanıyor.

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

![Bir wiki sayfasının anatomisi: frontmatter, gelecekteki ajan için özet, kaynaklı iddialar, tarihli bilgiler, tartışmalı ve geçici işaretleri](docs/images/page-anatomy.svg)

## Nasıl çalışır

![Nasıl çalışır: ham kaynaklar /ingest ile wiki'ye derlenir, /query wiki'den cevaplar, /save wiki'yi genişletir; oturum hafızasını /handoff korur](docs/images/how-it-works.svg)

Ayrıntılar: [docs/architecture.md](docs/architecture.md) (İngilizce).

```
raw/     senin kaynakların (Claude için salt okunur)
wiki/    Claude'un yazdığı sayfalar: kaynaklar, kavramlar, varlıklar, sentezler
notes/   senin notların (Claude asla düzenlemez)
```

## Kurulum (v0.1 için planlanıyor)

```
/plugin marketplace add erayozenn/Your-2ndBrain
/plugin install your-2ndbrain@your-2ndbrain
```

Ardından boş bir klasörde (veya mevcut bir Obsidian vault'unda) `/your-2ndbrain:init` çalıştır ve [docs/obsidian-setup.md](docs/obsidian-setup.md)
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
| `/your-2ndbrain:init [hedef klasör]` | Şablonlardan bir vault kurar — klasörler, `CLAUDE.md` şeması, hot cache, index, log, ayarlar — boş bir klasörde veya mevcut bir Obsidian vault'unda. Önce deneme çalıştırması yapar; hiçbir dosyanın üzerine yazmaz. |
| `/your-2ndbrain:ingest <yol-veya-url> [text\|smart\|full]` | Bir kaynağı `raw/` içine alır, uygun maliyetle okur, seninle tartışır, wiki sayfalarını yazar, index/log/hot cache'i günceller, link ve alıntıları doğrular. |
| `/your-2ndbrain:query <soru> [quick\|standard\|deep]` | Wiki'den cevap verir — hot cache, index, sonra okuma bütçesi içinde en ilgili sayfalar — her iddiayı kaynaklar, wiki yetmediğinde bunu açıkça söyler. |
| `/your-2ndbrain:save [başlık veya kaydedilecek şey]` | Oturumdaki iyi bir cevabı veya karşılaştırmayı sentez sayfası olarak kaydeder (veya mevcut birini genişletir); kaynakları ve belirsizlik işaretlerini korur. |
| `/your-2ndbrain:handoff [sonraki oturum için not]` | Oturum sonu devri: hot cache'in "Now" bölümünü yeniden yazar, kelime sınırında tutar, commit edilmemiş işi bildirir, düzeltmelerinden öğrenilen kuralları önerir. |

İsteğin uyduğunda Claude bu skill'leri kendiliğinden de kullanır (ör. "bu makaleyi ingest et").

> **Bir skill'i mi düzenledin?** Ardından `/reload-plugins` çalıştır — yoksa mevcut oturumda eski
> metin çalışmaya devam eder.

## Teşekkür

- Andrej Karpathy — projenin dayandığı "LLM Wiki" deseni.
- Claude Code + Obsidian alanındaki diğer açık projelerden ilham alınan fikirler (v0.1 öncesi
  YAPILACAK: her projeyi linkiyle listele, lisanslarını doğrula).

## Lisans

[MIT](LICENSE)
