#!/usr/bin/env bash
# تجهيز سيرفر Ubuntu جديد: تثبيت Docker وتجهيز ملف .env
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s|^FREQTRADE__API_SERVER__PASSWORD=.*|FREQTRADE__API_SERVER__PASSWORD=$(openssl rand -hex 16)|" .env
  sed -i "s|^FREQTRADE__API_SERVER__JWT_SECRET_KEY=.*|FREQTRADE__API_SERVER__JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env
  sed -i "s|^FREQTRADE__API_SERVER__WS_TOKEN=.*|FREQTRADE__API_SERVER__WS_TOKEN=$(openssl rand -hex 24)|" .env
  chmod 600 .env
  echo "✅ اتعمل ملف .env — افتحه واكتب مفاتيح Binance و Telegram:  nano .env"
fi
mkdir -p user_data/logs
# الكونتينر بيشتغل بمستخدم uid 1000، فلازم يقدر يكتب في user_data
if [ "$(id -u)" -eq 0 ]; then chown -R 1000:1000 user_data; else sudo chown -R 1000:1000 user_data; fi
echo "✅ السيرفر جاهز. بعد ما تملا .env شغّل:  docker compose up -d"
