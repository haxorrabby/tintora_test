# Tintora-এর ফ্রি Client Demo Deploy (Render + Neon)

এই পদ্ধতি client-কে ওয়েবসাইট দেখানোর জন্য। Free hosting-এ cold start, quota ও
অস্থায়ী file storage আছে—এটিকে live shop, customer upload বা real payment-এর
জন্য ব্যবহার করবেন না।

## কী লাগবে

- GitHub account ও এই project-এর একটি private repository
- Render account: [render.com](https://render.com)
- Neon account: [neon.com](https://neon.com)

## ১. GitHub-এ project upload

VS Code-এর **Source Control** থেকে পরিবর্তনগুলো দেখে commit করে private GitHub
repository-তে push করুন। `.env`, `db.sqlite3`, `media/invoices/` বা customer
data commit করবেন না। `.dockerignore` public `media/catalog/` photos image-এ
রাখে, আর `.gitignore`-ও শুধু public catalog photos-কে upload-এর জন্য visible
করে। Source Control-এ ওই photos-সহ changes review/stage করুন; invoice ও অন্য
private media যেন commit না হয়।

## ২. Free PostgreSQL database বানান

Neon-এ Free project তৈরি করে connection string নিন (pooled connection string
ব্যবহার করা ভালো)। URL-টি secret হিসেবে রাখুন; GitHub-এ লিখবেন না।

## ৩. Render Web Service তৈরি

1. Render Dashboard → **New** → **Web Service** → GitHub repository connect করুন।
2. Runtime হিসেবে **Docker** নির্বাচন করুন, root directory ফাঁকা রাখুন, instance
   plan **Free** দিন।
3. Health Check Path হিসেবে `/healthz/` দিন।
4. **Advanced → Docker Command** ফাঁকা রাখুন, যাতে Dockerfile-এর command চলে।
   `deploy/render-start.sh` startup-এ PostgreSQL ও host configuration যাচাই
   করে, migration চালায়, খালি database-এ public catalog একবার import করে,
   static files collect করে, তারপর Render-এর `PORT`-এ Gunicorn চালায়।

5. Environment Variables-এ যোগ করুন:

   | Key | Value |
   | --- | --- |
   | `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
   | `DEBUG` | `False` |
   | `SECRET_KEY` | নিচের command দিয়ে তৈরি করা নতুন, random secret |
   | `TOTP_ENCRYPTION_KEY` | নিচের command দিয়ে তৈরি করা আলাদা Fernet key |
   | `ALLOWED_HOSTS` | Render-এর service domain, যেমন `tintora-demo.onrender.com` |
   | `DATABASE_URL` | Neon-এর PostgreSQL connection string |
   | `SECURE_SSL_REDIRECT` | `True` |

   Key তৈরি করতে project root-এ PowerShell চালান:

   ```powershell
   .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   দুই key-ই নিরাপদ password manager-এ রাখুন। Render-এর Environment settings-এ
   value দিন; source file বা GitHub-এ নয়।

6. **Create Web Service** চাপুন। প্রথম build শেষ হলে service URL-এ `/es/` খুলে
   দেখুন। `/healthz/`-এ `200` এলে app চালু।

## ৪. Client-কে দেখানোর আগে

- Free hosting-এ local filesystem স্থায়ী নয়। Admin থেকে নতুন upload করা ছবি,
  artwork, invoice PDF বা SQLite data restart/redeploy/spin-down-এ হারাতে পারে;
  build-এর সময় থাকা `media/catalog/` product photos থাকবে। `.env`
  ফাইলে `USE_S3=True` দিয়ে private object storage সংযোগ না করা পর্যন্ত production
  customer file upload করবেন না।
- Render Free service 15 মিনিট request না পেলে sleep করে; পরের request-এ
  প্রায় এক মিনিট cold start হতে পারে। Neon Free database quota ও storage সীমিত।
- `seed_data` command চালাবেন না: এটি sample catalog ও demo account তৈরি করে;
  demo superuser-এর password unusable থাকে। Local database-ও deploy হয় না।
  Client-এর জন্য দরকারি public catalog data আলাদাভাবে review করে import করুন;
  customer/order/account data export করবেন না।
- Free plan-এ Render shell/one-off job নেই। Admin দরকার হলে Neon `DATABASE_URL`
  ব্যবহার করে নিজের কম্পিউটার থেকে superuser তৈরি করুন; production credentials
  কেবল local environment-এ দিন। Admin-এ TOTP চালু থাকবে।
- `STRIPE`/`Redsys` live credentials যোগ করবেন না। Live payment, email delivery,
  order processing, privacy/terms ও backup যাচাই না করে এটিকে public shop হিসেবে
  ঘোষণা করবেন না।

## Free plan-এর বাস্তব সীমা

Render Free web service 15 মিনিট request না পেলে sleep করে এবং local
filesystem ephemeral। Render-এর Free Postgres database 30 দিন পর expire করে।
তাই app Render-এ ও database Neon Free-তে রাখলে নির্দিষ্ট সীমার মধ্যে client
preview দেখানো যায়—দীর্ঘমেয়াদি production-এর জন্য নয়।

বিস্তারিত Render-এর [Free instance limits](https://render.com/docs/free) ও
Neon-এর [pricing / Free plan](https://neon.com/pricing) পাতা থেকে deploy করার
সময় আবার যাচাই করুন; মূল্য ও সীমা বদলাতে পারে।
