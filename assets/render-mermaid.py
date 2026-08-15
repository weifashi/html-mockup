#!/usr/bin/env python3
"""把页面里 .mmd 卡片中的 mermaid 源码就地渲染成内联 SVG。

    python3 render-mermaid.py <page.html> [<page2.html> ...] [--force]

为什么要这个:
  硬约束是「单文件、不引 CDN」——所以不能 <script src=mermaid.js>。
  但 SVG 是纯文本,预渲染后内联进 HTML 完全不破坏这条约束,
  而且 preview_html 和 8008 两种场景都能直接看到图。

行为:
  · 幂等——已经渲染过(卡里已有 <svg>)的跳过；--force 强制重渲
  · 每次都会重新计算尺寸策略(窄图撑满 / 宽图保持原尺寸+横向滚动),
    所以对已渲染的页面再跑一次也能修好手机上被压扁的宽图
  · 源码保留在 <details> 里,仍可复制去 issue/PR
  · 渲染失败时保留原样的代码卡,不会把页面改坏
"""
import html as _html
import os
import re
import shutil
import subprocess
import sys
import tempfile

def _find_chrome():
    """跨平台找 chrome。macOS 上它在 .app 包里，which 找不到。"""
    env = os.environ.get("PUPPETEER_EXECUTABLE_PATH") or os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(n)
        if p:
            return p
    for p in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/snap/bin/chromium",
    ):
        if os.path.exists(p):
            return p
    return None


CHROME = _find_chrome()
PUPPETEER_CFG = '{"args":["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]}'
# 源码没写 %%{init}%% 时的兜底主题——卡片是黑底,默认亮色主题会糊成一片
MERMAID_CFG = '{"theme":"dark","themeVariables":{"fontSize":"14px"}}'

# 超过这个宽度就不再压缩进容器,改为保持原尺寸 + 横向滚动
WIDE_PX = 900

# 卡片结构: <div class="mmd"> [<div class="cap">标题</div>] <图或源码> </div>
# 注意: mermaid 的 SVG 里有 <foreignObject><div>，会把卡片的 </div> 边界吃掉，
# 所以匹配前先把整段 <svg>…</svg> 抠成占位符（见 process）。
CARD_RE = re.compile(
    r'(<div class="mmd[^"]*"[^>]*>\s*)'       # 1 卡片开头
    r'((?:<div class="cap">.*?</div>\s*)?)'   # 2 可选标题
    r'(.*?)'                                  # 3 卡片正文（已占位，无嵌套 div）
    r'(\s*</div>)',                           # 4 卡片结尾
    re.S,
)
PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.S)
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
PH_RE = re.compile("\x00SVG(\\d+)\x00")

CSS_MARK = "/* mermaid-svg */"
CSS_ADD = """
/* mermaid-svg */
.mmd{position:relative}
.mmd svg{height:auto;display:block;margin:0 auto}
.mmd.fit svg{width:100%}
.mmd.wide svg{width:auto;max-width:none}
.mmd.wide:after{content:"\\2190 \\2192 \\0020 \\6b64 \\56fe \\8f83 \\5bbd \\ff0c \\53ef \\5de6 \\53f3 \\6ed1 \\52a8";
 display:block;color:#64748b;font-size:10.5px;font-family:var(--mono,monospace);
 margin-top:6px;text-align:right;position:sticky;left:0}
.mmd details{margin-top:9px;position:sticky;left:0}
.mmd details summary{color:#94a3b8;font-size:11px;cursor:pointer;font-family:var(--mono,monospace);
 list-style:none;user-select:none;padding:2px 0}
.mmd details summary::-webkit-details-marker{display:none}
.mmd details summary:before{content:"\\25b8 ";color:#64748b}
.mmd details[open] summary:before{content:"\\25be "}
.mmd details pre{margin-top:6px;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;
 font-size:11px;opacity:.85}
"""


def strip_markup(raw: str) -> str:
    """把 <pre> 里的高亮 span 去掉、实体解码，还原成纯 mermaid 源码。"""
    s = re.sub(r"</?span[^>]*>", "", raw)
    s = _html.unescape(s)
    return s.strip("\n")


def _mmdc_cmd():
    """找 mmdc 的调用方式。非交互 shell 里 npx 可能不在 PATH（macOS 常见）。"""
    for c in filter(None, [shutil.which("mmdc"),
                           os.path.expanduser("~/bin/mmdc"),
                           os.path.expanduser("~/.npm-global/bin/mmdc"),
                           "/opt/homebrew/bin/mmdc", "/usr/local/bin/mmdc"]):
        if os.path.exists(c):
            return [c]
    for npx in filter(None, [shutil.which("npx"),
                             "/opt/homebrew/bin/npx", "/usr/local/bin/npx"]):
        if os.path.exists(npx):
            return [npx, "--no-install", "mmdc"]
    return None


MMDC = _mmdc_cmd()


def _path_with_node():
    """mmdc 的 shebang 是 #!/usr/bin/env node —— 非交互 shell 的 PATH 里
    往往没有 node（macOS + homebrew 必踩），得给子进程补上。"""
    dirs = [os.path.dirname(MMDC[0])] if MMDC else []
    dirs += ["/opt/homebrew/bin", "/usr/local/bin",
             os.path.expanduser("~/bin"), os.path.expanduser("~/.npm-global/bin")]
    cur = os.environ.get("PATH", "").split(os.pathsep)
    seen, out = set(), []
    for d in dirs + cur:
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return os.pathsep.join(out)


