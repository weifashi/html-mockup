#!/usr/bin/env python3
"""检查页面有没有横向溢出（元素撑破整页，右侧内容跑到屏幕外）。

    python3 check-overflow.py <page.html> [<page2.html> ...] [--widths 390,768,1280,1568]

为什么要这个:
  正文栏一般 900px，但并排双栏、宽表、宽 ASCII 树天生要 1300px 上下。
  外层若是 overflow-x: visible，内容会一路溢出 .st -> .wrap -> 整页，
  页面上看不出任何报错，只有量 scrollWidth 才发现右侧内容跑到屏幕外了。
  修法见 SKILL.md §7「宽度」——给那几类内容加 .bleed。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PROBE = (
    'const vw=document.documentElement.clientWidth;const bad=[];'
    'document.querySelectorAll("*").forEach(e=>{const r=e.getBoundingClientRect();'
    'if(r.right>vw+1||r.left<-1){let p=e,c=false;'
    'while((p=p.parentElement)){const o=getComputedStyle(p).overflowX;'
    'if(o==="auto"||o==="hidden"||o==="scroll"){c=true;break;}}'
    'if(!c)bad.push({t:e.tagName.toLowerCase()+"."+(e.className||"").toString().split(" ")[0],'
    'r:r.right|0,w:r.width|0});}});'
    'document.title="@@"+JSON.stringify({vw,'
    'ov:document.documentElement.scrollWidth-vw,n:bad.length,top:bad.slice(0,5)})+"@@";'
)


def _chrome():
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(n)
        if p:
            return p
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if os.path.exists(p):
            return p
    return None


CHROME = _chrome()


def check(path, widths):
    src = open(path, encoding="utf-8").read()
    if "</body>" in src:
        src = src.replace("</body>", f"<script>{PROBE}</script></body>", 1)
    else:
        src += f"<script>{PROBE}</script>"
    bad = 0
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "p.html")
        open(p, "w", encoding="utf-8").write(src)
        for w in widths:
            r = subprocess.run(
                [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                 f"--window-size={w},900", "--virtual-time-budget=3500",
                 "--dump-dom", f"file://{p}"],
                capture_output=True, text=True, timeout=90)
            m = re.search(r"<title>@@(.*?)@@</title>", r.stdout, re.S)
            if not m:
                print(f"    视口 {w:>5}  ! 探测失败", file=sys.stderr)
                continue
            g = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&"))
            if g["ov"] > 0:
                bad += 1
                print(f"    视口 {g['vw']:>5}  ✗ 撑破 {g['ov']}px，{g['n']} 个元素没被滚动容器兜住")
                for b in g["top"]:
                    print(f"        {b['t']:24} 右边 {b['r']}  宽 {b['w']}")
            else:
                print(f"    视口 {g['vw']:>5}  ✓")
    return bad


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wm = [a for a in sys.argv[1:] if a.startswith("--widths")]
    widths = [int(x) for x in wm[0].split("=", 1)[1].split(",")] if wm and "=" in wm[0] \
        else [768, 1280, 1568]
    if not args:
        sys.exit(__doc__)
    if not CHROME:
        sys.exit("找不到 chrome/chromium，无法检查")
    total = 0
    for p in args:
        if not os.path.isfile(p):
            print(f"  ! 找不到 {p}", file=sys.stderr)
            continue
        print(f"  {os.path.basename(os.path.dirname(p)) or p}")
        total += check(p, widths)
    print(f"\n{'全部通过 ✓' if total == 0 else f'{total} 处横向溢出，见 SKILL.md §7 宽度'}")
    sys.exit(1 if total else 0)
