# html-mockup

> 一个 [Claude Code Skill](https://docs.claude.com/en/docs/claude-code/skills)：让 AI 用**一页自包含 HTML** 讲清一件事 —— 需求原型，或一次代码改动的完整汇报。
>
> A Claude Code skill that makes the agent explain things with a **single self-contained HTML page** — either a requirement mockup for review, or a full change report of what a task actually changed.

聊天窗里的长篇文字，PM 读不完、测试没法验收、你自己也发现不了「这个改动用户其实根本碰不到」。这个 skill 把这类内容变成一张能发出去的页面：界面帧、规则卡、状态流转图、改前改后对比，一页讲完。

---

## 两种用法

| 模式 | 什么时候用 | 产出 |
|---|---|---|
| **A · 需求原型** | 「出个 X 的原型 / 画一下 X 长什么样 / 给 PM 看看」 | 几个界面帧 + 规则说明 + 流转图拼成一页，用来评审、拍板、贴 issue |
| **B · 改动汇报** | 「总结一下这次改了什么 / 动了哪些表 / 影响哪些业务点」 | 逐文件交代 + 表字段 diff + **原有业务规则被改了哪几条** + 影响面 + 回滚方案 |

模式 B 会派多个 agent 并行从不同角度收集（清点 / 数据库 / 规则 diff / 影响面 / 契约 / 风险），最后合并成一份不漏的报告。

---

## 装

```bash
git clone https://github.com/<owner>/html-mockup.git ~/.claude/skills/html-mockup
```

Claude Code 会自动发现 `~/.claude/skills/` 下的 skill。Codex CLI 用户软链过去即可：

```bash
ln -s ~/.claude/skills/html-mockup ~/.codex/skills/html-mockup
```

装完让 AI 跑一次自举，它会建原型目录、装模板和积木库、（在支持的环境里）起本地静态服务：

```bash
bash ~/.claude/skills/html-mockup/assets/bootstrap.sh
```

---

## 依赖

**必需的只有 Python 3**，且全部用标准库（`http.server` / `re` / `html` / `subprocess` / `tempfile` …），不装任何 pip 包。

| 依赖 | 必需? | 缺了会怎样 |
|---|---|---|
| Python 3.8+ | ✅ 必需 | 起不了静态服务、渲染不了线图 |
| `bash` + `curl` | ✅ 必需 | `bootstrap.sh` 跑不了（只影响自举，页面本身照常写） |
| [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli) | ⬜ 可选 | 线图退回成源码卡，页面不会坏 |
| Chrome / Chromium | ⬜ 可选 | 同上（mermaid-cli 要靠它渲染） |

装可选依赖（渲染线图用）：

```bash
# 不要让 puppeteer 再下一份 chrome，用系统已有的
PUPPETEER_SKIP_DOWNLOAD=1 npm i -g @mermaid-js/mermaid-cli
```

渲染器会自动探测系统 Chrome（含 macOS 的 `.app` 路径）和 `mmdc`，探测不到就跳过、保持源码卡原样，**不会把页面改坏**。

---

## 产出放哪

两条路，skill 会自动二选一：

| 形态 | 什么时候 |
|---|---|
| **对话内预览**（如 `preview_html` 工具） | 默认。零部署、即时可见 |
| **本地静态服务 + 公网链接** | ① 要给第三方看；② 要留存、要改版迭代；③ 已确认被截断；④ 内容很大（≈50KB+） |

`bootstrap.sh` 会按环境自己决定起不起服务：

- **在 [Coder](https://coder.com/) 工作区里** —— 有公网端口转发，起服务，并从 `VSCODE_PROXY_URI` / `CODER_AGENT_URL` **推导出本机真实的 BASE_URL**（不写死任何域名）
- **其他环境**（本地 mac / Linux）—— 不起服务，直接走对话内预览；要局域网自用可 `PROTO_SERVE=1` 强制起

可调环境变量：

```bash
PROTO_ROOT=~/www      # 原型根目录
PROTO_PORT=8008       # 端口
PROTO_SERVE=auto      # auto | 1 | 0
```

---

## 里面有什么

```
SKILL.md                     主文档：硬约束、两种模式的流程、视觉规范、踩过的坑
references/
  change-report.md           模式 B 手册：6 条并行收集线、9 节骨架、规则卡格式
  blocks.md                  积木索引
assets/
  template.html              起手模板
  blocks.html                积木库：界面帧 / 后台外壳 / 列表页 / 小票 / 规则卡 / 对比双栏 …
  bootstrap.sh               环境自举（幂等，重复跑安全）
  serve.py                   静态服务（标准库）
  render-mermaid.py          把 mermaid 源码卡渲成内联 SVG
  check-overflow.py          多视口检测横向溢出（元素撑破整页，页面上看不出来）
  align-page.py              把已有页面对齐到当前模板（字号阶梯 + 布局兜底 CSS）
```

### 几条硬约束

- **单文件、零外部依赖**。不引 CDN、不引 Google Fonts、不外链图片、不引 mermaid.js —— 有些部署环境带 `Cross-Origin-Embedder-Policy: require-corp`，跨源资源会被浏览器直接拦掉。字体用系统字体栈，图标用 Unicode 字符。
- **线图必须渲染成图**。SVG 是纯文本，预渲染后内联进 HTML，既是真图又不破坏单文件约束。只贴源码等于没画 —— 读者手机上看到的是一坨代码。
- **正文 16px 起，不要更小**。中文比拉丁字母更吃字号，14px 正文在 900px 栏里读着累。要更紧凑就减内容，不是缩字。
- **宽度按页面类型分两档，同一页内不许出现断层**。说明为主的需求原型用 `.wrap`（900px，16px 下 54 汉字/行）；规则卡 + 表格 + 并排双栏为主的改动汇报 / 调查报告用 `.wrap rep`（1280px）。天生更宽的内容（并排两个后台外壳、10 列以上宽表）再加 `.bleed`（1440px）。<br>**别单独优化每一块**：曾按行长把正文栏定 900、按装得下把 `.bleed` 定 1400，每块单独看都对，摞在同一页上就是断的 —— 规则卡文字挤在 701px，紧贴它的双栏铺开 1400px。判断标准是**同页最窄块与最宽块差距不超过一档**。
- **ASCII 图只用半角**。框线里混中文在浏览器里必然错位。
- **改动汇报必须落到「页面 → 操作 → 结果」**。只写「改了 xxx 函数的判断条件」，PM 无法验收、测试无法复现。

---

## render-mermaid.py

可以脱离 skill 单独用 —— 把任意 HTML 里 `<div class="mmd">…<pre>mermaid 源码</pre></div>` 形态的卡片就地渲染成内联 SVG：

```bash
python3 assets/render-mermaid.py page.html [more.html ...] [--force]
```

- **幂等**：已渲染过的跳过；重复跑只重算尺寸策略，`--force` 才重渲
- **源码保留**在 `<details>` 折叠里，仍可复制去 issue / PR
- **按 viewBox 宽度分档**：≤900px 撑满容器；>900px 保持原尺寸 + 横向滚动 + 提示 —— 宽图硬塞进 390px 手机屏会缩到 13%，字比蚂蚁还小
- **不碰页面原有的 CSS**：自己的样式写进独立的 `<style data-mermaid-svg>`，更新时整块替换。早期版本把 CSS 塞进页面已有的 `<style>`、用「标记 → `</style>`」范围替换，会把标记之后的用户 CSS 一起吃掉 —— 已修
- **失败不改坏页面**：缺 `mmdc` 或 Chrome 时保持源码卡原样

---

## check-overflow.py

同样可以脱离 skill 单独用 —— 检查页面有没有**横向溢出**（某个元素撑破整页，右侧内容跑到屏幕外）：

```bash
python3 assets/check-overflow.py page.html [more.html ...] [--widths=768,1280,1568]
```

**为什么需要它**：宽内容（并排双栏、宽表）塞进窄正文栏、外层又是 `overflow-x: visible` 时，内容会一路溢出到 `<body>`。**页面上没有任何报错、肉眼扫过去也正常**，只有量 `document.documentElement.scrollWidth - clientWidth` 才发现。实测一个页面被撑破 121px，右侧两列直接跑到屏幕外。

它会逐个视口检测，并只报**真正没被任何滚动容器兜住**的元素（自带 `overflow-x:auto` 的容器内溢出是正常的，不算）。有溢出时退出码为 1，方便接进 CI。

只依赖系统 Chrome / Chromium。

---

## align-page.py

页面是一次性产物，模板改了不会自动回流。而新页面常常是**照着某个旧页面抄 CSS** 起手的（不是从 `_template` 复制），于是把那天的旧字号、缺失的布局兜底一起继承下来 —— 页面看着完全正常，不量根本发现不了。

```bash
python3 assets/align-page.py page.html [more.html ...]
```

- **字号**：整体上调到当前阶梯（16px 正文）
- **布局兜底**：`.bleed` / `.mmd` 横滚 / `code` 断行 / `table.cmp` 横滚 / `dd dt` 的 `min-width:0`
- **幂等**：靠 `<style>` 里的标记判重，重复跑安全
- **内联 SVG 一律跳过并断言前后一致** —— mermaid 的节点框尺寸是渲染那一刻烤死的，字号一改文字就顶出框被裁

跑完接着跑 `check-overflow.py`：字号变大会把并排双栏、宽表撑得更宽。

---

## License

MIT
