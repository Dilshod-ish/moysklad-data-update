# moysklad-data-update

MoySklad'dagi bitta bazani (hisobni) boshqa, yangi ochilgan bazaga MoySklad
JSON API orqali ko'chirish uchun skript.

## Nima ko'chiriladi

- Birliklar (uom), valyutalar (currency)
- Narx turlari (pricetype) — nomi bo'yicha moslashtiriladi
- Tovar guruhlari (productfolder) va kontragent guruhlari (counterpartyfolder),
  ierarxiyasi (ota-guruh) bilan birga
- Sklad (store)
- Kontragentlar (counterparty)
- Tovarlar, xizmatlar, modifikatsiyalar, komplektlar (product, service,
  variant, bundle)
- Custom fieldlar (dopolnitelnie polya), shu jumladan "customentity" turidagi
  (foydalanuvchi lug'ati) custom fieldlar va ularning qiymatlari

## Nima ko'chirilmaydi (v1 cheklovlari)

- Hujjatlar (sotuv, kirim-chiqim, ko'chirish va h.k.) va tovar qoldiqlari
- Fayllar/rasmlar (binar fayllarni qayta yuklashni talab qiladi)
- Foydalanuvchilar/xodimlar va tashkilot (yuridik shaxs) ma'lumotlari —
  bularni yangi bazada qo'lda sozlash tavsiya etiladi
- "file" turidagi custom fieldlar

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
```

## Qayta ishga tushirish (idempotentlik)

Skript har bir elementga manba bazadagi ID'ni `externalCode` sifatida
yozadi. Shu orqali skriptni bir necha marta ishga tushirish xavfsiz —
allaqachon ko'chirilgan elementlar qayta yaratilmaydi, faqat qolganlari
qo'shiladi. Bu internet uzilishi yoki xatolik bo'lgan taqdirda qayta
davom ettirish imkonini beradi.
