---
name: project-maintainer
description: 依据 project-model 的已批准 Markdown 架构树与用例树审查、实现、测试和验证完整项目，并用文件状态支持中断恢复。当用户要求检查代码是否符合项目模型、落地已批准需求、补齐测试、自主修复失败、验证项目或继续被阻塞的维护工作时使用。
---

# project-maintainer

把 `project-model` 生成的已批准双树作为项目维护契约，执行代码 Review、实现、自动化测试和验证。规范语义由 `project-model` 维护；本 Skill 不替用户作新的需求或架构决策。

执行前声明“依据 project-maintainer skill”。

## 前置条件

目标仓库必须包含 `docs/project-model/architecture/` 和 `docs/project-model/use-cases/`，并安装可用的 `project-model` Skill。开始任何代码修改前，运行 `project-model/scripts/validate_model.py` 并保存 JSON 报告。

状态和报告遵循 `references/maintenance-contract.md`。首次执行前读取该文件；不要另造状态字段或完成标准。

## 模式

从用户意图选择模式：

- `review`：只读审查模型、代码和测试；只写 generated 报告，不修复代码。
- `implement`：按用户明确范围实现已批准模型，包含测试与修复循环。
- `verify`：运行结构、用例和回归验证；失败时报告，不修改代码。
- `maintain`：先 review，再实现确认范围内的缺口，最后 verify。
- `resume`：从已有 maintenance state 继续，先检查模型和工作区是否变化。

用户没有指定模式时：要求审查用 `review`；要求开发或落地用 `implement`；要求测试或验收用 `verify`；要求自主完成全部维护闭环用 `maintain`；要求继续上次工作用 `resume`。

## 仓库根解析与多仓任务

目标仓库解析顺序与 `project-model` 相同：用户明确路径优先；否则使用当前 Git 仓库的顶层目录；仍不能唯一确定时询问路径。Skill 的安装目录和上一次工作目录不能成为隐式目标。

默认一次 maintenance work 只属于一个仓库。其代码、模型、Git baseline、任务、证据、阻塞和状态全部保存在该仓库内，所有命令以该仓库为工作边界。

一次请求明确涉及多个仓库时：

1. 建立仓库根清单和跨仓依赖顺序。
2. 每个仓库使用自己的 `docs/project-model/`、模型指纹和 maintenance work-id。
3. 分别记录每个仓库开始与结束的 Git 状态。
4. 一个仓库失败或阻塞时，不把其他仓库状态标记为完成，也不把证据写入其他仓库。
5. 汇总报告只引用各仓库内部报告，不替代它们。

不得默认读取或写入目标集合之外的仓库。跨仓接口需要改变时，各仓库先分别通过 `project-model change` 更新自己拥有的契约，再进入实现。

## 权限边界

可以修改：

- 用户批准范围内的生产代码。
- 为已批准用例创建或修正的自动化测试。
- `docs/project-model/generated/maintenance/<work-id>/` 下的状态和报告。
- 架构节点的 `implementation` 与用例节点的 `automation` 字段，但只有对应文件和符号已经存在且经过核查时，才能机械更新映射。

不能修改：

- 节点 `id`、`kind`、`status`、`origin`。
- `requirements`、`depends-on`、`targets`、`verifies`。
- 需求、架构、接口和用例正文。
- 未获用户批准的 `draft` 节点。
- Git 历史、远程分支、Issue、PR、部署环境或生产数据，除非用户另外明确授权。

发现规范语义需要变化时，记录规格阻塞并交回 `project-model change`；不得先修改代码再倒推规范。

## Step 1 — 确定目标、范围和工作记录

1. 唯一确定目标仓库；无法确定时只询问路径。
2. 确定模式和范围。完整项目实施必须由用户明确要求；否则选择用户点名的模型 ID、目录子树或已批准变更。
3. 记录开始时的 Git 状态，区分用户原有改动与本次改动。
4. 为新工作生成稳定、可读的 `work-id`，创建 maintenance 目录与 `state.json`。
5. `resume` 使用已有 work-id，不创建重复工作；先读取 state、报告和未完成任务。

范围无法从模型 ID、目录或用户指令唯一确定时，先问清范围，不把所有未实现节点默认为本次任务。

## Step 2 — 校验并冻结模型快照

1. 运行 project-model 校验器，将报告写入本 work-id 目录。
2. 校验失败时写入规格阻塞并停止，不修改代码。
3. 检查范围内节点全部为 `approved`；`draft` 节点属于规格阻塞。
4. 把报告中的 `modelFingerprint` 和 `modelSemanticFingerprint` 写入 state。
5. 解析报告中的节点状态，确认 scope 只包含 `approved` 节点。
6. 解析范围内 requirement、constraint、架构节点、接口用例和相关 journey，形成显式追踪闭包。

