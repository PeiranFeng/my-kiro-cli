# Project Model 契约

## 模型位置

目标仓库中的模型固定放在：

```text
docs/project-model/
├── README.md
├── architecture/
├── use-cases/
│   └── journeys/
└── generated/
```

## 仓库隔离

本契约中的所有路径都相对当前目标仓库根。每个仓库在相同相对路径 `docs/project-model/` 保存自己的模型，但内容、节点 ID 空间、校验报告和生成物彼此独立。

`implementation`、`automation`、模型报告路径和其他文件引用只能指向同一目标仓库内部。跨仓库依赖写成当前仓库模型中的外部契约说明，不使用 `../`、绝对路径或另一个仓库的本机路径建立文件引用。

处理多个仓库时，对每个仓库分别运行校验器并生成报告。报告只描述其 `--project-root` 指定的仓库，不能合并不同仓库的节点清单或指纹。

`architecture/` 和 `use-cases/` 是人可读、Agent 维护的事实源；`generated/` 是可删除重建的报告。

## 目录语义

`architecture/` 的目录表达系统、领域、模块、组件或类的所有权层级。需求放在对应层级的 `requirements/` 子目录；公开接口放在所属节点的 `interfaces/` 子目录。

`use-cases/` 尽量镜像 `architecture/`。每个未废弃的公开接口必须存在同相对路径的用例文件。跨接口、跨模块或跨仓库流程放在 `use-cases/journeys/`，不强行归入单个接口。

目录名和 Markdown 文件名使用小写 kebab-case。`README.md` 只允许作为模型总入口，不参与节点扫描。

## Frontmatter 子集

每个节点文件从第一行开始使用 YAML frontmatter。为保证 Python 标准库、Windows、Linux 和 macOS 解析结果一致，只使用以下子集：

- 标量写成单行 `key: value`。
- 列表写成单行 JSON 字符串数组。
- 不使用缩进对象、多行值、锚点、标签或注释。
- 键不能重复。

所有节点必需字段：

```yaml
---
id: <稳定小写点分 ID>
kind: <节点类型>
status: draft
origin: explicit
---
```

`id` 在两棵树中全局唯一，匹配 `^[a-z][a-z0-9]*(\.[a-z0-9][a-z0-9-]*)+$`。文件移动和标题变化不改变 ID。

`status` 取值：

- `draft`：Agent 提案或仍待用户确认。
- `approved`：用户明确批准的预期行为。
- `deprecated`：保留追溯但不再要求实现和覆盖。

`origin` 取值：

- `explicit`：来自用户明确要求。
- `inferred`：Agent 的推荐设计。
- `reconciled`：从已有代码或测试恢复的现状。

## 架构节点

`kind` 取值：

- `requirement`
- `constraint`
- `system`
- `domain`
- `module`
- `component`
- `class`
- `interface`
- `event`
- `data-model`

可选关系字段：

```yaml
requirements: ["req.<id>"]
depends-on: ["<architecture-id>"]
implementation: ["relative/path.ext#Symbol"]
```

规则：

- `requirements` 只能引用 `requirement` 或 `constraint` 节点。
- `depends-on` 只能引用架构树节点。
- 每个 `approved` 的 requirement/constraint 至少被一个未废弃架构节点的 `requirements` 引用。
- `implementation` 是目标仓库相对路径，可附加符号名；规划阶段允许为空。
- 文件引用统一使用 `/` 分隔，不写盘符、反斜杠、绝对路径或 `..`。

## 用例节点

`kind` 取值：

- `interface-cases`
- `component-cases`
- `journey`
- `quality-cases`

关系字段：

```yaml
targets: ["<architecture-id>"]
verifies: ["req.<id>"]
automation: ["relative/test/path.ext#TestName"]
```

规则：

- `targets` 至少包含一个未废弃架构节点。
- `verifies` 至少包含一个 requirement 或 constraint。
- 每个 `approved` requirement/constraint 至少被一个未废弃用例的 `verifies` 引用。
- `automation` 在设计阶段允许为空；为空时校验器给出警告，不判定模型无效。
- `interface-cases` 必须与目标 `interface` 节点同相对路径，并在 `targets` 中引用该接口 ID。

## 正文语义

需求节点陈述可观察行为、约束和验收条件。架构节点陈述职责、边界、公开契约、数据所有权、依赖和设计依据。接口用例按场景表达前置条件、动作、结果和不变量。联合用例按步骤引用多个目标接口并表达失败、补偿、幂等和一致性语义。

正文使用肯定式描述已决定的目标。未决问题集中写在 `## 待确认`，对应节点保持 `draft`。

## 有效模型

确定性校验通过表示结构和追踪关系成立，不表示架构正确或实现通过测试。模型进入代码维护前同时满足：

1. 校验器退出码为 0。
2. 本次实施范围内没有 `draft` 节点。
3. 所有重大待确认项已由用户决策。
4. 代码维护 Agent 读取的是当前提交或当前工作区中的同一份模型。

## 校验报告与模型指纹

校验器的 JSON 报告包含：

- `modelFingerprint`：按两棵树的路径和完整文件内容计算。
- `modelSemanticFingerprint`：使用同一输入，但排除架构节点的 `implementation` 和用例节点的 `automation` 行。
- `nodes.architecture` 与 `nodes.useCases`：节点 ID 到 `draft|approved|deprecated` 状态的映射。

同一模型得到同一 SHA-256 指纹。节点移动或语义内容修改会同时改变两个指纹；只更新真实实现和自动化测试映射会改变完整指纹，但保持语义指纹不变。

执行或恢复代码维护工作时保存该指纹。恢复前重新校验并比较；指纹变化表示规范已调整，维护 Agent 必须重新计算未完成任务的影响范围，不能沿用旧计划直接修改代码。

## 字段维护权

`project-model` 负责所有节点的语义和状态，包括正文、`id`、`kind`、`status`、`origin`、`requirements`、`depends-on`、`targets` 和 `verifies`。

`project-maintainer` 默认只读这些内容。它在实现或验证过程中可以机械更新 `implementation` 和 `automation`，前提是引用的真实文件与符号已经存在并经过核查；无法确定时保留空值并写入验证报告。任何会改变行为、边界或验收期望的调整都回到 `project-model change`。
