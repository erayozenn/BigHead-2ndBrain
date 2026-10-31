# BigHead 2ndBrain

![BigHead 2ndBrain — kaynakların girer, bağlantılı ve kaynaklı bir wiki çıkar](docs/images/hero.svg)

> **Durum: v0.1 — deneysel.** Skill'ler ve vault şeması 0.x sürümleri arasında hâlâ
> değişebilir. Güncellemeler mevcut bir vault'u asla yeniden yazmaz; vault'unun `CLAUDE.md`
> dosyasının ilk satırı hangi şablondan kurulduğunu gösterir. Şimdiye kadar Windows'ta test
> edildi; macOS ve Linux geri bildirimleri memnuniyetle karşılanır.

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

## Kurulum

Terminalde:

```
claude plugin marketplace add erayozenn/BigHead-2ndBrain
claude plugin install bighead@bighead
claude plugin list        # bighead@bighead  Status: ✔ enabled
```

Ya da bir Claude Code oturumunda: `/plugin marketplace add erayozenn/BigHead-2ndBrain`, ardından
`/plugin install bighead@bighead` — bu, plugin'in panelini açar; kurulumu orada
onaylarsın. Sonra yeni bir oturum başlat (veya `/reload-plugins` çalıştır).

Ardından boş bir klasörde (veya mevcut bir Obsidian vault'unda) `/bighead:init` çalıştır ve [docs/obsidian-setup.md](docs/obsidian-setup.md)
adımlarını izle.

## Gereksinimler

- Claude Code (Pro veya Max abonelik)
- Obsidian
- Git
- Python 3.10+ (hook'lar ve skill script'leri için)
- Windows: Git for Windows (Git Bash) — guard hook bash üzerinden çalışır
- İsteğe bağlı: pypdf (`pip install pypdf`), 10 sayfadan uzun PDF'ler ve ucuz salt-metin okuma
  için. Kurulu değilse `ingest` 10 sayfaya kadar olan PDF'leri doğrudan okur.

## Skill'ler

| Skill | Ne yapar |
|---|---|
| `/bighead:init [hedef klasör]` | Şablonlardan bir vault kurar — klasörler, `CLAUDE.md` şeması, hot cache, index, log, ayarlar — boş bir klasörde veya mevcut bir Obsidian vault'unda. Önce deneme çalıştırması yapar; hiçbir dosyanın üzerine yazmaz. |
| `/bighead:ingest <yol-veya-url> [text\|smart\|full]` | Bir kaynağı `raw/` içine alır, uygun maliyetle okur, seninle tartışır, wiki sayfalarını yazar, index/log/hot cache'i günceller, link ve alıntıları doğrular. |
| `/bighead:query <soru> [quick\|standard\|deep]` | Wiki'den cevap verir — hot cache, index, sonra okuma bütçesi içinde en ilgili sayfalar — her iddiayı kaynaklar, wiki yetmediğinde bunu açıkça söyler. |
| `/bighead:save [başlık veya kaydedilecek şey]` | Oturumdaki iyi bir cevabı veya karşılaştırmayı sentez sayfası olarak kaydeder (veya mevcut birini genişletir); kaynakları ve belirsizlik işaretlerini korur. |
| `/bighead:handoff [sonraki oturum için not]` | Oturum sonu devri: hot cache'in "Now" bölümünü yeniden yazar, kelime sınırında tutar, commit edilmemiş işi bildirir, düzeltmelerinden öğrenilen kuralları önerir. |
| `/bighead:lint [quick\|standard\|deep]` | Wiki'nin sağlık kontrolü: script taraması (şema, kırık linkler, kopyalar, sahipsiz sayfalar, index kapsamı, boyutlar, eskimiş sayfalar) ve okuma bütçesi içinde yargı kontrolleri (çelişkiler, tarihsiz bilgiler, kaynak eksikleri, sayfası olmayan kavramlar). Önce rapor verir; yalnızca onayladıklarını düzeltir. |
| `/bighead:teach-back <konu veya notes/ dosyası>` | Anlayışını sına: bir konuyu kendi cümlelerinle açıklarsın, Claude bunu wiki ile karşılaştırır ve eksikleri, hataları, belirsiz noktaları soru olarak döner. Hiçbir şey yazmaz. |
| `/bighead:review make <sayfa> \| quiz [deste]` | Bilgi kartları: bir wiki sayfasından hatırlama kartları taslağı çıkarır, onayladıklarını `cards/` içine ekler (Obsidian [Spaced Repetition](https://github.com/st3v3nmw/obsidian-spaced-repetition) formatı) ya da sohbette, vadesi gelenlerden başlayarak seni sınar. Mevcut kartlara ve zamanlamalarına asla dokunmaz. |
| `/bighead:today [odak]` | Güne başlangıç: hot cache, açık thread'ler, son log, bugünkü daily note ve vadesi gelen kartlar → kısa bir plan ve bir hatırlama sorusu. Hiçbir şey yazmaz. |
| `/bighead:weekly [YYYY-Www]` | Haftalık değerlendirme: eklenen, değişen ve karar verilen şeyler, eksikler, thread'ler, kartlar, gelecek hafta için üç öneri; onaylarsan `archive/` içine kaydedilir. |

İsteğin uyduğunda Claude bu skill'leri kendiliğinden de kullanır (ör. "bu makaleyi ingest et").

**Çalışma modu.** Plugin ayrıca bir `tutor` [output style](https://code.claude.com/docs/en/output-styles)
içerir: çalışma sorularında Claude önce senin tahminini ister, ipuçlarını kademeli verir, tam
cevabı yalnızca sen istediğinde gösterir; vault işlemleri (ingest, lint, …) her zamanki gibi
çalışır. `/output-style bighead:tutor` ile açılır, `/output-style default` ile kapanır.
Varsayılan olarak asla açık değildir. Ingest de makale veya ders kaynaklarında, okumadan önce
2–5 sorunu almayı bir kez (atlanabilir) teklif eder ve bunları kaynak sayfasında cevaplar.

> **Bir skill'i mi düzenledin?** Ardından `/reload-plugins` çalıştır — yoksa mevcut oturumda eski
> metin çalışmaya devam eder.

## Hook'lar

**Guard.** Plugin, bir vault içinde (`raw/` klasörü ve `# Vault Schema & Rules` ile başlayan bir `CLAUDE.md`
olan klasör) her `Write`, `Edit` ve `NotebookEdit` öncesinde çalışan bir `PreToolUse` hook'u içerir.
Şunları reddeder:

- `raw/` altındaki mevcut dosyalarda değişiklik ve `raw/web/` dışında yeni raw dosyası
- frontmatter'ında `author: me` olan notlarda düzenleme
- `.obsidian/` altındaki her şey

Vault dışında hiçbir şey yapmaz. Guard vault içinde kendisi hata verirse, düzenlemeyi geçirmek
yerine engeller.

**Sınır:** guard yalnızca dosya araçlarını görür. Shell komutları (`rm`, `del`,
`python -c "os.remove(...)"`, `>` yönlendirme) incelenmez; yaygın olanları vault'un izin kuralları
reddeder, kalanını git geri alınabilir kılar.

**Validator.** Bir `PostToolUse` hook'u, Claude'un az önce yazdığı veya düzenlediği her vault
sayfasını şemaya göre kontrol eder: zorunlu frontmatter alanları ve izin verilen değerler, geçerli
tarihler (`updated`, `created`'dan önce ya da gelecekte olamaz), "For future agent" özet callout'u,
geçmiş bir "Goes stale" ayı, BOM/CRLF. Sorunlar doğrudan Claude'a döner ve Claude sayfayı aynı turda
düzeltir. `raw/`, `notes/`, sistem dosyaları ve `author: me` notları atlanır. Validator kendi
hatalarında hiçbir şeyi engellemez.

Python 3 bulunamazsa iki hook da bir uyarı yazar ve devre dışı kalır.

## Teşekkür

- Andrej Karpathy — [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  fikri: ham kaynaklar, LLM'in sürdürdüğü bir wiki ve bir şema dosyası; ingest, query ve lint.
- AgriciDaniel'in [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) projesi
  (MIT) — index'ten önce okunan oturum hot cache'i, taslak döndüren salt-okur yardımcılar ve zayıf
  ya da çelişen kanıtı görünür tutma fikirleri.

Yalnızca fikirler: ikisinden de kod veya metin kopyalanmadı; buradaki kurallar ve script'ler
sıfırdan yazıldı.

## Lisans

[MIT](LICENSE)
