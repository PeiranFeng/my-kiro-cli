# 文档骨架

Agent 填充这些骨架。没有内容的段落直接删除，不保留空标题，不为填满模板制造内容。

## 功能点或约束

路径：`docs/requirements/<module>/<feature>.md`，项目级放在 `docs/requirements/<feature>.md`。

```markdown
---
id: req.<module>.<feature>
kind: requirement
status: draft
---

# <功能点名称>

## 需求

- r1 <需求条目。>

## 待确认

- <只列影响语义的未决问题。>
```

每条需求是一句话、一件事，编号 `r<n>` 在文件内唯一。句式取自 EARS，必须是下列五种之一，校验器逐条核对：

| 类型 | 句式 |
|------|------|
| 通用 | `<主体>应<可观察结果>。` |
| 事件 | `当<触发>时，<主体>应<可观察结果>。` |
| 状态 | `在<状态>期间，<主体>应<可观察结果>。` |
| 异常 | `若<异常条件>，则<主体>应<可观察结果>。` |
| 可选 | `在具备<特性>的情况下，<主体>应<可观察结果>。` |

约束把 `kind` 改为 `constraint`，格式相同，范围是跨模块的行为。

## 模块总览

路径：`docs/architecture/<module>/README.md`。子目录总览把 `kind` 改为 `package`。

```markdown
---
id: arch.<module>
kind: module
status: draft
requirements: []
depends-on: []
---

# <模块名称>

## 职责

<模块独立承担的职责，以及它负责和不负责的范围。>

## 结构

<模块内各公开源文件的分工，以及它们如何协作完成模块职责。>

## 依赖

<依赖的其他模块、方向和原因。>
```

## 源文件

路径：`docs/architecture/<module>/<path>/<stem>.md`，对应源文件 `<source>/<path>/<stem><suffix>`。

```markdown
---
id: arch.<module>.<stem>
kind: source
status: draft
requirements: ["req.<module>.<feature>"]
depends-on: []
---

# <stem>

## 职责

<该文件封装的数据、提供的行为、对数据的约束。>

## 决策

### d1 <决策标题>

- 背景：<驱动该决策的需求与约束。>
- 候选：<至少一个被放弃的方案及其代价。>
- 决定：<采用的设计模式或算法。>
- 后果：<得到什么，付出什么。>

## 约束

- <接口 ID 或符号> 不变量：<所有调用都成立的性质。>
- <接口 ID 或符号> 错误：<错误类别和触发条件。>

## 待确认

- <会改变边界或契约的未决问题。>
```

签名、参数、返回类型只写在同路径的结构文档，本文件不重复。算法依赖的数据特性及其保障级别写进「约束」。没有真实取舍的文件省略「决策」。

## 结构文档

路径：`docs/architecture/<module>/<path>/<stem>.structure.md`，与同路径的源文件文档并列。

````markdown
---
id: struct.<module>.<stem>
kind: structure
status: draft
---

# <stem> 结构

> <模块说明。>

## 模块变量

```python
<名称>: <类型>  # <说明>
```

## <类>(<基类>) {#api.<module>.<stem>.<symbol>}

> <类说明。>

```python
<属性>: <类型>  # <说明>
```

### <类>.<方法> {#api.<module>.<stem>.<symbol>.<method>}

```python
<装饰器>
def <方法>(<参数>) -> <返回类型>  # <说明>
```

## <函数> {#api.<module>.<stem>.<symbol>}

```python
def <函数>(<参数>) -> <返回类型>  # <说明>
```

## 动态探测

| 位置 | 调用 | 目标名 |
| --- | --- | --- |
````

- 内容由 `scripts/gen_structure.py` 从代码生成：公开的模块变量、类、方法、函数按声明顺序排列，说明取自 docstring 首句或行尾注释，缺失时写 `(无说明)`；没有内容的小节省略。
- 设计阶段代码尚不存在，由 Agent 按本模板手写；代码实现后，校验器把 implemented 的结构文档与脚本输出逐项比对，结构不同即不一致，说明文字不参与比对。
- 「动态探测」列出代码中 `getattr`、`hasattr` 以字符串字面量探测的名字，使未在基类声明却被依赖的能力可见。
- 接口锚点 `{#api.…}` 只出现在本文件。

## 接口用例

路径与源文件文档相同，位于 `docs/test-cases/` 下；对应测试文件由模块配置的 `testFile` 推出。

```markdown
---
id: cases.<module>.<stem>
kind: cases
status: draft
verifies: ["req.<module>.<feature>"]
---

# <stem> 用例

## <公开类或函数> {#cases.<module>.<stem>.<symbol>}

### <场景名：用它独有的可观察结果命名>

Given <只写必要的前置条件>
When <唯一的触发动作>
Then <可观察结果>
```

每个场景只验证一个行为点，只有一个 When。取值不同而行为相同的场景合并为一张表，列为输入与期望，场景只写一次。场景按正常、异常、边界、状态转换、安全与一致性的顺序排列，没有对应语义的类别不写。

## 联合流程

路径：targets 最近公共目录下的 `journeys/<name>.md`。

```markdown
---
id: journey.<scope>.<name>
kind: journey
status: draft
targets: ["api.<...>", "api.<...>"]
verifies: ["req.<...>"]
---

# <流程名称>

## 参与者与目标

<外部参与者、目标和跨越的边界。>

## 成功流程

1. <接口调用及其结果。>

## 失败与恢复

- <失败点、补偿、重试和最终状态。>

## 跨边界不变量

- <幂等、一致性、顺序或安全性质。>
```

## 一致性报告

路径：`.project-spec/maintain-report.md`；bootstrap 发现的差异写入 `.project-spec/bootstrap-report.md`，格式相同。

```markdown
# 一致性报告

## 结构

- <违反结构规则的文档，或缺少文档的公开源文件；证据；处理方向。>

## 需求与架构

- <需求 ID、未被满足的验收条件、证据、处理方向。>

## 架构与代码

- <接口 ID、签名或行为差异、证据、处理方向。>

## 用例与测试

- <用例小节 ID、缺失或不符的测试、证据、处理方向。>

## 无法验证

- <缺失的环境、测试或外部依赖。>
```

## 来源

- EARS 句式与原子需求：Mavin 等，Easy Approach to Requirements Syntax，2009。
- 构件视图与代码层：arc42 第 5 节 Building Block View；C4 模型的 code 层。
- 决策条目：Nygard 的 Architecture Decision Records，及其 Markdown 形式 MADR。
- 场景写法：Gherkin 与 Cucumber 的 Better Gherkin 指南，声明式、一场景一行为。
