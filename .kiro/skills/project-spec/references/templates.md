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

## 目标

- <参与者与触发条件。>
- <系统可观察行为及其价值。>

## 验收条件

- <可验证的结果。>

## 边界

- <错误、权限、容量、时序或兼容性边界。>

## 待确认

- <只列影响语义的未决问题。>
```

每节都分条列出，每条限一到两句话（原则 Q3）。约束把 `kind` 改为 `constraint`，正文分条写明适用范围和验证方法。

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

## 设计

<采用的设计模式、满足哪些功能点、选择理由与放弃的候选方案；算法依赖的数据特性及其保障级别。>

## <公开类或函数> {#api.<module>.<stem>.<symbol>}

<签名。>

- 输入：<参数、类型、约束和默认语义。>
- 输出：<结果及其保证。>
- 错误：<错误类别和触发条件。>
- 副作用：<状态修改、事件和外部调用。>
- 不变量：<所有调用都成立的性质。>

### <方法> {#api.<module>.<stem>.<symbol>.<method>}

<同上，只写与所属类不同的部分。>

## 待确认

- <会改变边界或契约的未决问题。>
```

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

### <场景独有的条件>

Given <前置条件>
When <动作>
Then <可观察结果>
```

每个场景只验证一个行为点。场景按正常、异常、边界、状态转换、安全与一致性的顺序排列，没有对应语义的类别不写。

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