def render(src: str):
    """mermaid 源码 -> SVG 字符串；失败返回 None。"""
    if not CHROME:
        print("  ! 找不到 chrome/chromium，无法渲染", file=sys.stderr)
        return None
    if not MMDC:
        print("  ! 找不到 mmdc，跑 npm i -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return None
    with tempfile.TemporaryDirectory() as d:
        mmd, svg, pcfg, mcfg = (os.path.join(d, n) for n in ("i.mmd", "o.svg", "pc.json", "mc.json"))
        with open(mmd, "w", encoding="utf-8") as f:
            f.write(src)
        with open(pcfg, "w", encoding="utf-8") as f:
            f.write(PUPPETEER_CFG)
        with open(mcfg, "w", encoding="utf-8") as f:
            f.write(MERMAID_CFG)
        env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=CHROME, PATH=_path_with_node())
        r = subprocess.run(
            MMDC + ["-i", mmd, "-o", svg, "-p", pcfg, "-c", mcfg, "-b", "transparent"],
            capture_output=True, text=True, env=env, timeout=180,
        )
        if r.returncode != 0 or not os.path.exists(svg):
            tail = (r.stderr or r.stdout).strip().splitlines()[-1:]
            print(f"  ! 渲染失败: {tail}", file=sys.stderr)
            return None
        out = open(svg, encoding="utf-8").read()
    out = re.sub(r"<\?xml[^>]*\?>\s*", "", out)
    out = re.sub(r"<!DOCTYPE[^>]*>\s*", "", out)
    # 保险：不允许出现外链
    if re.search(r'(?:href|src)="https?://', out):
        print("  ! SVG 含外部引用，跳过（违反单文件约束）", file=sys.stderr)
        return None
    return out.strip()


def fit(svg: str):
    """按 viewBox 决定尺寸策略，返回 (改好的 svg, 'fit' | 'wide')。

    窄图撑满容器宽度即可；宽图压进 390px 手机屏会把字缩到看不清，
    改成保持原始尺寸、由 .mmd 的 overflow-x 提供横向滚动。
    """
    m = re.search(r'viewBox="\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)', svg)
    if not m:
        return svg, "fit"
    vw, vh = float(m.group(3)), float(m.group(4))
    head_end = svg.index(">")
    head, rest = svg[:head_end], svg[head_end:]
    head = re.sub(r'\s(?:width|height)="[^"]*"', "", head)
    head = re.sub(r'\sstyle="[^"]*"', "", head)
    if vw > WIDE_PX:
        head += f' width="{vw:.0f}" height="{vh:.0f}"'
        return head + rest, "wide"
    head += f' width="100%" style="max-width:{vw:.0f}px"'
    return head + rest, "fit"


def process(path, force=False):
    src = open(path, encoding="utf-8").read()
    done = refit = skipped = 0

    # 先把已有的 <svg>…</svg> 抠出来换成占位符，卡片边界才不会被 SVG 内部的 </div> 破坏
    blobs = []

    def stash(m):
        blobs.append(m.group(0))
        return f"\x00SVG{len(blobs) - 1}\x00"

    work = SVG_RE.sub(stash, src)

    def repl(m):
        nonlocal done, refit, skipped
        head, cap, body, tail = m.groups()
        ph = PH_RE.search(body)

        if ph and not force:
            # 已渲染过：只重算尺寸策略（修手机上被压扁的宽图）
            i = int(ph.group(1))
            blobs[i], kind = fit(blobs[i])
            refit += 1
            return f'{_klass(head, kind)}{cap}{body}{tail}'

        pre = PRE_RE.search(body)
        code = strip_markup(pre.group(1)) if pre else ""
        if not code:
            skipped += 1
            return m.group(0)
        svg = render(code)
        if svg is None:
            skipped += 1
            return m.group(0)
        svg, kind = fit(svg)
        blobs.append(svg)
        done += 1
        keep = _html.escape(code)
        return (f'{_klass(head, kind)}{cap}\x00SVG{len(blobs) - 1}\x00\n'
                f'<details><summary>mermaid 源码（可复制到 issue / PR 渲染）</summary>'
                f'<pre>{keep}</pre></details>{tail}')

    out = CARD_RE.sub(repl, work)
    out = PH_RE.sub(lambda m: blobs[int(m.group(1))], out)
    if done or refit:
        if CSS_MARK not in out:
            out = out.replace("</style>", CSS_ADD + "</style>", 1)
        else:
            # CSS 里有 \2190 之类的转义，不能当替换串（会被解释成组引用），用回调
            out = re.sub(re.escape(CSS_MARK) + r".*?(?=</style>)",
                         lambda _: CSS_ADD.lstrip("\n"), out, count=1, flags=re.S)
        open(path, "w", encoding="utf-8").write(out)
    return done, refit, skipped


def _klass(head: str, kind: str) -> str:
    """把 fit / wide 写进卡片的 class。"""
    head = re.sub(r'\sclass="mmd(?:\s+(?:fit|wide))?', ' class="mmd', head, count=1)
    return head.replace('class="mmd', f'class="mmd {kind}', 1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    if not args:
        sys.exit(__doc__)
    td = tr = ts = 0
    for p in args:
        if not os.path.isfile(p):
            print(f"  ! 找不到 {p}", file=sys.stderr)
            continue
        d, r, s = process(p, force)
        td, tr, ts = td + d, tr + r, ts + s
        name = os.path.basename(os.path.dirname(p)) or p
        print(f"  {name}: 渲染 {d} / 重排 {r} / 跳过 {s}")
    print(f"\n合计 渲染 {td} / 重排 {tr} / 跳过 {ts}")
