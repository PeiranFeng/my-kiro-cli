# 接口：review

对线上 PR 的 diff 做独立代码审查。只在回复里呈现，不写文件。不读取也不评估 GitHub 上已有的 review 意见，以保持审查独立。

## 步骤

### 1. 拉取元数据与 diff

```bash
gh pr view <number> --repo FinAI-Project/<repo> \
  --json number,title,url,state,body,author,headRefName,baseRefName,headRefOid

gh pr diff <number> --repo FinAI-Project/<repo>
```

### 2. 阅读源码，理解改动

按 `reading-source.md` 读取。阅读目标：

1. 明确每个改动文件的职责和在架构中的位置。
2. 理解新增和修改代码的逻辑，包括做了什么、为什么。
3. 核对 review 检查项：扫描 steering 中的 `[review]` 标记（`grep -rn '\[review\]' .kiro/steering/`，方法见 `user-review` skill），逐条对这份 diff 给出结论，覆盖全部标记条目，每条有且只有一个结论：通过、存在问题或不适用。

### 3. 输出

- 变更摘要：改了哪些文件、各自职责、核心逻辑变化，基于源码阅读，不翻译 PR 正文。
- 逐条审查结论：按 steering 中的顺序逐项呈现，存在问题的注明文件与行号，并先说是什么、再说为什么是问题。不适用的一句话说明理由。全部通过写"各项均通过"。
- 描述代码行为遵循 `user-explain/principles/code-description.md`；引用具体方法或变量时让读者能定位其归属，不重复变更摘要已介绍过的类或模块信息。

### 4. 写回复并验收

按 `user-explain` skill 的流程写回复，读者缺的前提先补上；写完后过 `user-explain/checklist.md` 全部项，再过下面的接口验收项，任何一项为否就改写。

1. 每条 `[review]` 检查项是否都有且只有一个结论？
2. 存在问题的条目是否都带文件与行号，并先说是什么、再说为什么是问题？
3. 不适用的条目是否都有一句话理由？
4. 审查中的术语和概念，读者可能不熟悉的，首次出现时是否已解释？
5. 回复是否没有引用或评估 GitHub 上已有的 review 意见？

## 边界

- 需求与方案是否成立由 requirement 接口负责，本接口只审代码。
- 不发评论、不提交 review。
- 要查看已有的 review 意见时，用 comments 接口。
