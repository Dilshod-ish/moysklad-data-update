# moysklad-data-update

MoySklad'dagi bitta bazani (hisobni) boshqa, yangi ochilgan bazaga MoySklad
JSON API orqali ko'chirish uchun skript.

## Nima ko'chiriladi

**Spravochniklar:**
- Birliklar (uom), valyutalar (currency)
- Narx turlari (pricetype), pul mablag'lari harakati moddalari (expenditem) —
  nomi bo'yicha moslashtiriladi
- Bo'limlar (group/Отдел), xodimlar (employee)
- Tashkilotlar / yuridik shaxslar (organization), ularning bank hisoblari
- Tovar guruhlari (productfolder), ierarxiyasi (ota-guruh) bilan birga
- Sklad (store)
- Kontragentlar (counterparty), ularning bank hisoblari
- Loyihalar (project), shartnomalar (contract)
- Tovarlar, xizmatlar, modifikatsiyalar, komplektlar (product, service,
  variant, bundle)
- Custom fieldlar (dopolnitelnie polya), shu jumladan "customentity" turidagi
  (foydalanuvchi lug'ati) custom fieldlar va ularning qiymatlari. Agar manba
  bazada lug'atning o'zi (masalan o'chirilgan bo'lgani uchun) havolasi
  buzilgan bo'lsa ham, skript qiymatning ko'rinadigan nomi orqali maqsad
  bazada mos lug'at/elementni topadi yoki yaratadi — shunday qilib qiymat
  yo'qolmaydi.

**Hujjatlar** (xronologik tartibda, holatlari — status — bilan birga):
- Oприходование (enter), Списание (loss), Перемещение (move), Инвентаризация
  (inventory)
- Технологическая карта (processingplan), Заказ на производство
  (processingorder), Texoperatsiya / Производство (processing)
- Заказ поставщику (purchaseorder), Приемка (supply), Возврат поставщику
  (purchasereturn)
- Заказ покупателя (customerorder), Отгрузка (demand), Возврат покупателя
  (salesreturn)
- Счет поставщика (invoicein), Счет покупателю (invoiceout)
- Входящий/исходящий платежи (paymentin, paymentout), ПКО/РКО (cashin,
  cashout) — bog'liq bank hisoblari va boshqa hujjatlarga havolalari bilan

Tovar qoldiqlari (stock) alohida "sozlanmaydi" — ular yuqoridagi qoldiqqa
ta'sir qiluvchi hujjatlar (enter, loss, move, inventory, processing, supply,
demand, qaytarishlar) to'liq ko'chirilgani natijasida maqsad bazada
avtomatik hisoblanadi.

## Nima ko'chirilmaydi (cheklovlar)

- **Fayllar va rasmlar** — binar fayllarni qayta yuklashni talab qiladi,
  siz so'ragan doirada ataylab chetlab o'tilgan.
- **Xodimlar login/paroli** — xavfsizlik sabab API orqali parol
  o'rnatib bo'lmaydi; xodim ma'lumotlari (ism, lavozim, aloqa) ko'chiriladi,
  lekin tizimga kirish uchun ularni yangi bazada qayta taklif qilish (invite)
  kerak bo'ladi.
- Chakana savdo hujjatlari (retaildemand, retailsalesreturn va h.k. —
  do'kon/kassa POS ulanishiga bog'liq), komissiya hisobotlari
  (commissionreportin/out), ichki buyurtma (internalorder) — kamdan-kam
  ishlatiladigan turlar, hozircha kiritilmagan (kerak bo'lsa qo'shish mumkin).
