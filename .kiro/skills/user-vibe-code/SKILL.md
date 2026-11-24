---
name: user-vibe-code
description: 给 AI 编程套一层约束，防止过度防御式编程、偏离仓库既有命名与写法、不必要的抽象导致项目熵增。分开发、review、写用例、前提验证、问题分析五个独立接口，运行测试转 user-run-tests。当用户要求写、改、补全代码，审查 AI 的开发是否过度防御或偏离仓库约定，设计或补写测试用例，验证代码所依赖数据的取值边界与前提，或要求自查多余的防御时使用。
---

# user-vibe-code

约束 AI 编程的行为，防止它为了"独立交出能跑的代码"而过度防御、另起炉灶、堆叠抽象。本文件只写接口的选择与共用规则；各接口的步骤在 `interfaces/`，通用原则、文献与公开实践的整理在 `principles/`，验收在 `checklist.md`，从实际案例归纳的 AI 开发原则库在 `domain/`。与 steering 重复的条目只在 `principles/` 里转述并给出锚点，原文以 steering 为准。

## 接口

接口相互独立，用户只要求其中一个时，只执行该接口，不顺带执行其他接口。

| 接口 | 做什么 | 输出 | 写文件 | 细则 |
|---|---|---|---|---|
| develop | 在约束下写或改代码 | 代码与回复 | 是 | `interfaces/develop.md` |
| review | 审查一份 AI 开发的改动是否违反本 skill 的原则 | 回复正文 | 否 | `interfaces/review.md` |
| testcase | 设计并写测试用例 | 测试代码与回复 | 是 | `interfaces/testcase.md` |
| premise | 验证代码所依赖数据的前提与取值边界 | 回复正文 | 否 | `interfaces/premise.md` |
| analysis | 分析一个已发现的 AI 开发问题，归纳出原则并追加到原则库 | `domain/ai-dev-problems.md` | 是 | `interfaces/analysis.md` |
| 运行测试 | 执行测试并读取结果 | 不属于本 skill | — | 用 `user-run-tests` skill |

选择接口的依据是用户的话：

- 要求写、改、补全、修复代码：develop。
- 要求审查、检查 AI 写的代码是否过度防御或偏离仓库写法：review。
- 要求设计或补写测试：testcase。
- 要求确认数据的取值范围、可空性、量纲、上游承诺：premise。
- 指出 AI 开发中的问题，或要求分析、记录某个问题：analysis。
- 仍无法判断时，只问用户要哪个接口。

## 与 user-review 的分工

`user-review` 按通用的代码设计原则（命名、注释、OOP、算法、测试覆盖等 steering 的 `[review]` 项）审查代码。本 skill 的 review 只审查 AI 开发行为本身的问题：过度防御、静默兜底、偏离仓库既有写法、无依据的抽象、没有独立期望值的测试。两者的检查项互不替代。

## 共用规则

- 只实现用户确认过的方案，范围见 `principles/scope.md`。
- 数据契约的查证与分级见 `principles/data-contract.md`，guard 的去留见 `principles/defensive.md`，失败方式见 `principles/failure.md`，与仓库既有写法保持一致见 `principles/repo-conventions.md`，测试设计见 `principles/testing.md`。
- 任何判断都要有依据：读过的代码、真实数据的统计或用户的说明；没有依据的，标"需确认"，不凭"可能"下结论。

## 写入限制

`domain/` 只存放从实际开发案例归纳出的原则，不记案例本身，由 analysis 接口追加，条目须通过 `interfaces/analysis.md` 的三关。文献与公开实践整理在 `principles/`，修改须经用户确认。
