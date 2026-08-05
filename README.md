# moysklad-data-update

MoySklad'dagi bitta bazani (hisobni) boshqa, yangi ochilgan bazaga MoySklad
JSON API orqali ko'chirish uchun skript.

## Nima ko'chiriladi

**Spravochniklar:**
- Birliklar (uom), valyutalar (currency)
- Narx turlari (pricetype) — nomi bo'yicha moslashtiriladi
- Bo'limlar (group/Отдел), xodimlar (employee)
- Tashkilotlar / yuridik shaxslar (organization), ularning bank hisoblari
- Tovar guruhlari (productfolder) va kontragent guruhlari (counterpartyfolder),
  ierarxiyasi (ota-guruh) bilan birga
- Sklad (store)
- Kontragentlar (counterparty), ularning bank hisoblari
- Loyihalar (project), shartnomalar (contract)
- Tovarlar, xizmatlar, modifikatsiyalar, komplektlar (product, service,
  variant, bundle)
- Custom fieldlar (dopolnitelnie polya), shu jumladan "customentity" turidagi
  (foydalanuvchi lug'ati) custom fieldlar va ularning qiymatlari

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
