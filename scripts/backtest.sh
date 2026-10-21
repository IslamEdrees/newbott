#!/usr/bin/env bash
# اختبار الاستراتيجية على بيانات قديمة.  مثال:  ./scripts/backtest.sh 20250101-
set -euo pipefail
cd "$(dirname "$0")/.."
RANGE="${1:-$(date -d '-365 days' +%Y%m%d)-}"
CFG="--config /freqtrade/user_data/config.json --config /freqtrade/user_data/config-backtest.json"

docker compose run --rm freqtrade download-data $CFG \
  --timeframes 5m 1h --timerange "$RANGE"

docker compose run --rm freqtrade backtesting $CFG \
  --strategy "${STRATEGY:-SmartStrategy}" --timerange "$RANGE" \
  --breakdown month --cache none
