# pragma pylint: disable=missing-docstring, invalid-name
"""
ScalpStrategy - سكالبينج على فريم 5 دقايق بأهداف صغيرة (0.6% - 2%)

الفكرة:
  1) فلتر السوق العام: ما ندخلش لو BTC نازل على فريم الساعة.
  2) فلتر اتجاه العملة: ما ندخلش غير لو العملة فوق EMA50 على فريم الساعة.
  3) نوعين دخول:
     - dip:      نزلة مؤقتة (RSI منخفض + السعر تحت Bollinger السفلي) في اتجاه صاعد.
     - momentum: تقاطع EMA9 فوق EMA21 مع فوليوم أعلى من المتوسط.
  4) الخروج: أهداف ROI بتقل مع الوقت + Trailing Stop + وقف خسارة حقيقي على Binance.
  5) حماية: بيوقف التداول لوحده بعد خسائر متتالية أو Drawdown كبير.
"""

from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
    IStrategy,
    Trade,
    informative,
)


class ScalpStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 200

    # أهداف الربح حسب مدة الصفقة بالدقايق.
    # العمولة ~0.2% للصفقة الكاملة، فأقل هدف لازم يكون أعلى منها بوضوح.
    minimal_roi = {
        "0": 0.02,
        "30": 0.015,
        "60": 0.01,
        "120": 0.006,
    }

    # وقف الخسارة (بيتحط فعلياً على Binance عن طريق stoploss_on_exchange).
    stoploss = -0.03

    # بعد ما الربح يوصل 1.2%، نقفل الربح ونمشي ورا السعر بمسافة 0.5%.
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # باراميترات قابلة للتحسين بـ hyperopt
    dip_rsi = IntParameter(20, 40, default=30, space="buy")
    dip_bb_factor = DecimalParameter(0.98, 1.01, default=1.0, decimals=3, space="buy")
    mom_volume_factor = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="buy")
    exit_rsi = IntParameter(65, 85, default=75, space="sell")

    @property
    def protections(self):
        return [
            # استراحة 5 شمعات بعد قفل أي صفقة على نفس العملة
            {"method": "CooldownPeriod", "stop_duration_candles": 5},
            # 3 وقف خسارة في آخر 24 ساعة => وقف كل التداول 6 ساعات
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 288,
                "trade_limit": 3,
                "stop_duration_candles": 72,
                "only_per_pair": False,
            },
            # Drawdown أكتر من 5% في آخر 24 ساعة => وقف التداول 12 ساعة
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 4,
                "stop_duration_candles": 144,
                "max_allowed_drawdown": 0.05,
            },
            # عملة خسرانة باستمرار => تتمنع يوم كامل
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 576,
                "trade_limit": 3,
                "stop_duration_candles": 288,
                "required_profit": -0.01,
            },
        ]

    # ---------------- فريم الساعة ----------------
    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    @informative("1h", "BTC/{stake}", "btc_{column}_{timeframe}")
    def populate_indicators_btc_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    # ---------------- فريم 5 دقايق ----------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_mid"] = bb["mid"]
        dataframe["bb_upper"] = bb["upper"]

        dataframe["volume_mean"] = dataframe["volume"].rolling(30).mean()
        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        market_ok = (dataframe["btc_close_1h"] > dataframe["btc_ema50_1h"]) & (
            dataframe["btc_rsi_1h"] > 45
        )
        trend_ok = dataframe["close_1h"] > dataframe["ema50_1h"]
        # تجنب الشمعات الميتة والتذبذب المجنون
        sane = (dataframe["volume"] > 0) & (dataframe["atr_pct"].between(0.002, 0.03))

        dip = (
            (dataframe["rsi"] < self.dip_rsi.value)
            & (dataframe["close"] < dataframe["bb_lower"] * self.dip_bb_factor.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
        )
        dataframe.loc[market_ok & trend_ok & sane & dip, ["enter_long", "enter_tag"]] = (1, "dip")

        momentum = (
            qtpylib.crossed_above(dataframe["ema9"], dataframe["ema21"])
            & (dataframe["close"] > dataframe["ema200"])
            & (dataframe["rsi"].between(50, 68))
            & (dataframe["volume"] > dataframe["volume_mean"] * self.mom_volume_factor.value)
        )
        dataframe.loc[
            market_ok & trend_ok & sane & momentum & (dataframe["enter_long"] != 1),
            ["enter_long", "enter_tag"],
        ] = (1, "momentum")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > self.exit_rsi.value) & (dataframe["close"] > dataframe["bb_upper"]),
            ["exit_long", "exit_tag"],
        ] = (1, "overbought")
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        # لو BTC قلب نازل والصفقة كسبانة شوية، اخرج بالمكسب بدل ما يضيع.
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        last = dataframe.iloc[-1]
        if last["btc_close_1h"] < last["btc_ema50_1h"] and current_profit > 0.004:
            return "btc_turned_down"
        # صفقة واقفة أكتر من 8 ساعات من غير ما تتحرك => اخرج وحرر الفلوس.
        if (current_time - trade.open_date_utc).total_seconds() > 8 * 3600 and current_profit > -0.005:
            return "stale_trade"
        return None
