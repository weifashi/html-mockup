#!/usr/bin/env python3
"""把多份 archify 产物合并成一个 tab 页（单文件、零外链）。

    python3 archify-tabs.py <out.html> <标签>=<a.html> [<标签>=<b.html> ...]
    python3 archify-tabs.py <out.html> a.html b.html            # 标签取图自己的标题

为什么要这个:
  archify 每张图产出一个 ~620KB 的独立 HTML，四张就是 2.5MB，而且每份都带
  3 处 Google Fonts 外链 —— 违反本 skill「单文件、不引 CDN」的硬约束
  （端口转发带 COEP require-corp，外链会被浏览器直接拦掉）。

  但同一版本 archify 产出的那 177KB CSS 是**逐字节相同**的，所有图共用
  c-backend / a-emphasis 这套 class 命名空间。所以只留一份 CSS + N 个
  内联 SVG，实测 2474KB -> 240KB（-90%），外链归零。

必须处理的坑:
  各图 SVG 里有同名 id（arrowhead / arrowhead-dashed / archify-diagram-title …），
  直接摞会互相覆盖 —— **箭头会全部失效**。本脚本给每张图的 id 加 d0-/d1- 前缀，
  并同步改写 url(#…)、href="#…"、aria-labelledby / aria-describedby。
"""
import html as _html
import os
import re
import sys

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S)
ID_RE = re.compile(r'\sid="([^"]+)"')

TAB_CSS = """
.tabwrap{max-width:1600px;margin:0 auto;padding:16px}
.tabwrap h1{font-size:20px;margin:0 0 14px}
.tabbar{display:flex;gap:6px;border-bottom:2px solid rgba(128,128,128,.3);
 margin-bottom:14px;flex-wrap:wrap}
.tb{border:0;background:none;padding:9px 16px;font-size:15px;cursor:pointer;
 border-bottom:2px solid transparent;margin-bottom:-2px;font-family:inherit;opacity:.65}
.tb.on{border-bottom-color:currentColor;font-weight:600;opacity:1}
.pane{display:none}
.pane.on{display:block}
.pane .cap{font-size:15px;margin:0 0 12px;opacity:.75}
.pane svg{max-width:100%;height:auto}
"""

TAB_JS = (
    'document.querySelectorAll(".tb").forEach(function(b){b.onclick=function(){'
    'document.querySelectorAll(".tb,.pane").forEach(function(e){e.classList.remove("on")});'
    'b.classList.add("on");'
    'document.querySelector(\'.pane[data-i="\'+b.dataset.i+\'"]\').classList.add("on")}});'
)


def prefix_ids(svg: str, pre: str) -> str:
    """给 SVG 内部所有 id 加前缀，并同步改写引用它们的地方。"""
    # 长的先替换，避免 arrowhead 把 arrowhead-dashed 的前半截也换掉
    for i in sorted(set(ID_RE.findall(svg)), key=len, reverse=True):
        svg = svg.replace(f'id="{i}"', f'id="{pre}{i}"')
        svg = svg.replace(f"url(#{i})", f"url(#{pre}{i})")
        svg = svg.replace(f'href="#{i}"', f'href="#{pre}{i}"')
        svg = svg.replace(f'aria-labelledby="{i}', f'aria-labelledby="{pre}{i}')
        svg = svg.replace(f'aria-describedby="{i}', f'aria-describedby="{pre}{i}')
    return svg


def load(path: str):
    src = open(path, encoding="utf-8").read()
    m = SVG_RE.search(src)
    if not m:
        raise SystemExit(f"  ! {path} 里没有 <svg>，不像 archify 产物")
    css = "\n".join(STYLE_RE.findall(src))
    t = TITLE_RE.search(src)
    title = re.sub(r"\s+", " ", t.group(1)).strip() if t else os.path.basename(path)
    return m.group(0), css, title


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    out_path, items = argv[1], argv[2:]

    svgs, css_set, tabs, panes = [], [], [], []
    for i, item in enumerate(items):
        label, _, path = item.partition("=")
        if not path:
            path, label = label, ""
        svg, css, title = load(path)
        css_set.append(css)
        svgs.append(prefix_ids(svg, f"d{i}-"))
        name = _html.escape(label or title)
        on = " on" if i == 0 else ""
        tabs.append(f'<button class="tb{on}" data-i="{i}">{name}</button>')
        panes.append(f'<section class="pane{on}" data-i="{i}">'
                     f'<p class="cap">{_html.escape(title)}</p>{svgs[-1]}</section>')

    uniq = {c for c in css_set}
    if len(uniq) > 1:
        print(f"  ! {len(uniq)} 份 CSS 不一致（archify 版本不同？），全部保留，体积会变大",
              file=sys.stderr)
    css = "\n".join(sorted(uniq, key=len, reverse=True)) if len(uniq) > 1 else css_set[0]

    page_title = os.path.splitext(os.path.basename(out_path))[0]
    out = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_html.escape(page_title)}</title>"
        f"<style>{css}</style><style>{TAB_CSS}</style></head><body>"
        f'<div class="tabwrap"><h1>{_html.escape(page_title)}</h1>'
        f'<div class="tabbar">{"".join(tabs)}</div>{"".join(panes)}</div>'
        f"<script>{TAB_JS}</script></body></html>"
    )

    ext = re.findall(r'(?:href|src)="https?://', out)
    if ext:
        print(f"  ! 产物仍有 {len(ext)} 处外链，违反单文件约束", file=sys.stderr)

    open(out_path, "w", encoding="utf-8").write(out)
    total = sum(os.path.getsize(i.partition("=")[2] or i.partition("=")[0]) for i in items)
    print(f"  {os.path.basename(out_path)}: {len(items)} 张图  "
          f"{total // 1024}KB -> {len(out) // 1024}KB  外链 {len(ext)} 处")


if __name__ == "__main__":
    main(sys.argv)
