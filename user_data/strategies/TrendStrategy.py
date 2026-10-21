# pragma pylint: disable=missing-docstring, invalid-name
"""
TrendStrategy - امشي مع الترند الكبير وسيب المكسب يكبر (فريم ساعة)

الدرس من الـ backtests الحقيقية: السوق طلع ~50% في 90 يوم، وكل استراتيجيات
المضاربة السريعة خسرت بسبب وقف الخسارة القريب. هنا العكس:
  - ندخل بس لما الاتجاه صاعد على اليومي و 4 ساعات، و BTC كمان صاعد.
  - الدخول على كسر أعلى سعر في آخر 48 ساعة، أو تقاطع EMA20 فوق EMA50 على الساعة.
  - ما فيش هدف ربح ثابت: بنفضل في الصفقة لحد ما الترند على 4 ساعات يتكسر.
  - وقف خسارة واسع (3 × ATR، من 4% لـ 8%)، وبعد +6% بنقفل جزء من الربح.
"""

from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_open


class TrendStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 600

    # من غير هدف ثابت - الخروج من كسر الترند أو الوقف
    minimal_roi = {"0": 10}

    stoploss = -0.08
    use_custom_stoploss = True
    trailing_stop = False
    use_exit_signal = True

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 6},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 72,
                "trade_limit": 3,
                "stop_duration_candles": 48,
                "only_per_pair": False,
            },
        ]

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    @informative("4h", "BTC/{stake}", "btc_{column}_{timeframe}")
    def populate_indicators_btc_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        dataframe["high48"] = dataframe["high"].rolling(48).max().shift(1)
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["volume"].rolling(24).mean()

        dataframe["big_trend"] = (
            (dataframe["close_1d"] > dataframe["ema20_1d"])
            & (dataframe["close_4h"] > dataframe["ema50_4h"])
            & (dataframe["btc_close_4h"] > dataframe["btc_ema50_4h"])
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        base = d["big_trend"] & (d["rsi"] < 75) & (d["volume"] > 0)

        breakout = (d["close"] > d["high48"]) & (d["vol_ratio"] > 1.2)
        d.loc[base & breakout, ["enter_long", "enter_tag"]] = (1, "breakout")

        cross = qtpylib.crossed_above(d["ema20"], d["ema50"])
        d.loc[base & cross & (d["enter_long"] != 1), ["enter_long", "enter_tag"]] = (1, "ema_cross")
        return d

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # الترند على 4 ساعات اتكسر
        dataframe.loc[
            dataframe["close_4h"] < dataframe["ema50_4h"], ["exit_long", "exit_tag"]
        ] = (1, "trend_end")
        return dataframe

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
        if current_profit > 0.15:
            return stoploss_from_open(current_profit - 0.06, current_profit)
        if current_profit > 0.06:
            return stoploss_from_open(current_profit - 0.04, current_profit)

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        atr_pct = float(dataframe["atr_pct"].iloc[-1])
        if np.isnan(atr_pct):
            return None
        sl = min(max(atr_pct * 3, 0.04), 0.08)
        return stoploss_from_open(-sl, current_profit)
