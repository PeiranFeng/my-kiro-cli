---
name: user-pr
description: 拉取指定仓库和时间范围内的 GitHub PR，阅读源码做实质分析并归档到 ~/data/pr/<repo>/<number>.md。当用户要求分析、归档、review GitHub PR 时使用。
---

# user-pr — GitHub Pull Request 分析归档

拉取 PR、阅读源码、做独立分析并按固定格式归档。所有 gh 命令针对组织 `FinAI-Project` 下的三个仓库（见 `50-project-facts.md#repos`）。

## Step 1 — 确认参数

优先从用户指令和对话上下文推断参数，不铺选项询问（见 `00-collaboration.md#answer-dont-offer-options`）。

- 模式 A：用户直接给了 PR 编号列表（如 `#210 #211` 或 `210,211`）及仓库，则跳过其他条件，直接以该列表为目标进入 Step 2。
- 模式 B：未给编号列表，读取以下筛选参数——仓库（`compass-app-jasper`/`compass-core`/`fenghe-nn`，可多选，默认全部三个）、时间范围（默认最近 7 天）、发布者 author（默认不限制）。这些参数有默认值，直接采用默认继续，仅当某个关键前提无法推断且会改变结果时才直接问一句。

## Step 2 — 拉取 PR 列表

对每个目标仓库：

```bash
gh pr list \
  --repo FinAI-Project/<repo> \
  --state all \
  --search "created:>=<YYYY-MM-DD>" \
  [--author <author>] \
  --json number,title,url,state,createdAt \
  --limit 200
```

设置了发布者才追加 `--author <login>`。列表为空则告知用户该仓库无 PR 并跳过。

## Step 2.5 — 覆盖确认

检查待处理编号在 `~/data/pr/<repo>/` 下是否已有 `.md`：

```bash
ls ~/data/pr/<repo>/<number>.md 2>/dev/null
```

已存在时，向用户确认覆盖策略（覆盖=删除重写 / 跳过=仅处理不存在的编号）后固定下来。删除已有文件是有副作用操作，须先确认再执行。

## Step 3 — 逐条处理

跳过策略下已存在的文件直接略过；覆盖策略下先 `rm ~/data/pr/<repo>/<number>.md` 再处理。

### 3.1 拉取元数据、审查意见、diff

```bash
gh pr view <number> --repo FinAI-Project/<repo> \
  --json number,title,url,state,body,comments,reviews,labels,assignees,author,createdAt,closedAt,mergedAt,baseRefName,headRefName
```

inline review comments（`reviews` 只含 review body，不含 inline）：

```bash
gh api repos/FinAI-Project/<repo>/pulls/<number>/comments \
  --jq '.[] | {id, path, line, body, user: .user.login}'
```

diff：

```bash
gh pr diff <number> --repo FinAI-Project/<repo>
```

### 3.2 阅读源码，理解改动

不切换分支。先 fetch 再用 `git show` 读远程分支文件；每一步验证成功后才继续——读到的内容是后续分析的唯一依据，读错却未发现会让全部分析建立在错误内容上：

```bash
git -C ~/data/<repo> fetch origin
git -C ~/data/<repo> show origin/<headRefName>:<path/to/file>
```

- fetch 失败（网络、路径错）：停止并报告，不得用可能过期的本地 `origin/<headRefName>` 继续。
- `git show` 失败（分支/路径不存在、`fatal: invalid object name` 等）：停止，核对 `headRefName`/路径与 3.1 元数据一致后重试，不凭猜测内容继续。
- 每次 `git show` 前确认路径确实出现在 3.1 的 diff 里，不读 diff 之外的路径。

阅读入口：compass-app-jasper 从 `app2/Makefile` 或 `app2/train.py` 出发追踪 diff 涉及模块；compass-core / fenghe-nn 从 diff 涉及的 `test/` 测试文件出发追到实现。

阅读目标：
1. 明确每个改动文件的职责和在架构中的位置。
2. 理解新增/修改代码的逻辑（做了什么、为什么）。
3. 强制核对 review 检查项：扫描 steering 中的 `[review]` 标记（`grep -rn '\[review\]' .kiro/steering/`，方法见 `user-review` skill），逐条对这份 diff 给出通过/存在问题的结论，覆盖全部标记条目。
4. diff 涉及的自定义类型、以及审查意见指控有问题的代码所涉类型，必须追到实现文件、验证实际行为后再下结论。
5. 用搜索确认"某调用不存在/某字段无人使用"时适用 `20-engineering.md#empty-search-not-absence`：空结果须换一种方法二次确认。

### 3.3 写入 MD 文件

基于源码阅读做实质性分析，不是翻译 PR 内容。写作规则：正文用中文，专有名词后括注英文原文；代码块保持原文不翻译；图片替换为 `【此处有一张图片，无法解析】`；其他无法解析内容注明 `【此处有附件/媒体内容，无法解析】`。写入 `~/data/pr/<repo>/<number>.md`，格式：

```markdown
# PR #<number>：<翻译后的标题>

- **编号（Number）**：#<number>
- **网址（URL）**：<url>
- **状态（State）**：开放中（open）/ 已合并（merged）/ 已关闭（closed）
- **作者（Author）**：<author>
- **源分支（Head Branch）**：<headRefName>
- **目标分支（Base Branch）**：<baseRefName>
- **创建时间（Created At）**：<createdAt>
- **合并时间（Merged At）**：<mergedAt>（未合并则省略）
- **关闭时间（Closed At）**：<closedAt>（未关闭则省略）
- **标签（Labels）**：<labels>（无则省略）
- **指派人（Assignees）**：<assignees>（无则省略）

---

## 变更摘要（Change Summary）

<!-- 基于源码阅读的改动说明，非 PR body 翻译。说明改了哪些文件、各自职责、核心逻辑变化。 -->

---

## 独立代码审查

<!-- 基于源码阅读的独立发现，与 GitHub 既有意见无关。每条 [review] 标记条目有且只有一个结论，来源为 3.2 的逐条核对。
按 10-communication.md 的描述代码行为原则组织成连贯叙述：不重复变更摘要已介绍的类/模块信息，但引用具体方法/变量时让读者能定位其归属（用"见上文变更摘要的 <类名>"引用而非重新完整介绍）；每条先说是什么（给文件路径和行号）再说为什么是问题，不堆大段代码块；全篇统一叙述风格与详略度。
按条目逐项呈现，每项给明确结论（通过/存在问题），存在问题时注明文件和行号。全部通过写"各项均通过"。 -->

---

## GitHub 审查意见与评估

<!-- 逐条列出 PR 上所有评论，原文在上、评估紧随其后。
来源标签（账号名在前，类型标签紧随）：`<login> [🤖]` AI bot；`<login> [👤]` 人工。
Gemini/Codex 自动摘要类 review body 不含具体意见，注明后跳过不评估：
  **<login> [🤖] 自动摘要**（不评估）：<一句话概括>
含具体意见的 comment 用以下格式：

### 意见 N — <login> [🤖]/[👤] — <时间或 commit>

> （原文关键段落，完整引用；过长可用"……"省略）

**评估**：成立 / 不成立 / 部分成立
**理由**：…（基于源码实地验证，不凭描述推断）
**处理状态**：已处理 / 未处理 / 不需要处理
-->
```

## Step 4 — 汇报结果

```
已归档 PR：
  compass-app-jasper: #<n1>, #<n2>（共 <count> 条）
  compass-core:       #<n>（共 <count> 条）
  fenghe-nn:          无新 PR
文件位置：~/data/pr/
```