`resume` 时重新计算指纹。指纹变化后保留已完成证据，重新检查其是否仍有效，并重新规划所有未完成任务；不能静默沿用旧模型快照。

## Step 3 — 建立可执行计划

把范围拆成有依赖关系的任务，每个任务必须列出：

- 要满足的架构节点和需求 ID。
- 要覆盖的接口用例和联合用例 ID。
- 预期修改文件。
- 定向测试和完成证据。
- 依赖的前置任务。

优先按可独立验证的纵向行为切分，不按“先写所有类、再写所有测试”横向切分。计划写入 `plan.md` 和 state 后再修改代码。

## Step 4 — review 模式

从四个方向审查：

1. 模型到代码：公开节点、签名、约束、依赖方向和实现映射是否成立。
2. 代码到模型：新增公开行为、跨边界调用和外部依赖是否有已批准来源。
3. 模型到测试：接口场景和 journey 是否有对应自动化或明确的未自动化原因。
4. 测试到模型：断言是否符合用例期望，是否存在通过修改预期掩盖行为偏差。

对“存在、不存在、通过、失败”的结论提供文件、符号或实际命令证据。发现项按阻断、重要、建议分类写入 `review.md`。review 完成表示审查工作完成，不表示项目没有问题；state 的 outcome 必须反映 `pass` 或 `findings`。

## Step 5 — implement 与 maintain 模式

逐个执行计划任务：

1. 读取对应接口用例和 journey，不从任务摘要猜测行为。
2. 先创建或定位能证明缺口的自动化测试，并实际观察预期失败；已有充分回归测试时记录其失败证据。
3. 实现满足当前任务的最小代码，不扩展范围。
4. 运行定向测试；失败时调查根因，代码问题进入有上限的修复循环。
5. 运行直接相关的组件、契约或联合用例。
6. 检查改动是否引入未批准的公开契约或依赖方向。
7. 更新任务状态和证据；只在文件与符号真实存在后更新 implementation/automation 映射。

默认最多连续修复三轮同一失败。仍失败时记录 implementation blocker，保留证据并停止该范围，不通过跳过测试、放宽断言或更改规范继续。

## Step 6 — verify 模式与最终验证

verify 本身只验证不修复。implement 和 maintain 在完成代码后执行同样的最终验证：

1. 再次运行项目模型校验并确认指纹对应当前规范。
2. 检查范围内架构与代码映射。
3. 运行每个接口用例的定向测试。
4. 运行相关 journey、组件和契约测试。
5. 运行项目约定的回归、构建、类型和静态检查；无法运行的检查明确标为未验证。
6. 使用独立上下文复核需求符合性、回归风险和测试缺口；宿主没有独立 subagent 时明确标记为 inline review。
7. 对比结束与开始 Git 状态，列出本次改动、用户原有改动和测试产物。

所有证据写入 `verification.md` 和 state。每次状态转换后必须运行 `scripts/validate_state.py` 并提供当前 `model-validation.json`；省略模型报告不构成有效校验。只有维护契约的完成门全部满足时，state 才能标记 `completed` 且 outcome 为 `pass`。

## Step 7 — 阻塞处理

阻塞分为：

- `specification`：需求、架构、用例、状态或追踪关系不完整或冲突。
- `environment`：缺少运行时、服务、凭据、硬件或测试数据。
- `permission`：所需写入、命令或外部操作未获授权。
- `implementation`：已批准行为明确，但有限修复后代码或测试仍失败。

写入 `blockers.md` 和 state，说明证据、已尝试操作、继续所需的最小动作。规格阻塞调用 `project-model change` 解决；环境和权限阻塞由用户或环境处理；实现阻塞可在新证据出现后 `resume`。

## Step 8 — 文件与 Git 安全

不覆盖、删除或回退开始前已存在的用户改动。不使用 reset、clean、checkout 覆盖文件或等价操作。本次创建的临时测试产物按项目约定放置；清理前核对其由本次工作创建。

不自动 commit、push、开 PR 或部署。用户另外要求这些操作时，先展示范围和内容并遵循目标仓库的 Git 规则。

## Step 9 — 汇报

汇报：

- 模式、work-id、范围和最终状态。
- 已满足与未满足的模型节点。
- 修改的代码和测试边界。
- 实际运行的命令、退出码和证据文件。
- 独立或 inline review 结果。
- 阻塞项及下一步是 `resume` 还是 `project-model change`。

测试未运行、环境缺失或证据过期时使用“未验证”，不能用“应当通过”。