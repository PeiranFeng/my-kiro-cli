---
name: user-issue
description: 拉取指定仓库和时间范围内的 GitHub Issue，逐条翻译成中文并归档到 ~/data/issue/<repo>/<number>.md。当用户要求拉取、翻译、归档 GitHub Issue 时使用。
---

# user-issue — GitHub Issue 中文归档

拉取 issue、翻译成中文、按固定格式归档。gh 命令针对组织 `FinAI-Project` 下三个仓库（见 `50-project-facts.md#repos`）。

## Step 1 — 确认参数

优先从用户指令和对话上下文推断参数，不铺选项询问（见 `00-collaboration.md#answer-dont-offer-options`）。

- 模式 A：用户直接给了 issue 编号列表（如 `#1335 #1366` 或 `1335,1366`）及仓库，则跳过其他条件，直接进入 Step 2。
- 模式 B：未给编号列表，读取——仓库（三个，可多选，默认全部）、时间范围（默认最近 7 天）、指派人 assignee（默认不限制）、发布者 author（默认不限制）。有默认值则直接采用，仅关键前提无法推断且影响结果时才直接问一句。

## Step 2 — 拉取 Issue 列表

```bash
gh issue list \
  --repo FinAI-Project/<repo> \
  --state all \
  --search "created:>=<YYYY-MM-DD>[ author:<author>]" \
  [--assignee <assignee>] \
  --json number,title,url,state,createdAt \
  --limit 200
```

设置了发布者则在 `--search` 追加 `author:<login>`；设置了指派人则追加 `--assignee <login>`。列表为空则告知并跳过。

## Step 2.5 — 覆盖确认

```bash
ls ~/data/issue/<repo>/<number>.md 2>/dev/null
```

已存在时确认覆盖策略（覆盖=删除重写 / 跳过=仅处理不存在的）。删除已有文件是有副作用操作，须先确认再执行。

## Step 3 — 逐条处理

跳过策略下已存在文件直接略过；覆盖策略下先 `rm ~/data/issue/<repo>/<number>.md` 再处理。

### 3a 拉取完整内容

```bash
gh issue view <number> --repo FinAI-Project/<repo> \
  --json number,title,url,state,body,comments,labels,assignees,author,createdAt,closedAt
```

### 3b 翻译并写入

翻译规则：正文（标题、正文、评论）译为中文，专有名词后括注英文原文；代码块保持原文不翻译；图片替换为 `【此处有一张图片，无法解析】`；其他无法解析内容注明 `【此处有附件/媒体内容，无法解析】`。写入 `~/data/issue/<repo>/<number>.md`，格式：

```markdown
# Issue #<number>：<翻译后的标题>

- **编号（Number）**：#<number>
- **网址（URL）**：<url>
- **状态（State）**：开放中（open）/ 已关闭（closed）
- **作者（Author）**：<author>
- **创建时间（Created At）**：<createdAt>
- **关闭时间（Closed At）**：<closedAt>（未关闭则省略）
- **标签（Labels）**：<labels>（无则省略）
- **指派人（Assignees）**：<assignees>（无则省略）

---

## 描述（Description）

<翻译后的 body 正文>

---

## 评论（Comments）

### 评论 1 — <author>（<createdAt>）

<翻译后的评论内容>

### 评论 2 — <author>（<createdAt>）

<翻译后的评论内容>

（无评论则写"暂无评论（No comments）"）
```

## Step 4 — 汇报结果

```
已归档 Issue：
  compass-app-jasper: #1336, #1337, #1340（共 3 条）
  compass-core:       #88, #89（共 2 条）
  fenghe-nn:          无新 issue
文件位置：~/data/issue/
```
