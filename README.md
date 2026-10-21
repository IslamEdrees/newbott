# newbott: بوت تداول أوتوماتيك على Binance مع متابعة كاملة من Telegram

البوت مبني على [Freqtrade](https://www.freqtrade.io)، وهو مشروع مفتوح المصدر ومجرَّب من آلاف المستخدمين.
بيشتغل 24 ساعة على سيرفر: بيشتري ويبيع لوحده، ويبعتلك كل حاجة على Telegram.

> ⚠️ **تحذير مهم:** مفيش بوت بيضمن مكسب. ابدأ بفلوس وهمية (dry-run)، وبعدها بمبلغ صغير تقبل تخسره.

---

## البوت بيعمل إيه

- **الاستراتيجية `ScalpStrategy`** على فريم 5 دقايق:
  - ما بيدخلش لو **BTC نازل** على فريم الساعة، لأن السوق كله بيقع وراه.
  - ما بيدخلش غير في العملات اللي **اتجاهها صاعد** على فريم الساعة.
  - عنده نوعين دخول:
    - `dip`: نزلة مؤقتة في اتجاه صاعد.
    - `momentum`: بداية حركة صعود ومعاها فوليوم عالي.
- **أهداف الربح:** 2% أول نص ساعة، وبعدين 1.5%، وبعدين 1%، وبعد ساعتين 0.6%.
- **Trailing Stop:** لما الربح يعدي 1.2%، البوت بيمشي ورا السعر ويقفل الربح.
- **وقف خسارة 3% متحط فعلياً على Binance.** يعني لو السيرفر وقع، صفقتك متحمية برضه.
- **حماية تلقائية:**
  - 3 وقف خسارة في يوم واحد ← البوت يوقف تداول 6 ساعات.
  - خسارة أكتر من 5% في يوم ← يوقف 12 ساعة.
  - عملة بتخسر على طول ← تتمنع يوم كامل.
- **العملات:** أعلى 25 عملة سيولة مقابل USDT، والفلتر بيستبعد العملات المستقرة والعملات الميتة أو المجنونة.
- **فلوس كل صفقة:** 3 صفقات بالكتير في نفس الوقت، والرصيد بيتقسم عليهم أوتوماتيك.

---

## خطوات التشغيل

### 1) مفتاح Binance API
1. من موقع Binance: **Profile ← API Management ← Create API ← System generated**.
2. فعّل **Enable Reading** و**Enable Spot & Margin Trading** بس.
3. ❌ **أوعى تفعّل Enable Withdrawals.** كده حتى لو المفتاح اتسرق، محدش يقدر يسحب فلوسك.
4. اختار **Restrict access to trusted IPs only** واكتب IP السيرفر.

### 2) بوت Telegram
1. افتح [@BotFather](https://t.me/BotFather)، ابعت `/newbot`، وخد **التوكن**.
2. افتح [@userinfobot](https://t.me/userinfobot) وخد **رقم الـ ID** بتاعك.
3. افتح البوت الجديد بتاعك ودوس **Start**.

### 3) السيرفر
اعمل سيرفر Ubuntu صغير (1GB RAM كفاية)، من Hetzner أو Contabo أو DigitalOcean مثلاً، وتكلفته حوالي 5 دولار في الشهر.

> 💡 اختار سيرفر في **أوروبا أو آسيا**. سيرفرات أمريكا ممنوعة من Binance.com.

```bash
git clone https://github.com/IslamEdrees/newbott.git
cd newbott
./scripts/setup_server.sh      # يثبت Docker ويجهز ملف .env
nano .env                      # اكتب مفاتيح Binance و Telegram
```

### 4) اختبار على بيانات قديمة (Backtest)
```bash
./scripts/backtest.sh               # آخر سنة
./scripts/backtest.sh 20250101-     # من تاريخ معين
```
بص على `Total profit %` و`Win %` و`Max Drawdown`. لو النتيجة خسرانة، **ما تشغلوش بفلوس حقيقية**.

### 5) تشغيل بفلوس وهمية (Dry-run)، أسبوعين على الأقل
```bash
docker compose up -d
```
هتوصلك رسالة على Telegram إن البوت اشتغل. تابع أداءه من هناك.

### 6) التحويل لفلوس حقيقية
في ملف `.env` غيّر السطرين دول:
```
FREQTRADE__DRY_RUN=false
DB_FILE=tradesv3.sqlite
```
وبعدين شغّل:
```bash
docker compose up -d
```

---

## أوامر Telegram

| الأمر | بيعمل إيه |
|---|---|
| `/status` | الصفقات المفتوحة دلوقتي |
| `/profit` | إجمالي الأرباح والخسائر |
| `/daily` | الربح يوم بيوم |
| `/balance` | رصيدك |
| `/performance` | أداء كل عملة |
| `/start` / `/stop` | تشغيل التداول / إيقافه |
| `/stopentry` | يبطّل يفتح صفقات جديدة، ويكمّل الصفقات المفتوحة لحد ما تقفل |
| `/forceexit <id>` أو `/forceexit all` | بيع فوري لصفقة معينة أو لكل الصفقات |
| `/forcebuy BTC/USDT` | شرا يدوي |
| `/help` | كل الأوامر |

## أوامر السيرفر

```bash
docker compose logs -f          # تشوف البوت بيعمل إيه دلوقتي
docker compose restart          # إعادة تشغيل
docker compose down             # إيقاف
git pull && docker compose up -d   # تحديث
```

**واجهة الويب (رسوم بيانية وإحصائيات):** من جهازك شغّل
`ssh -L 8080:localhost:8080 user@SERVER_IP`
وافتح `http://localhost:8080`. اسم المستخدم `admin`، والباسورد هتلاقيه في `.env`.

---

## تعديل الإعدادات

- **عدد الصفقات في نفس الوقت:** `max_open_trades` في `user_data/config.json`.
- **الأهداف ووقف الخسارة:** `minimal_roi` و`stoploss` في `user_data/strategies/ScalpStrategy.py`.
- **تحسين الاستراتيجية أوتوماتيك (Hyperopt):**
  ```bash
  docker compose run --rm freqtrade hyperopt \
    --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config-backtest.json \
    --strategy ScalpStrategy --hyperopt-loss SharpeHyperOptLoss --spaces buy sell -e 300
  ```
