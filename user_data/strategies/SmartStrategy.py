# pragma pylint: disable=missing-docstring, invalid-name
"""
SmartStrategy - نسخة ذكية متكيفة من ScalpStrategy (فريم 5 دقايق)

1) قراءة حالة السوق (Regime):
   - BTC لازم يكون سليم (فوق EMA50 ساعة، ومفيش انهيار في آخر ساعة).
   - العملة نفسها: ترند صاعد (ADX عالي) ولا سوق عرضي (ADX واطي)، والتذبذب المجنون ممنوع.
2) نظام نقاط (Score): كل إشارة بتاخد نقط، والدخول للفرص اللي درجتها عالية بس.
   - trend: ارتداد من EMA21 جوه ترند صاعد.
   - range: نزلة تحت Bollinger السفلي في سوق عرضي مع شمعة تأكيد.
3) حجم الصفقة متغير: فرصة قوية = حجم كامل، فرصة متوسطة = حجم أقل،
   وعملة خسرانة مؤخراً = نص الحجم.
4) التعلم من النتايج: لو نسبة الكسب في آخر الصفقات وقعت، البوت بيقبل
   الفرص الأقوى بس لحد ما الأداء يتحسن.
5) وقف خسارة ذكي: على حسب ATR (من 1.2% لـ 2.5%)، وبيتنقل لنقطة التعادل
   بعد +1.3%، وبعدين بيقفل الربح خطوة بخطوة.
"""

from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.enums import RunMode
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
    IStrategy,
    informative,
    stoploss_from_open,
)


class SmartStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 200

    # شبكة أمان فقط - الخروج الأساسي من custom_stoploss و custom_exit
    minimal_roi = {
        "0": 0.04,
        "60": 0.025,
        "180": 0.012,
        "360": 0.006,
    }

    # أقصى خسارة مطلقة (الوقف الفعلي بيتحسب في custom_stoploss)
    stoploss = -0.04
    use_custom_stoploss = True
    trailing_stop = False

    use_exit_signal = True
    exit_profit_only = False

    # ---- باراميترات قابلة للتحسين بـ hyperopt ----
    trend_min_score = IntParameter(4, 7, default=6, space="buy")
    range_min_score = IntParameter(3, 6, default=4, space="buy")
    range_rsi = IntParameter(22, 38, default=32, space="buy")
    trend_adx = IntParameter(18, 30, default=22, space="buy")
    atr_sl_mult = DecimalParameter(1.5, 3.0, default=2.2, decimals=1, space="sell")
    exit_rsi = IntParameter(70, 85, default=78, space="sell")

    # ---- إعدادات التعلم من النتايج ----
    learn_window = 12          # عدد آخر الصفقات المقفولة اللي بنتعلم منها
    learn_min_winrate = 0.45   # لو نسبة الكسب أقل من كده => نقبل الفرص القوية بس
    pair_window = 5            # آخر صفقات العملة نفسها
    pair_min_winrate = 0.4

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 6},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 288,
                "trade_limit": 3,
                "stop_duration_candles": 72,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 4,
                "stop_duration_candles": 144,
                "max_allowed_drawdown": 0.05,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 576,
                "trade_limit": 3,
                "stop_duration_candles": 288,
                "required_profit": -0.01,
            },
        ]

    # ================= فريم الساعة =================
    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    @informative("1h", "BTC/{stake}", "btc_{column}_{timeframe}")
    def populate_indicators_btc_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["chg"] = dataframe["close"].pct_change()
        return dataframe

    # ================= فريم 5 دقايق =================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe)
        dataframe["macdhist"] = macd["macdhist"]

        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_mid"] = bb["mid"]
        dataframe["bb_upper"] = bb["upper"]

        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["volume"].rolling(30).mean()

        # ---- حالة السوق ----
        dataframe["market_ok"] = (
            (dataframe["btc_close_1h"] > dataframe["btc_ema50_1h"])
            & (dataframe["btc_rsi_1h"] > 42)
            & (dataframe["btc_chg_1h"] > -0.015)
        )
        dataframe["calm"] = dataframe["atr_pct"].between(0.002, 0.025) & (dataframe["volume"] > 0)
        dataframe["regime_trend"] = (
            (dataframe["close_1h"] > dataframe["ema50_1h"])
            & (dataframe["adx_1h"] > 20)
            & (dataframe["adx"] > self.trend_adx.value)
            & (dataframe["plus_di"] > dataframe["minus_di"])
        )
        dataframe["regime_range"] = (dataframe["adx"] < 20) & (
            dataframe["close_1h"] > dataframe["ema50_1h"] * 0.98
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        base = d["market_ok"] & d["calm"]

        # ---- ترند: ارتداد من EMA21 ----
        bounce = (d["low"] <= d["ema21"] * 1.002) & (d["close"] > d["ema21"]) & (d["close"] > d["open"])
        trend_score = (
            (d["close"] > d["ema200"]).astype(int)
            + (d["ema9"] > d["ema21"]).astype(int) * 2
            + d["rsi"].between(40, 62).astype(int)
            + (d["macdhist"] > d["macdhist"].shift(1)).astype(int)
            + (d["vol_ratio"] > 1.2).astype(int)
            + (d["mfi"] < 70).astype(int)
        )
        trend_ok = base & d["regime_trend"] & bounce & (trend_score >= self.trend_min_score.value)

        # ---- عرضي: نزلة تحت Bollinger مع شمعة تأكيد ----
        dip = d["low"] < d["bb_lower"]
        range_score = (
            (d["rsi"] < self.range_rsi.value).astype(int)
            + (d["rsi"] < self.range_rsi.value - 7).astype(int)
            + (d["mfi"] < 25).astype(int)
            + (d["vol_ratio"] > 1.0).astype(int)
            + (d["close"] > d["open"]).astype(int)
            + (d["close"] > d["bb_lower"]).astype(int)
        )
        range_ok = base & d["regime_range"] & dip & (range_score >= self.range_min_score.value)

        d.loc[range_ok, "enter_long"] = 1
        d.loc[range_ok, "enter_tag"] = "range_" + range_score[range_ok].astype(str)
        d.loc[trend_ok, "enter_long"] = 1
        d.loc[trend_ok, "enter_tag"] = "trend_" + trend_score[trend_ok].astype(str)
        return d

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > self.exit_rsi.value) & (dataframe["close"] > dataframe["bb_upper"]),
            ["exit_long", "exit_tag"],
        ] = (1, "overbought")
        return dataframe

    # ================= التعلم من النتايج =================
    def _winrate(self, pair: str | None, window: int) -> tuple[float, int]:
        trades = Trade.get_trades_proxy(pair=pair, is_open=False)
        trades = sorted(trades, key=lambda t: t.close_date_utc)[-window:]
        if not trades:
            return 1.0, 0
        wins = sum(1 for t in trades if (t.close_profit or 0) > 0)
        return wins / len(trades), len(trades)

    @staticmethod
    def _tag_score(tag: str | None) -> tuple[str, int]:
        if not tag or "_" not in tag:
            return "", 0
        mode, _, score = tag.partition("_")
        return mode, int(score) if score.isdigit() else 0

    def _is_strong(self, tag: str | None) -> bool:
        mode, score = self._tag_score(tag)
        if mode == "trend":
            return score >= 7
        if mode == "range":
            return score >= 5
        return False

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if not dataframe.empty:
            # ما نطاردش السعر لو طار بعد الإشارة
            if rate > dataframe["close"].iloc[-1] * 1.004:
                return False

        # لو الأداء العام وحش، نقبل الفرص القوية بس
        winrate, n = self._winrate(None, self.learn_window)
        if n >= 6 and winrate < self.learn_min_winrate and not self._is_strong(entry_tag):
            return False

        # فحص السبريد في التداول الحقيقي
        if self.dp.runmode in (RunMode.LIVE, RunMode.DRY_RUN):
            ob = self.dp.orderbook(pair, 1)
            if ob["bids"] and ob["asks"]:
                spread = (ob["asks"][0][0] - ob["bids"][0][0]) / ob["asks"][0][0]
                if spread > 0.002:
                    return False
        return True

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        mult = 1.0 if self._is_strong(entry_tag) else 0.7
        pair_winrate, n = self._winrate(pair, self.pair_window)
        if n >= 3 and pair_winrate < self.pair_min_winrate:
            mult *= 0.5
        stake = min(proposed_stake * mult, max_stake)
        if min_stake and stake < min_stake:
            # ما نكبرش الصفقة عشان نوصل للحد الأدنى إلا لو المتاح يسمح
            return min_stake if min_stake <= max_stake else 0
        return stake

    # ================= وقف الخسارة الذكي =================
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        # قفل الأرباح خطوة بخطوة
        # (كل مستوى أعلى من العمولة ~0.2% بوضوح، عشان المكسب ما يتاكلش)
        if current_profit > 0.03:
            return stoploss_from_open(current_profit - 0.01, current_profit)
        if current_profit > 0.02:
            return stoploss_from_open(0.01, current_profit)
        if current_profit > 0.013:
            return stoploss_from_open(0.005, current_profit)

        # الوقف المبدئي على حسب تذبذب العملة
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        atr_pct = float(dataframe["atr_pct"].iloc[-1])
        if np.isnan(atr_pct):
            return None
        sl = min(max(atr_pct * self.atr_sl_mult.value, 0.012), 0.025)
        return stoploss_from_open(-sl, current_profit)

    # ================= خروج ذكي =================
    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        last = dataframe.iloc[-1]
        prev = dataframe.iloc[-2]
        mode, _ = self._tag_score(trade.enter_tag)

        # السوق العام قلب => خد المكسب الصغير ومتستناش
        if not last["market_ok"] and current_profit > 0.003:
            return "market_turned"

        # صفقة العرضي: الهدف هو رجوع السعر للمنتصف
        if mode == "range" and current_rate >= last["bb_mid"] and current_profit > 0.005:
            return "mean_reached"

        # الزخم بيضعف بعد هدف محترم
        target = min(max(float(last["atr_pct"]) * 2.0, 0.008), 0.03)
        if (
            current_profit > target
            and last["macdhist"] < prev["macdhist"]
            and last["rsi"] > 60
        ):
            return "momentum_fading"

        # صفقة واقفة كتير => حرر الفلوس
        hours = (current_time - trade.open_date_utc).total_seconds() / 3600
        if hours > 6 and current_profit > -0.005:
            return "stale_trade"
        return None
