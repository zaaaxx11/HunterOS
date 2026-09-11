#!/bin/bash
# Disk usage watchdog — alert Telegram if rootfs >= 85%
THRESH=85
USE=$(df / | awk 'NR==2 {gsub(/%/,""); print $5}')
if [ "$USE" -ge "$THRESH" ]; then
  MSG="🚨 DISK WARNING — / usage = ${USE}% >= ${THRESH}%! Cleanup needed to avoid session corruption."
  curl -sS "https://api.telegram.org/bot$(grep -Po 'telegram_bot_token\s*=\s*"\K[^"]+' /root/.hermes/config.toml 2>/dev/null)/sendMessage" -d chat_id="$TARGET_CHAT_ID" -d text="$MSG" >/dev/null 2>&1
fi
exit 0