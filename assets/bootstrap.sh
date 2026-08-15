#!/usr/bin/env bash
# html-mockup 环境自举 —— 幂等,重复跑安全。
#   1) 建原型根目录       2) 装 _template / _blocks
#   3) 起 8008 静态服务   4) 本地自检
#   5) 打印本机真实 BASE_URL(永远用它,不要背域名)
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$SKILL_DIR/assets"
ROOT="${PROTO_ROOT:-$HOME/www}"
PORT="${PROTO_PORT:-8008}"
LOG="$ROOT/.serve.log"

say() { printf '%s\n' "$*"; }

# ---- 0) 这台要不要起 8008 ---------------------------------------------------
# Coder 工作区有公网端口转发,值得常驻服务;mac 开发机等没有转发通道,
# 起了也只能局域网看,还白占一个端口 —— 那边原型直接走 preview_html。
# 需要强制起/不起:PROTO_SERVE=1 / PROTO_SERVE=0
SERVE="${PROTO_SERVE:-auto}"
if [ "$SERVE" = "auto" ]; then
  if [ -n "${CODER_WORKSPACE_NAME:-}${VSCODE_PROXY_URI:-}" ]; then SERVE=1; else SERVE=0; fi
fi

if [ "$SERVE" = "0" ]; then
  say "· 本机不起 8008(非 Coder 环境,没有公网转发通道)"
  say "· 原型直接走 preview_html —— 这台上 SKILL.md §4.5 的 ①② 本来就做不到"
  say "· 积木库和模板直接读文件,不用起服务:"
  say "    $ASSETS/blocks.html"
  say "    $ASSETS/template.html"
  say ""
  say "  真要起服务(局域网自用):PROTO_SERVE=1 bash $0"
  exit 0
fi

# ---- 1) 原型根目录(已存在或已是软链则沿用) --------------------------------
if [ -L "$ROOT" ]; then
  say "· 原型根目录: $ROOT -> $(readlink -f "$ROOT") (软链,沿用)"
else
  mkdir -p "$ROOT"
  say "· 原型根目录: $ROOT"
fi

# ---- 2) 模板与积木库(每次覆盖,保持与 skill 同版本) ------------------------
mkdir -p "$ROOT/_template" "$ROOT/_blocks"
cp -f "$ASSETS/template.html" "$ROOT/_template/index.html"
cp -f "$ASSETS/blocks.html"   "$ROOT/_blocks/index.html"
say "· 已更新 _template/ 与 _blocks/"

# 积木库自己的 mermaid 样图也得是真图,不然抄的人以为源码卡就是终态
if command -v python3 >/dev/null 2>&1; then
  python3 "$ASSETS/render-mermaid.py" "$ROOT/_blocks/index.html" >/dev/null 2>&1 \
    && say "· _blocks 的 mermaid 已渲染" \
    || say "! _blocks 的 mermaid 未渲染(缺 mermaid-cli 或 chrome,不影响其他功能)"
fi

# ---- 3) 8008 静态服务 -------------------------------------------------------
if curl -fsS -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null; then
  say "· 服务已在运行: 127.0.0.1:$PORT"
else
  pkill -f "serve.py .* $PORT" 2>/dev/null
  PY=$(command -v python3 || echo /usr/bin/python3)   # 绝对路径:nohup 后 PATH 可能不同
  nohup "$PY" "$ASSETS/serve.py" "$ROOT" "$PORT" >>"$LOG" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/" 2>/dev/null && break
    sleep 0.4
  done
  say "· 已启动服务(日志 $LOG)"
fi

# ---- 4) 自检 ---------------------------------------------------------------
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/_blocks/")
if [ "$code" = "200" ]; then
  say "· 自检 OK: /_blocks/ -> 200"
else
  say "! 自检失败: /_blocks/ -> $code  (看 $LOG)"
fi

# ---- 5) BASE_URL(从 Coder 端口转发模板推导,推不出才回落拼接) ---------------
if [ -n "${VSCODE_PROXY_URI:-}" ]; then
  BASE="${VSCODE_PROXY_URI/\{\{port\}\}/$PORT}"
elif [ -n "${CODER_WORKSPACE_NAME:-}" ]; then
  # 域名从 CODER_AGENT_URL 推导，不同 Coder 部署各不相同，不要写死
  DOMAIN=$(printf '%s' "${CODER_AGENT_URL:-}" | sed -E 's#^https?://##; s#/.*$##')
  BASE="https://${PORT}--${CODER_WORKSPACE_AGENT_NAME:-main}--${CODER_WORKSPACE_NAME}--${CODER_WORKSPACE_OWNER_NAME:-$USER}.${DOMAIN:-example.invalid}"
else
  # 非 Coder 环境(mac 开发机等):优先给局域网地址,同网段的人能直接打开
  LAN=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
        || hostname -I 2>/dev/null | awk '{print $1}')
  if [ -n "${LAN:-}" ]; then
    BASE="http://$LAN:$PORT"
    say "· 非 Coder 环境:给的是局域网地址,同网段可直接打开;要发给外部人需另配隧道"
  else
    BASE="http://127.0.0.1:$PORT"
    say "! 非 Coder 环境且取不到局域网 IP,只有本机能访问"
  fi
fi
BASE="${BASE%/}/"

# 探测公网可达性。Coder 端口默认 owner-only,外部人打开会跳登录页(3xx/401)。
# 工作区里的 coder 是精简 agent 版,没有 port-share 子命令,只能去面板改。
if [ "${BASE:0:5}" = "https" ]; then
  pub=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${BASE}_blocks/")
  case "$pub" in
    200) say "· 公网可达: $pub (已 public,可以直接发给别人)" ;;
    000) say "! 公网探测超时,工作区出网可能受限;从你自己浏览器再试一次" ;;
    *)   say "! 公网返回 $pub —— 端口还是 owner-only,别人打开是登录页。"
         say "  去 ${CODER_AGENT_URL:-<你的 Coder 地址>}@${CODER_WORKSPACE_OWNER_NAME:-$USER}/${CODER_WORKSPACE_NAME:-?} 的 Ports,"
         say "  把 $PORT 的 Share 改成 Public,再发链接。" ;;
  esac
fi

say ""
say "已有原型:"
ls -d "$ROOT"/*/ 2>/dev/null | sed "s#^#  #" | head -40
say ""
say "BASE_URL=$BASE"
