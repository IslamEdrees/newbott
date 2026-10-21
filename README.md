# newbott: بوت تداول أوتوماتيك على Binance مع متابعة كاملة من Telegram

البوت مبني على [Freqtrade](https://www.freqtrade.io)، وهو مشروع مفتوح المصدر ومجرَّب من آلاف المستخدمين.
بيشتغل 24 ساعة على سيرفر: بيشتري ويبيع لوحده، ويبعتلك كل حاجة على Telegram.

> ⚠️ **تحذير مهم:** مفيش بوت بيضمن مكسب. ابدأ بفلوس وهمية (dry-run)، وبعدها بمبلغ صغير تقبل تخسره.

---

## البوت بيعمل إيه

الاستراتيجية الأساسية هي **`SmartStrategy`**، وهي نسخة ذكية بتتكيف مع السوق، على فريم 5 دقايق:

- **بتقرا حالة السوق قبل أي صفقة:**
  - ما بتدخلش لو **BTC نازل**، أو لو وقع أكتر من 1.5% في آخر ساعة.
  - بتعرف العملة في **ترند صاعد** ولا في **سوق عرضي**، وبتدخل بطريقة مختلفة في كل حالة.
  - بتبعد عن العملات اللي تذبذبها مجنون.
- **بتدّي كل فرصة درجة (Score)**، وما بتدخلش غير الفرص اللي درجتها عالية.
- **حجم الصفقة على حسب قوة الفرصة:**
  - فرصة قوية: حجم كامل.
  - فرصة عادية: 70% من الحجم.
  - عملة خسّرتك مؤخراً: نص الحجم.
- **بتتعلم من نتايجها:** لو نسبة الكسب في آخر 12 صفقة نزلت تحت 45%، بتقبل الفرص القوية بس لحد ما الأداء يتحسن.
- **وقف خسارة ذكي:**
  - بيتحسب على حسب تذبذب العملة، من 1.2% لـ 2.5%.
  - بعد +1.3% بيتنقل لربح مضمون، وبعدين بيقفل الربح خطوة بخطوة.
  - **متحط فعلياً على Binance**، فلو السيرفر وقع صفقتك متحمية.
- **خروج ذكي:**
  - لو السوق قلب، بتاخد المكسب وتخرج.
  - لو الزخم ضعف بعد هدف محترم، بتخرج.
  - صفقة العرضي بتقفل لما السعر يرجع للمنتصف.
- **حماية تلقائية:**
  - 3 وقف خسارة في يوم ← البوت يوقف 6 ساعات.
  - خسارة 5% في يوم ← يوقف 12 ساعة.
- **حد أقصى للفلوس:** البوت مش بيلمس أكتر من المبلغ اللي إنت حددته.

> النسخة الأبسط `ScalpStrategy` موجودة كمان. عشان تستخدمها، ضيف `STRATEGY=ScalpStrategy` في ملف `.env`.

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
- **الأهداف ووقف الخسارة:** `custom_stoploss` و`custom_exit` في `user_data/strategies/SmartStrategy.py`.
- **تحسين الاستراتيجية أوتوماتيك (Hyperopt):**
  ```bash
  docker compose run --rm freqtrade hyperopt \
    --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config-backtest.json \
    --strategy SmartStrategy --hyperopt-loss SharpeHyperOptLoss --spaces buy sell -e 300
  ```
