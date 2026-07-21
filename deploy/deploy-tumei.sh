#!/usr/bin/env bash
# 一键部署：把最新 index.html 同步到 wordtest.tumei.online
# （腾讯云广州 · 系统自带 Nginx 静态站，与 word.tumei.online 同一台服务器 43.139.242.52）
#
# 本应用是单文件应用：所有数据/图表/JS/CSS 都内联在 index.html 里，
# 因此“发布内容”就是把 index.html 覆盖到服务器站点根目录。
#
# 前提：本机 ~/.ssh/tumei_deploy 私钥已授权到服务器 root（与背单词项目共用同一把钥匙）。
# 日常更新：改完 index.html 后，直接 bash deploy/deploy-tumei.sh 即可。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${TUMEI_KEY:-$HOME/.ssh/tumei_deploy}"
HOST="${TUMEI_HOST:-root@43.139.242.52}"
DEST="/var/www/wordtest.tumei.online"

[ -f "$KEY" ] || { echo "找不到部署私钥 $KEY"; exit 1; }

echo "同步 index.html + 本地库 -> $HOST:$DEST"
rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
  "$ROOT/index.html" "$ROOT/dom-to-image-more.min.js" "$ROOT/jspdf.umd.min.js" "$HOST:$DEST/"

ssh -i "$KEY" "$HOST" 'nginx -t >/dev/null 2>&1 && systemctl reload nginx && echo nginx-reloaded'
echo "✅ 已部署 -> https://wordtest.tumei.online/"
