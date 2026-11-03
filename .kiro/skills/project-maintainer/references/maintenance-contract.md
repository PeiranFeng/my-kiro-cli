# Project Maintainer 状态与证据契约

## 工作目录

每次独立维护工作使用：

```text
docs/project-model/generated/maintenance/<work-id>/
├── state.json
├── model-validation.json
├── plan.md
├── review.md
├── verification.md
└── blockers.md
```

`work-id` 使用稳定的小写 kebab-case。恢复已有工作时复用原目录；同一目标不能用新 work-id 绕过 blocked 或 verification-failed 状态。

## 仓库隔离

每个 maintenance work 绑定一个规范化仓库根。`state.json`、模型报告、任务、证据和阻塞只能描述该仓库的模型与文件；路径一律相对该仓库根。

多仓请求为每个仓库创建独立 work 目录。即使各仓库使用相同 `work-id`，状态也因位于各自 `docs/project-model/generated/maintenance/` 而隔离。跨仓汇总不能作为任一仓库的完成证据，任一仓库的 modelFingerprint 也不能写入另一仓库的 state。

## state.json

状态文件是中断恢复入口，使用严格 JSON：

```json
{
  "schemaVersion": 1,
  "workId": "<work-id>",
  "mode": "review",
  "status": "planned",
  "outcome": "not-run",
  "modelFingerprint": "sha256:<digest>",
  "modelSemanticFingerprint": "sha256:<digest>",
  "scope": {
    "architectureIds": [],
    "useCaseIds": []
  },
  "baseline": {
    "gitStatus": [],
    "head": null
  },
  "tasks": [],
  "blockers": [],
  "evidence": []
}
```

允许的 mode：`review`、`implement`、`verify`、`maintain`。

允许的 status：`planned`、`running`、`blocked`、`verification-failed`、`completed`。

允许的 outcome：`not-run`、`pass`、`findings`、`blocked`、`failed`。

状态转换：

```text
planned -> running
running -> blocked | verification-failed | completed
blocked -> running
verification-failed -> running
```

`completed` 是本 work-id 的终态。模型或范围改变后需要继续实现时创建新 work-id，并引用原 work-id；不能把已完成证据改写成新任务证据。

## scope

`architectureIds` 包含本次直接实现或审查的 requirement、constraint 和架构节点。`useCaseIds` 包含直接接口用例和影响闭包中的 journey。

范围使用模型 ID，不只记录文件路径。完整项目范围必须由用户明确要求。

## baseline

`gitStatus` 保存开始工作时逐行的 Git 状态；它不是干净工作区证明。`head` 在 Git 仓库中保存开始时的 commit ID，否则为 null。

结束时重新采集状态并区分：

- baseline 已存在的用户改动。
- state.tasks 中记录的本次改动。
- 测试或工具生成的产物。

## tasks

每个任务对象包含：

```json
{
  "id": "task-001",
  "title": "<可验证行为>",
  "status": "pending",
  "architectureIds": [],
  "useCaseIds": [],
  "dependsOn": [],
  "files": [],
  "evidenceIds": []
}
```

任务 status：`pending`、`running`、`passed`、`blocked`、`failed`。

任务只能在对应定向测试通过、相关模型检查完成且证据已记录后标记 `passed`。

## evidence

证据对象包含：

```json
{
  "id": "evidence-001",
  "kind": "focused-test",
  "command": "<实际命令>",
  "exitCode": 0,
  "result": "passed",
  "scope": ["<model-id>"],
  "outputRef": "<日志或报告相对路径>"
}
```

kind：`model-validation`、`focused-test`、`integration-test`、`regression-test`、`build`、`static-check`、`review`、`git-status`。

result：`passed`、`failed`、`not-run`。

命令必须是实际执行的命令；尚未执行时 `command` 说明计划检查且 `exitCode` 为 null。输出很长时把日志位置写入 `outputRef`，state 不复制完整日志。

每次状态转换后运行本 Skill 自带校验器：

```text
<python> <本-Skill目录>/scripts/validate_state.py --project-root <目标仓库> --state docs/project-model/generated/maintenance/<work-id>/state.json --model-report docs/project-model/generated/maintenance/<work-id>/model-validation.json
```

校验器退出非 0 时先修复状态记录；不能以损坏或指纹过期的 state 继续修改代码。

## blockers

阻塞对象包含：

```json
{
  "type": "specification",
  "summary": "<最小阻塞事实>",
  "evidenceRefs": [],
  "attempts": [],
  "requiredAction": "<继续所需动作>"
}
```

type：`specification`、`environment`、`permission`、`implementation`。

规格阻塞的 requiredAction 指向具体模型 ID 和需要 `project-model change` 决定的语义，不要求用户手工编辑 Markdown。

## 报告职责

### plan.md

记录范围闭包、任务依赖、预期文件、用例和每项完成证据。计划描述未发生的工作时使用肯定式。

### review.md

记录四向审查证据：模型到代码、代码到模型、模型到测试、测试到模型。发现按 blocking、important、suggestion 分类。

### verification.md

记录最终模型指纹、实际命令与退出码、接口用例、journey、回归检查、独立复核和 Git 状态归属。

### blockers.md

面向用户解释当前为何不能继续、现有证据、已经尝试什么和最小恢复动作。没有阻塞时可以不存在或明确写“无阻塞”。

## 完成门

implement 或 maintain 只有同时满足以下条件才能 `completed/pass`：

1. 当前模型校验通过，state 的完整指纹和语义指纹均与最新模型报告一致。
2. 范围内节点均为 approved，没有规格阻塞。
3. 所有任务为 passed。
4. 所有接口用例有自动化映射并通过定向测试。
5. 相关 journey、组件或契约测试通过。
6. 项目要求的回归、构建和静态检查通过；不适用项有证据说明。
7. 独立 review 没有未解决的 blocking 或 important 发现；inline review 被明确标记。
8. 结束 Git 状态已核对，本次改动与 baseline 用户改动可以区分。

review 模式完成时允许 `completed/findings`。verify 模式存在验证失败时使用 `verification-failed/failed`，不能用 completed/findings 弱化失败。

## 机械映射更新

project-maintainer 只能修改：

- 架构 frontmatter 的 `implementation`。
- 用例 frontmatter 的 `automation`。

更新前验证路径存在并定位到对应符号或测试。不得同时重排其他 frontmatter、改正文、改状态或改变语义关系。无法确定映射时写入 reconcile 或 verification 报告，不猜测。

## 模型快照保护

`modelSemanticFingerprint` 在开始修改代码前保存，用于机械保护规范语义。普通实现、测试和 `implementation`/`automation` 映射更新不得改变它。

机械映射更新后重新运行模型校验器，并将新的 `modelFingerprint` 写入 state；`modelSemanticFingerprint` 必须仍与初始值一致。若语义指纹变化，状态校验失败并停止代码修改。只有用户通过 `project-model change` 批准了新的规范，`resume` 重新计算影响范围并记录旧、新指纹后，才能把新语义指纹作为恢复基线。

模型报告中的 `nodes` 保存 ID 到状态的映射。状态校验器必须拒绝 scope 中不存在、`draft` 或 `deprecated` 的节点。
