# pragma pylint: disable=missing-docstring, invalid-name
"""
SwingStrategy - صفقات أقل وأقوى على فريم 15 دقيقة

الدرس من الـ backtest الحقيقي لـ SmartStrategy (فريم 5 دقايق):
معظم الخسارة كانت من وقف خسارة ضيق بيضربه تذبذب الدقايق العادي.
النسخة دي:
  - فريم 15 دقيقة، والاتجاه لازم يكون صاعد على الساعة و 4 ساعات.
  - بندخل بس بعد ما التصحيح يخلص (RSI يرجع يطلع فوق 40) جوه الترند.
  - وقف الخسارة أوسع (2.5 × ATR، من 2.5% لـ 5%)، والهدف أكبر (3% لـ 6%).
  - قفل الربح بيبدأ بعد +2.5%.
"""

from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_open


class SwingStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 400

    minimal_roi = {
        "0": 0.06,
        "240": 0.04,
        "720": 0.025,
        "1440": 0.015,
    }

    stoploss = -0.05
    use_custom_stoploss = True
    trailing_stop = False
    use_exit_signal = True

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 48,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 192,
                "trade_limit": 4,
                "stop_duration_candles": 96,
                "max_allowed_drawdown": 0.06,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 384,
                "trade_limit": 2,
                "stop_duration_candles": 192,
                "required_profit": -0.01,
            },
        ]

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    @informative("1h", "BTC/{stake}", "btc_{column}_{timeframe}")
    def populate_indicators_btc_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["chg"] = dataframe["close"].pct_change()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["volume"].rolling(20).mean()
        macd = ta.MACD(dataframe)
        dataframe["macdhist"] = macd["macdhist"]

        dataframe["market_ok"] = (
            (dataframe["btc_close_1h"] > dataframe["btc_ema50_1h"])
            & (dataframe["btc_rsi_1h"] > 45)
            & (dataframe["btc_chg_1h"] > -0.015)
        )
        dataframe["uptrend"] = (
            (dataframe["close_4h"] > dataframe["ema20_4h"])
            & (dataframe["close_1h"] > dataframe["ema50_1h"])
            & (dataframe["ema20_1h"] > dataframe["ema50_1h"])
            & (dataframe["adx_1h"] > 20)
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        # التصحيح خلص: RSI نزل تحت 40 في آخر 8 شمعات ورجع يطلع فوقها
        pullback_done = qtpylib.crossed_above(d["rsi"], 40) & (
            d["rsi"].rolling(8).min() < 38
        )
        d.loc[
            d["market_ok"]
            & d["uptrend"]
            & pullback_done
            & (d["close"] > d["ema50"] * 0.99)
            & (d["macdhist"] > d["macdhist"].shift(1))
            & (d["vol_ratio"] > 0.8)
            & d["atr_pct"].between(0.003, 0.03)
            & (d["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "pullback")
        return d

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["rsi"] > 80, ["exit_long", "exit_tag"]] = (1, "overbought")
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
        if current_profit > 0.05:
            return stoploss_from_open(current_profit - 0.015, current_profit)
        if current_profit > 0.035:
            return stoploss_from_open(0.015, current_profit)
        if current_profit > 0.025:
            return stoploss_from_open(0.008, current_profit)

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        atr_pct = float(dataframe["atr_pct"].iloc[-1])
        if np.isnan(atr_pct):
            return None
        sl = min(max(atr_pct * 2.5, 0.025), 0.05)
        return stoploss_from_open(-sl, current_profit)

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
        if not last["market_ok"] and current_profit > 0.008:
            return "market_turned"
        if not last["uptrend"] and current_profit > 0.004:
            return "trend_lost"
        hours = (current_time - trade.open_date_utc).total_seconds() / 3600
        if hours > 36 and current_profit > -0.01:
            return "stale_trade"
        return None
