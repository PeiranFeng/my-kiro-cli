# 接口：requirement

验证 PR 的需求与方案本身是否成立，与代码是否有 bug 无关。只在回复里呈现，不写文件。不读取也不评估 GitHub 上已有的 review 意见，以保持独立。

## 步骤

### 1. 拉取元数据与 diff

```bash
gh pr view <number> --repo FinAI-Project/<repo> \
  --json number,title,url,state,body,author,headRefName,baseRefName,headRefOid,closingIssuesReferences

gh pr diff <number> --repo FinAI-Project/<repo>
```

PR 正文、`closingIssuesReferences` 与正文里引用的 issue 都是需求的出处，逐个用 `gh issue view <number> --repo FinAI-Project/<repo>` 取正文。

### 2. 提炼需求与方案

先用两句话以内写出：这个 PR 要解决什么问题（需求），打算怎么解决（方案）。提炼依据是出处文本与 diff，二者不一致时以 diff 为方案、出处为需求。

### 3. 五个维度逐项验证

读取源码按 `reading-source.md`。每个维度有且只有一个结论：通过、存在问题、无法核实。无法核实的写明缺什么信息。

1. 来源：需求在 issue、PR 正文或其他可追溯文本中的出处；出处不可追溯则为无法核实。
2. 前提：把需求依赖的事实写成命题，逐条用源码、数据或文档验证；数据取值类前提按 `user-vibe-code` 的 premise 接口验证。
3. 副作用：沿被改动的符号找 base 分支上的调用方与下游消费者，核对公开接口、输出结构、行为、性能的变化是否带来新问题。
4. 达成度：把需求逐条对应到 diff 中的实现，找出未被实现的需求与超出需求的改动。
5. 方案最优性：独立构造至少一个替代方案，按速度、简单度、优雅度与 PR 方案比较，替代方案必须在已核实的物理与环境限制内可行；只有替代方案在某维度更优时才记为问题，并写明替代方案与依据。

### 4. 写回复并验收

按 `user-explain` skill 的流程写回复，读者缺的前提先补上；写完后过 `user-explain/checklist.md` 全部项，再过下面的接口验收项，任何一项为否就改写。

1. 五个维度是否都有且只有一个结论？
2. 存在问题的维度是否都带依据（文件与行号、issue 编号或数据），并先说是什么、再说为什么是问题？
3. 无法核实的维度是否写明了缺什么信息？
4. 最优性的问题是否给出了具体的替代方案？
5. 回复是否没有引用或评估 GitHub 上已有的 review 意见，也没有混入 `[review]` 代码检查项？

## 边界

- 不发评论、不提交 review。
- 代码层面的 `[review]` 检查项属于 review 接口。
