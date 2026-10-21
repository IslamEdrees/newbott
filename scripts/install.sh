#!/usr/bin/env bash
# تسطيب كامل بأمر واحد على سيرفر Ubuntu جديد (ينفع من الموبايل):
#   curl -fsSL https://raw.githubusercontent.com/IslamEdrees/newbott/ccr-827592fe-1232qh/scripts/install.sh | bash
set -euo pipefail

REPO="https://github.com/IslamEdrees/newbott.git"
BRANCH="ccr-827592fe-1232qh"
DIR="$HOME/newbott"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

ask() {  # ask <var> <prompt> [silent]
  local v
  if [ "${3:-}" = "silent" ]; then read -rsp "$2" v </dev/tty; echo; else read -rp "$2" v </dev/tty; fi
  printf -v "$1" '%s' "$v"
}

echo "📦 تثبيت الأدوات..."
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq git curl openssl >/dev/null
command -v docker >/dev/null || curl -fsSL https://get.docker.com | $SUDO sh

echo "⬇️ تنزيل البوت..."
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q; else git clone -q -b "$BRANCH" "$REPO" "$DIR"; fi
cd "$DIR"

if [ ! -f .env ]; then
  echo
  echo "🔑 اكتب المفاتيح (بتتحفظ على السيرفر ده بس):"
  ask BKEY  "Binance API Key: "
  ask BSEC  "Binance API Secret: " silent
  ask TTOK  "Telegram Bot Token: " silent
  ask TCHAT "Telegram Chat ID: "
  ask CAP   "البوت مسموحله يستخدم كام دولار USDT بالكتير؟ [50]: "
  CAP="${CAP:-50}"
  ask MODE  "تشغيل بفلوس وهمية الأول؟ (y/n) [y]: "
  if [ "${MODE:-y}" = "n" ]; then DRY=false; DB=tradesv3.sqlite; else DRY=true; DB=tradesv3.dryrun.sqlite; fi

  (umask 077; cat > .env <<EOF
FREQTRADE__DRY_RUN=$DRY
DB_FILE=$DB
FREQTRADE__AVAILABLE_CAPITAL=$CAP
FREQTRADE__DRY_RUN_WALLET=$CAP
FREQTRADE__EXCHANGE__KEY=$BKEY
FREQTRADE__EXCHANGE__SECRET=$BSEC
FREQTRADE__TELEGRAM__TOKEN=$TTOK
FREQTRADE__TELEGRAM__CHAT_ID=$TCHAT
FREQTRADE__API_SERVER__PASSWORD=$(openssl rand -hex 16)
FREQTRADE__API_SERVER__JWT_SECRET_KEY=$(openssl rand -hex 32)
FREQTRADE__API_SERVER__WS_TOKEN=$(openssl rand -hex 24)
EOF
  )
fi

mkdir -p user_data/logs
# الكونتينر بيشتغل بمستخدم uid 1000، فلازم يقدر يكتب في user_data
$SUDO chown -R 1000:1000 user_data
echo "🚀 تشغيل البوت..."
$SUDO docker compose pull -q
$SUDO docker compose up -d

echo
echo "✅ البوت شغال! هتوصلك رسالة على Telegram خلال دقيقة."
echo "   اللوج:    cd $DIR && $SUDO docker compose logs -f"
echo "   إيقاف:    cd $DIR && $SUDO docker compose down"
