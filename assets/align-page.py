#!/usr/bin/env python3
"""把已有页面对齐到当前模板：字号阶梯 + 布局兜底 CSS。

    python3 align-page.py <page.html> [<page2.html> ...]

为什么要这个:
  页面是一次性产物，模板改了不会自动回流。而新页面常常是照着某个旧页面
  抄 CSS 起手的（不是从 _template 复制），于是把那天的旧字号、缺失的
  布局兜底一起继承下来 —— 页面看着完全正常，不量根本发现不了。
  2026-08-16 一天之内连踩三次。

它做两件事，各自幂等（靠 <style> 里的标记判重，重复跑安全）:
  · 字号:整体上调两档，对齐模板的 16px 正文阶梯
  · 布局:补 .bleed / .mmd 横滚 / code 断行 / table.cmp 横滚 / dd dt min-width:0

**内联 SVG 一律跳过并断言前后一致** —— mermaid 的节点框尺寸是渲染那一刻
烤死的，字号一改文字就顶出框被裁。

跑完接着跑 check-overflow.py:字号变大会把并排双栏、宽表撑得更宽。
"""
import re, sys, os
M1 = {'10':'10.5','10.5':'11','11':'11.5','11.5':'12','12':'12.5','12.5':'13',
      '13':'14','13.5':'14','14':'15','15':'16','16':'17','22':'23'}
M2 = {'10':'10.5','10.5':'11','11':'11.5','11.5':'12','12':'12.5','12.5':'13',
      '13':'14','13.5':'14.5','14':'15','14.5':'15','15':'16','16':'17',
      '17':'18','18':'19','19':'20','22':'23','23':'24'}
SVG_RE = re.compile(r'<svg\b.*?</svg>', re.S)
FMARK = '/* font-scale-2 */'
LMARK = '/* layout-guard v3'
CSS = """
/* layout-guard v3 —— 与模板一致的布局兜底，防止内容悄悄撑破整页 */
.wrap .bleed{overflow-x:auto}
@media (min-width:1000px){
  .wrap .bleed,.wrap .mmd.wide{--bw:min(1400px,calc(100vw - 40px));
    width:var(--bw);margin-left:calc(50% - var(--bw) / 2)}
}
.mmd{overflow-x:auto}
/* 裸文本里的长标识符(没包 <code> 的那些)在窄屏必须能断行 —— 
   按元素右边缘扫是扫不到它的,它是文本节点,没有元素可报 */
.wrap{overflow-wrap:break-word}
code{overflow-wrap:anywhere}
.wrap table.cmp{display:block;overflow-x:auto;max-width:100%}
.wrap dd,.wrap dt,.wrap dl > *{min-width:0}
/* 窄屏下表格一律可横滚 —— 逐个枚举 .cmp/.mx/.dt 挡不住，宽屏不受影响 */
@media (max-width:900px){
  .wrap table{display:block;overflow-x:auto;max-width:100%}
}
"""

def scale(t, M):
    blobs = []
    def stash(m):
        blobs.append(m.group(0)); return f"\x00S{len(blobs)-1}\x00"
    w = SVG_RE.sub(stash, t)
    w = re.sub(r'font-size:\s*([\d.]+)px',
               lambda m: f"font-size:{M.get(m.group(1), m.group(1))}px", w)
    return re.sub(r'\x00S(\d+)\x00', lambda m: blobs[int(m.group(1))], w)

for p in sys.argv[1:]:
    s = open(p, encoding='utf-8').read()
    name = os.path.basename(os.path.dirname(os.path.abspath(p)))
    out, did = s, []
    if FMARK not in out:
        out = scale(scale(out, M1), M2)
        assert SVG_RE.findall(s) == SVG_RE.findall(out), f"{p}: SVG 被动了"
        out = out.replace('</style>', FMARK + '</style>', 1); did.append('字号')
    if LMARK not in out:
        out = out.replace('</style>', CSS + '</style>', 1); did.append('布局')
    if not did:
        print(f"  {name}: 已是最新"); continue
    open(p, 'w', encoding='utf-8').write(out)
    print(f"  {name}: ✓ 补了 {' + '.join(did)}")
