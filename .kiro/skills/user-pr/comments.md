# 接口：comments

查阅 PR 上已有的 review 意见，逐条对照源码评估。只在回复里呈现，不写文件。不对 diff 做独立代码审查，也不核对 `[review]` 检查项。

## 步骤

### 1. 拉取意见

三类来源都要取：

```bash
gh pr view <number> --repo FinAI-Project/<repo> \
  --json number,title,url,state,author,headRefName,baseRefName,headRefOid,comments,reviews
```

`reviews` 只含 review 正文，不含 inline 评论，inline 评论单独取：

```bash
gh api repos/FinAI-Project/<repo>/pulls/<number>/comments --paginate \
  --jq '.[] | {id, path, line, commit_id, in_reply_to_id, created_at, body, user: .user.login}'
```

每条 review 对应的 commit 用下面的命令取，用于判断意见提出时的代码与当前 head 是否相同：

```bash
gh api repos/FinAI-Project/<repo>/pulls/<number>/reviews \
  --jq '.[] | {id, user: .user.login, state, commit_id}'
```

### 2. 拉取 diff

```bash
gh pr diff <number> --repo FinAI-Project/<repo>
```

### 3. 读取意见所涉的代码

按 `reading-source.md` 读取。范围限于意见指向的文件，以及评估它们所必需的类型实现，不读 diff 之外与意见无关的代码。

### 4. 逐条评估

- 来源标签：账号名在前，类型标签紧随。`<login> [🤖]` 表示 AI bot，`<login> [👤]` 表示人工。
- Gemini、Codex 等自动摘要类 review 正文不含具体意见，注明后跳过：`<login> [🤖] 自动摘要（不评估）：<一句话概括>`。
- 含具体意见的，每条先用一句话说明这条意见在说什么，再给出：原文关键段落、评估、理由、处理状态。
  - 评估取值：成立、不成立、部分成立。
  - 理由基于对源码的实地验证，不凭描述推断；涉及外部工具行为而未核实的，明标"未核实"。
  - 处理状态取值：已处理、未处理、不需要处理。意见对应的 commit 与当前 head 不同时，核对其后的改动是否已处理该意见。
- 对 review 状态（如 `CHANGES_REQUESTED`）和评论自带的严重程度标记，如实转述，并说明评估结论是否支持该标记。
- 每条意见先按 `user-review` skill「回复规范」中的职责范围原则判定是否属于本 PR 的职责；范围外的处理状态记"不需要处理"，给出 PR 之外的处理手段，不列入合并前必须处理的项。

### 5. 汇总

回复末尾给出总体结论：哪些意见需要在合并前处理，哪些可以不处理，各自的依据。

### 6. 写回复并验收

按 `user-explain` skill 的流程写回复，读者缺的前提先补上；写完后过 `user-explain/checklist.md` 全部项，再过下面的接口验收项，任何一项为否就改写。

1. 每条意见是否先有一句话说明它在说什么？
2. 意见和评估中读者可能不熟悉的概念，首次出现时是否已解释？
3. 每条评估的理由是否有源码依据，并带文件与行号？
4. 处理状态是否核对了意见对应的 commit 与当前 head？
5. 回复是否只含本接口的内容，没有混入独立代码审查？
6. 每条意见是否先判定了职责范围，范围外的是否给出了 PR 之外的处理手段？

## 边界

- 读代码时发现意见之外的问题，不在本接口展开，只在末尾用一句话提示可用 review 接口。
- 不发评论、不回复意见。
