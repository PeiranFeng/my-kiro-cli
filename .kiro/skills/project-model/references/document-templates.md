# Project Model 文档骨架

这些骨架由 Agent 填充。占位段落没有信息时删除，不保留空标题。

## 模型入口

```markdown
# 项目模型

## 当前状态

说明模型覆盖范围、批准状态和主要未决事项。

## 架构树

说明从 `architecture/` 开始浏览。

## 用例树

说明接口用例镜像规则和 `use-cases/journeys/` 的联合流程。

## 维护方式

说明使用自然语言调用 project-model 的 bootstrap、change、reconcile、approve 和 validate 动作。
```

## 需求或约束节点

```markdown
---
id: req.<scope>.<name>
kind: requirement
status: draft
origin: explicit
---

# <可观察目标>

## 目标

<参与者、条件、系统行为和业务价值。>

## 验收条件

- <可验证结果。>

## 边界

- <错误、权限、容量、时序或兼容性边界。>

## 待确认

- <只有影响语义的未决问题。>
```

约束节点把 `kind` 改为 `constraint`，正文说明所有适用范围和验证方法。

## 系统、领域、模块、组件或类节点

```markdown
---
id: arch.<scope>.<name>
kind: <system|domain|module|component|class>
status: draft
origin: inferred
requirements: ["req.<scope>.<name>"]
depends-on: []
implementation: []
---

# <节点名称>

## 职责

<该节点拥有的数据和提供的行为。>

## 边界

<该节点负责和不负责的范围。>

## 数据所有权

<拥有、读取和修改的数据。>

## 公开契约

<对外提供的接口、事件或数据模型。>

## 依赖

<依赖方向和原因。>

## 设计依据

<用户明确决策或 Agent 推荐设计及其约束。>

## 待确认

- <会改变边界或契约的未决问题。>
```

## 公开接口节点

```markdown
---
id: api.<scope>.<name>
kind: interface
status: draft
origin: inferred
requirements: ["req.<scope>.<name>"]
depends-on: []
implementation: []
---

# <接口名称>

## 职责

<调用者可观察的行为。>

## 输入

<字段、类型、约束和默认语义。>

## 输出

<成功结果及其保证。>

## 错误

<错误类别、触发条件和外部可观察结果。>

## 不变量

- <所有调用都成立的性质。>

## 副作用

<状态修改、事件和外部调用。>

## 兼容性

<版本、迁移和弃用承诺。>
```

## 镜像接口用例节点

文件相对路径与对应架构接口完全一致。

```markdown
---
id: cases.<scope>.<name>
kind: interface-cases
status: draft
origin: inferred
targets: ["api.<scope>.<name>"]
verifies: ["req.<scope>.<name>"]
automation: []
---

# <接口名称>用例

## 正常场景

### <场景名称>

Given <前置条件>
When <动作>
Then <可观察结果>
And <不变量或副作用>

## 异常场景

### <场景名称>

Given <前置条件>
When <动作>
Then <错误和状态结果>

## 边界场景

### <场景名称>

Given <边界条件>
When <动作>
Then <可观察结果>

## 安全与一致性

- <权限、隐私、幂等、并发或事务性质。>
```

没有实际语义的场景分类直接删除，不为填满模板制造用例。

## 联合用例节点

```markdown
---
id: journey.<scope>.<name>
kind: journey
status: draft
origin: inferred
targets: ["<architecture-id>", "<architecture-id>"]
verifies: ["req.<scope>.<name>"]
automation: []
---

# <联合流程名称>

## 参与者与目标

<外部参与者、业务目标和系统边界。>

## 成功流程

1. <接口或事件及其结果。>
2. <下一接口或事件及其结果。>

## 失败与恢复

- <失败点、补偿、重试和最终状态。>

## 跨边界不变量

- <幂等、一致性、顺序、安全或可观测性性质。>
```

## Reconcile 报告

```markdown
# 项目模型对齐报告

## 模型存在、代码未定位

- <模型节点 ID、预期位置和证据。>

## 代码存在、模型缺失

- <代码符号、位置和建议草稿节点。>

## 疑似不一致

- <接口签名或行为差异及证据。>

## 无法验证

- <缺失环境、测试或外部依赖。>
```
