# archify：更高规格的架构图（可选，不替代 mermaid）

> 只在**图本身就是交付物**时才读这份。改动汇报里的配图用 mermaid 就够，见 `SKILL.md` §7。

## 什么时候升级到 archify(可选,不替代 mermaid)

[archify](https://github.com/tt-a1i/archify) 是另一个 Agent Skill(MIT),专做架构类图,视觉水准明显高一档,而且**渲染前用 JSON Schema + 布局约束校验**——标签塞不下、节点重叠、边穿过无关节点,它都在渲染前拦住并给出修正坐标。

**但它不是 mermaid 的替代品**,四种图型实测成本差极大,决定因素是**坐标自由度**:

| 图型 | 轮次 | 布局模型 | 中文标签 | 用不用 |
|---|---|---|---|---|
| `sequence` 时序图 | **1** | 绝对 `y` 坐标 | 原文照搬 | **首选** |
| `lifecycle` 状态机 | 5 | 一维链 `col` | 原文照搬 | 可用(4 轮是机械调标签位置,它会算好坐标给你) |
| `architecture` 架构图 | 6 | 绝对 `pos`/`size` | 原文照搬 | 可用,但**别用 `boundary`**(见下) |
| `workflow` 流程图 | 7 | 泳道 × 6 列**网格** | **被迫压到 2~4 字** | **别用**,留给 mermaid |

**规律**:给绝对坐标的中文没问题,给网格的塞不进去——网格格宽是按短英文标签定死的。

**已知坑**:`architecture` 的 `boundary`(区域框)与「跨边界连线」天然冲突——框外节点连到框内,转折点必然落在框的左沿,触发 `container-border-run`。`fromSide/toSide`、`route:straight`、挪坐标都试过无效,最后只能删掉 boundary。要用就让连线两端都在框内或都在框外。

**边界**:图本身是交付物(架构评审、给外部看的系统地图)才值得花这个成本;改动汇报里的配图(图是配角)还用 mermaid,写完就渲。
## 多张 archify 图合并成一页(tab)

archify 每张图产出 ~620KB 独立 HTML,**且带 3 处 Google Fonts 外链——违反本 skill 的单文件硬约束**(COEP 会拦掉)。合并成 tab 页同时解决体积和外链:

```bash
python3 ~/.claude/skills/html-mockup/assets/archify-tabs.py <out.html> \
  流程图=a.html 状态机=b.html 时序图=c.html 架构图=d.html
```

实测四张图 **2477KB → 240KB(-90%)、外链归零**。能压这么多是因为同版本 archify 产出的那 177KB CSS **逐字节相同**,只留一份即可,所有图共用 `c-backend` / `a-emphasis` 命名空间。

**想让节点能点开看代码**,JSON 里要同时有两样,缺一不可:

```jsonc
"meta": { "repository": { "url": "https://github.com/<org>/<repo>", "revision": "<完整 sha>" } }
// 每个 component / state:
"sources": [ { "path": "main/pkg/storage/factory.go", "line": 29, "end_line": 50, "label": "读 STORAGE_DRIVER" } ]
```

**行号必须 `grep` 出来,不许编。**不存在的文件(比如「本次新增」还没写的)就别挂,挂了是死链。渲染时带 `--repo-root <仓库路径>` 校验路径存在。

> ⚠️ **它不内嵌代码,只生成 blob 链接**(`…/blob/<revision>/<path>#L29`)。实测:`factory.go:29` 的真实内容在产物里搜不到。所以**私有仓库对外部人是 404**,给 PM 看的图要么别挂 sources,要么先说明。
>
> ⚠️ **合并成 tab 页会丢掉这份数据** —— 它存在页面 JS 里,而 `archify-tabs.py` 只抠 `<svg>` + `<style>`(那正是 620KB→210KB、外链归零的原因)。脚本已补救,**不依赖 archify 的 viewer JS**,改用原生 SVG 链接:
>
> - 带 `sources` 的节点 `<g>` 包进 `<a href>` + `<title>` 悬停提示 —— **点节点直接跳 GitHub 那一行**
> - 图下面折叠一份源码列表,URL **明文完整写出来且可点**(明文和可点不冲突,见 §5「交付话术」)

> ⚠️ **必须给 id 加前缀,否则箭头全废。**各图 SVG 里都有同名 id(`arrowhead`、`arrowhead-dashed`、`archify-diagram-title` …),直接摞会互相覆盖。脚本已处理:加 `d0-`/`d1-` 前缀,并同步改写 `url(#…)`、`href="#…"`、`aria-labelledby`。收尾自检:每张图应各有 4 个 `<marker>`,且没有裸 `url(#` 引用。

**不预装,要用那次现拉**(零 npm 依赖,Node ≥18,约几十秒)。整仓 83MB 大半是 gallery 的图片和 GIF,只取 `archify/` 子目录 9.2MB:

```bash
A=/tmp/archify && rm -rf $A && \
git clone -q --depth 1 --filter=blob:none --sparse \
  https://github.com/tt-a1i/archify.git $A && \
git -C $A sparse-checkout set archify && \
node $A/archify/bin/archify.mjs doctor    # 全绿才往下走
```

之后一律用 `node $A/archify/bin/archify.mjs <子命令>`,用完 `rm -rf $A`。

**别预装在四台机器上**:按上表的边界,只有「图本身是交付物」才用得着,一年没几次;而且**产物是自包含单文件,看图的人和跑 `archify-tabs.py` 的人都不需要装**——那个脚本只读产物 HTML,依赖全是 Python 标准库。