- "file" turidagi custom fieldlar (qiymati fayl bo'lgani uchun).

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` faylini oching va ikkala baza uchun API token (yoki login/parol)
kiriting:

```
SOURCE_TOKEN=...   # eski (hozir ishlatilayotgan) baza
DEST_TOKEN=...     # yangi ochilgan baza
```

API token MoySklad'da: **Sozlamalar → API va integratsiyalar → Tokenlar
uchun kirish** bo'limidan olinadi.

## Ishga tushirish

Avval tekshirish uchun (hech narsa yozmaydi, faqat qancha element
ko'chirilishini ko'rsatadi):

```bash
python main.py --dry-run
```

Haqiqiy migratsiya:

```bash
python main.py
```

Faqat ma'lum turlarni ko'chirish kerak bo'lsa:

```bash
python main.py --only product,service,variant
python main.py --only demand,supply,paymentin,paymentout
```

Ilgari ko'chirilgan elementlarni ham qayta tekshirib, manba bazadagidan
farq qilsa (masalan, kod yangilangandan keyin ba'zi hujjatlar noto'g'ri
qiymat bilan yaratilgan bo'lsa) — maqsad bazadagisini yangilash:

```bash
python main.py --update-existing
python main.py --update-existing --only cashin,cashout,paymentin,paymentout
```

Bu rejim har bir allaqachon mavjud elementni qayta hisoblab, maqsad
bazadagisi bilan solishtiradi va farq bo'lsagina yangilaydi (`PUT`) —
shuning uchun oddiy ishga tushirishga qaraganda sekinroq ishlaydi
(hujjatlar uchun ularning pozitsiyalari qayta so'raladi).

## Muhim eslatmalar

- Hujjatlar ko'p bo'lsa (minglab), migratsiya biroz vaqt oladi — har bir
  hujjat uchun uning pozitsiyalari (positions) alohida so'rov bilan olinadi,
  bu MoySklad API'ning cheklovi (positions to'liq holda ro'yxat so'rovida
  qaytmaydi).
- Skript MoySklad'ning rate limit'iga (taxminan 45 so'rov/3 soniya) duch
  kelsa, avtomatik kutib, qayta urinadi — buni to'xtatish shart emas.
- Katta bazalarda avval `--only` bilan kichik bir turni sinab ko'rish
  tavsiya etiladi (masalan `--only uom,currency,store`), keyin to'liq
  migratsiyaga o'tish.
- Yangi MoySklad akkaunti ba'zi standart elementlarni (birlik "шт", "Основной
  склад" ombori, "Основной" bo'limi va h.k.) oldindan o'zi yaratib qo'yadi.
  Skript `uom`, `currency`, `group`, `store`, `expenditem` turlari uchun
  bunday nomdosh elementlarni avtomatik aniqlab, ularni qayta yaratmasdan
  mavjudiga bog'laydi.
- Maqsad bazaning hisob (учётная) valyutasi uchun hujjatlardagi kurs (rate)
  har doim 1 bo'lishi shart — skript shu holatni avtomatik aniqlab, kerak
  bo'lsa "rate" maydonini olib tashlaydi.
- Valyutalar (currency) spravochnigi ko'chirilganda ham xuddi shunday: faqat
  manba bazaning O'ZINING hisob (учётная) valyutasi uchun "rate" olib
  tashlanadi (chunki maqsad bazada ham u hisob valyutasi bo'lib qoladi va
  kursi majburiy 1). Boshqa (chet el) valyutalarning kursi esa to'liq
  saqlanadi — shu orqali `currency.rate` maydoniga tayanadigan hisobot
  skriptlari to'g'ri ishlashda davom etadi.

## Qayta ishga tushirish (idempotentlik)

Skript har bir elementga manba bazadagi ID'ni `externalCode` sifatida
yozadi. Shu orqali skriptni bir necha marta ishga tushirish xavfsiz —
allaqachon ko'chirilgan elementlar qayta yaratilmaydi, faqat qolganlari
qo'shiladi. Bu internet uzilishi yoki xatolik bo'lgan taqdirda qayta
davom ettirish imkonini beradi.

## GitHub Actions orqali ishga tushirish

Skriptni o'z kompyuteringizda emas, GitHub'ning serverida ishga tushirish
uchun `.github/workflows/migrate.yml` workflow qo'shilgan. U qo'lda
(**Actions** bo'limidan) ishga tushiriladi — avtomatik jadval bo'yicha emas,
chunki migratsiya odatda bir martalik amal.

**Sozlash (bir marta):**

1. Repozitoriyada **Settings → Secrets and variables → Actions → New
   repository secret** bo'limiga kirib, quyidagi secret'larni qo'shing:
   - `SOURCE_TOKEN` — eski (hozir ishlatilayotgan) baza API tokeni
   - `DEST_TOKEN` — yangi baza API tokeni
   - (token o'rniga login/parol ishlatmoqchi bo'lsangiz: `SOURCE_LOGIN`,
     `SOURCE_PASSWORD`, `DEST_LOGIN`, `DEST_PASSWORD`)

**Ishga tushirish:**

1. GitHub'da repozitoriyaning **Actions** bo'limiga kiring.
2. Chap tomondan **"MoySklad migratsiya"** workflow'ini tanlang.
3. **"Run workflow"** tugmasini bosing.
4. Avval `dry_run = true` bilan ishga tushirib, loglarda nechta element
   ko'chirilishini tekshiring. Keyin `dry_run = false` qilib, haqiqiy
   migratsiyani boshlang.
5. Xohlasangiz, `only` maydoniga vergul bilan ajratilgan turlarni yozib,
   faqat ularni ko'chirishingiz mumkin (masalan `uom,currency,store`).

Ishlash jarayoni va xatoliklar workflow ishga tushgan sahifadagi loglarda
ko'rinadi.

## Hujjatlar vaqtini xronologik tartiblash (`reschedule.py`)

Ko'chirishdan keyin bir kunda bir nechta turdagi hujjat bo'lsa (masalan
o'sha kuni ham приемка, ham отгрузка), ularning **soati** manba
bazadagi tasodifiy/original vaqtda qolishi mumkin — bu esa MoySklad'da
qoldiq hisobini kunning ichida vaqtinchalik noto'g'ri ko'rsatishi mumkin
(masalan tovar "kelishi"dan oldin "chiqib ketgandek" ko'rinishi). Bu
skript **sanani saqlab**, faqat soatni hujjat turiga qarab quyidagi
jadval bo'yicha to'g'irlaydi (yangi — DEST — bazada):

| Vaqt | Hujjat turi |
|---|---|
| 06:00 | inventory (Инвентаризация) |
| 06:30 | enter (Оприходование) |
| 07:00 | purchaseorder |
| 07:30 | supply (Приемка) |
| 07:45 | invoicein |
| 08:00 | purchasereturn |
| 08:15 | move (Перемещение) |
| 08:30 | processingplan / processingorder / processing |
| 09:00 | customerorder |
| 10:00 | paymentin / cashin |
| 13:00 | loss (Списание) |
| 18:00 | demand (Отгрузка) |
| 18:15 | invoiceout |
| 18:30 | salesreturn |
| 20:00 | paymentout / cashout |

Barcha vaqtlar 06:00–21:00 oralig'ida.

Bir kunda bir xil turdagi bir nechta hujjat bo'lsa, ularning barchasi
o'sha turning jadvaldagi vaqtiga o'tkaziladi (masalan barcha o'sha
kungi `supply`lar 08:00ga).

Ishga tushirish:

```bash
python reschedule.py --dry-run          # avval tekshirish
python reschedule.py                    # haqiqiy tuzatish
python reschedule.py --only supply,demand   # faqat ma'lum turlar
```

Yoki GitHub Actions'dan: **Actions → "Hujjatlar vaqtini tartiblash" →
Run workflow**. Bu faqat DEST (yangi) bazaga yozadi, manba bazaga
tegmaydi.

## Ikkalasini birga: migratsiya + vaqtni tartiblash (`migrate-and-reschedule.yml`)

Yuqoridagi ikkita workflow'ni ("MoySklad migratsiya" va "Hujjatlar
vaqtini tartiblash") qo'lda birin-ketin ishga tushirish o'rniga, bitta
workflow orqali ham qilish mumkin: **Actions → "MoySklad migratsiya +
vaqtni tartiblash" → Run workflow**. U avval eski bazadan hujjatlarni
o'qib yangi bazaga ko'chiradi (1-bosqich, `main.py`), so'ng — muvaffaqiyatli
tugasa — darhol o'sha yangi bazadagi hujjatlarning vaqtini xronologik
jadval bo'yicha to'g'irlaydi (2-bosqich, `reschedule.py`).

Maydonlar:
- `dry_run` — ikkala bosqich uchun ham amal qiladi.
- `only` — 1-bosqich (migratsiya) uchun turlarni cheklaydi.
- `update_existing` — 1-bosqich uchun, ilgari ko'chirilganlarni ham tekshirish.
- `run_reschedule` — 2-bosqichni butunlay o'chirib qo'yish uchun (`false`
  qilsangiz, faqat migratsiya bajariladi).
- `reschedule_only` — 2-bosqich (vaqtni tartiblash) uchun hujjat turlarini
  cheklaydi, `only`dan mustaqil.

Agar 1-bosqich (migratsiya) xatolik bilan to'xtasa, 2-bosqich (vaqtni
tartiblash) avtomatik ishga tushmaydi — GitHub Actions'ning odatiy
xatti-harakati shunday (oldingi qadam muvaffaqiyatsiz bo'lsa, keyingisi
o'tkazib yuboriladi).
