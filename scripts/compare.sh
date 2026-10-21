#!/usr/bin/env bash
# مقارنة كل الاستراتيجيات على نفس البيانات الحقيقية.
#   ./scripts/compare.sh               آخر 90 يوم
#   ./scripts/compare.sh 20260101-     من تاريخ معين
set -euo pipefail
cd "$(dirname "$0")/.."
RANGE="${1:-$(date -d '-90 days' +%Y%m%d)-}"
STRATS="${STRATS:-SmartStrategy ScalpStrategy SwingStrategy}"
export BOT_MEM="${BT_MEM:-1500m}"
CFG="--config /freqtrade/user_data/config.json --config /freqtrade/user_data/config-backtest.json"

docker compose run --rm freqtrade download-data $CFG \
  --timeframes 5m 15m 1h 4h --timerange "$RANGE" >/tmp/bt_download.log 2>&1

for s in $STRATS; do
  docker compose run --rm freqtrade backtesting $CFG \
    --strategy "$s" --timerange "$RANGE" --cache none --export none \
    >"/tmp/bt_$s.log" 2>&1 || echo "❌ $s failed, see /tmp/bt_$s.log"
done

echo "===== RESULTS ($RANGE) ====="
for s in $STRATS; do
  f="/tmp/bt_$s.log"
  echo
  echo "### $s"
  grep -E "Market change|Max % of account underwater  |Profit factor" "$f" | tr -s ' '
  grep -E "^│ +$s " "$f" | tr -s ' '
  echo "-- exits:"
  awk '/EXIT REASON STATS/{f=1} f&&/TOTAL/{print; f=0} f&&/│/' "$f" | tr -s ' '
done
