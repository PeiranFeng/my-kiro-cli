---
name: user-vibe-code
description: 给 AI 编程套一层约束，防止过度防御式编程、偏离仓库既有命名与写法、不必要的抽象与模块结构失当导致项目熵增。分开发（develop）、方案评估（plan-review）、代码审查（code-review）、写用例（testcase）、前提验证（premise）、问题分析（analysis）六个独立接口，运行测试转 user-run-tests。当用户要求写、改、补全代码，评估开发方案或设计文档，审查 AI 写的代码是否过度防御、偏离仓库约定或结构失当，设计或补写测试用例，验证代码所依赖数据的取值边界与前提，或要求自查多余的防御时使用；通用的代码设计审查（steering 的 [review] 项）用 user-review。
---

# user-vibe-code

约束 AI 编程的行为，防止它为了"独立交出能跑的代码"而过度防御、另起炉灶、堆叠抽象。本文件只写接口的选择与执行流程。

| 目录 | 内容 |
|---|---|
| `interfaces/` | 各接口的触发、步骤与回复内容 |
| `objects/` | 被检查的对象（方案、代码、测试）：打分前要列出什么、读什么，用清单的哪几部分 |
| `principles/` | 原则，每节写规则、理由与常见形态 |
| `checklist.md` | 每种产物交出前的逐项打分，每项是"是/否"问题并注明出处原则 |
| `domain/` | 从实际案例归纳的 AI 开发原则库 |

原则只写在 `principles/`，打分项只写在 `checklist.md`，每个打分项末尾注明它出自哪条原则；`objects/` 只指定用清单的哪几部分，不复述打分项。各节"常见形态"的出处见 `principles/sources.md` 的"约束 AI 编程的公开实践"，成因为来源的解释，未经独立验证。与 steering 重复的条目只在 `principles/` 里转述并给出锚点，原文以 steering 为准。

## 接口

接口相互独立，用户只要求其中一个时，只执行该接口，不顺带执行其他接口。唯一的例外是 develop 开始前必须先执行 plan-review 作为关卡。

| 接口 | 做什么 | 输出 | 写文件 | 细则 |
|---|---|---|---|---|
| develop | 在临时 clone 中写或改代码；开始前先过 plan-review 关卡，推送后询问是否删除 clone | 代码与回复 | 是 | `interfaces/develop.md` |
| plan-review | 评估开发方案（specification、设计文档、实现步骤）是否满足编码约束 | 回复正文 | 否 | `interfaces/plan-review.md` |
| code-review | 审查一份 AI 开发的代码改动是否违反本 skill 的原则 | 回复正文 | 否 | `interfaces/code-review.md` |
| testcase | 设计并写测试用例 | 测试代码与回复 | 是 | `interfaces/testcase.md` |
| premise | 验证代码所依赖数据的前提与取值边界 | 回复正文 | 否 | `interfaces/premise.md` |
| analysis | 分析一个已发现的 AI 开发问题，归纳出原则并追加到原则库 | `domain/ai-dev-problems.md` | 是 | `interfaces/analysis.md` |
| 运行测试 | 执行测试并读取结果 | 不属于本 skill | — | 用 `user-run-tests` skill |

选择接口的依据是用户的话：

- 要求写、改、补全、修复代码：develop。
- 要求评估、审查方案、设计文档、实现步骤、迁移计划：plan-review。
- 要求审查、检查 AI 写的代码是否过度防御、偏离仓库写法或结构失当：code-review。
- 要求设计或补写测试：testcase。
- 要求确认数据的取值范围、可空性、量纲、上游承诺：premise。
- 指出 AI 开发中的问题，或要求分析、记录某个问题：analysis。
- 仍无法判断时，只问用户要哪个接口。

## 执行流程

1. 按用户的话选接口。
2. 按接口确定被检查的对象，读 `objects/` 中对应的文件，列出其中要求的各项。
3. 按 `checklist.md` 开头的表，对该产物逐项打分；答"否"的按接口写成发现，或回到开发步骤修改。
4. 交出评估结论或原则条目前，再按清单的五或六打分。

## 与 user-review 的分工

`user-review` 按通用的代码设计原则（命名、注释、OOP、算法、测试覆盖等 steering 的 `[review]` 项）审查代码。本 skill 的 code-review 与 plan-review 审查 AI 开发行为本身的问题：过度防御、静默兜底、偏离仓库既有写法、无依据的抽象、没有独立期望值的测试，以及方案与代码中模块之间的结构（`principles/structure.md`，类与方法层面的细审归 `user-review`）。两者的检查项互不替代。

## 共用规则

- 只实现用户确认过的方案，范围见 `principles/scope.md`。
- 数据契约的查证与分级见 `principles/data-contract.md`，guard 的去留见 `principles/defensive.md`，失败方式见 `principles/failure.md`，与仓库既有写法保持一致与框架取舍见 `principles/repo-conventions.md`，模块之间的结构见 `principles/structure.md`，测试设计见 `principles/testing.md`。
- 任何判断都要有依据：读过的代码、真实数据的统计或用户的说明；没有依据的，标"需确认"，不凭"可能"下结论。

## 写入限制

`domain/` 只存放从实际开发案例归纳出的原则，不记案例本身，由 analysis 接口追加，条目须通过 `interfaces/analysis.md` 的三关。文献与公开实践整理在 `principles/`，修改须经用户确认；新增原则时同时在 `checklist.md` 增加注明出处的打分项。
