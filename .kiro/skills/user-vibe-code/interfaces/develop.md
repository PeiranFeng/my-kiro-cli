# 接口：develop

在约束下写或改代码。新增功能、修改功能、处理外部输入、修复缺陷共用这套步骤，差异见末尾。

## 步骤

1. 确认开发位置：开发前向用户确认目标仓库，以及本次开发对应的分支、PR 或 issue，新建分支时还有基线，缺哪项只问哪项（`40-git-safety.md#identify-repo`）。确认后按下方"临时 clone"建立开发目录，此后的读改、提交都在其中进行，不改动 `~/data/<repo>` 下的原仓库。
2. 方案关卡（硬性）：写任何代码之前，对开发计划执行一次 `interfaces/plan-review.md`。结论为"需修改"或"需确认"时停止，向用户汇报发现，不写代码；方案改完并重新评估得到"通过"后才进入步骤 3。
3. 定范围：复述用户已确认的方案，只实现它，并把任务转成可验证的完成标准（`principles/scope.md`）。需求有多种解读时列出并请用户选。
4. 看周边：读被改动处的上下游与同类代码，记下既有的命名、工具函数、错误处理与测试写法（`principles/repo-conventions.md`）。
5. 查前提：对代码要消费的每份数据，按 `interfaces/premise.md` 的方法确认其契约及强度；改动很小、不涉及新的数据消费时可略。
6. 写最小实现：沿用周边的写法与已有的工具函数，不新增并行机制。
7. 过三问：对每一处想加的校验、try/except、默认值、兜底、可选参数，按 `principles/defensive.md` 决定去留；形态与失败方式按 `principles/failure.md`。
8. 写测试：按 `interfaces/testcase.md` 为保留的 guard 与新行为写用例。
9. 交出前打分：按 `objects/代码.md` 与 `objects/测试.md` 列项，按 `checklist.md` 的一、三、四逐项打分；答"否"的回到对应步骤修改，答不上的 guard 和不能追溯到需求的新增删除；需要偏离计划时，回到 plan-review 重新评估。
10. 回复：呈现下方"回复内容"。
11. 推送与清理：推送前把分支与提交内容给用户确认（`40-git-safety.md#confirm-remote-ops`、`#pre-push-checks`）；推送完成后询问用户是否删除这个临时 clone，得到明确同意才删除。

## 临时 clone

- 位置：`$DEV_CLONE_ROOT/<repo>-<分支名，斜杠换成短横>`，`DEV_CLONE_ROOT` 取自 `.kiro/local-context.sh`。目录已存在时，先告知用户并询问复用还是另建，不覆盖。
- 建立：`git clone --recurse-submodules "$(git -C ~/data/<repo> remote get-url origin)" <目录>`，远程地址取自原仓库。随后按 `40-git-safety.md#fetch-before-checkout` 先 fetch 再检出：已有分支、PR 的头分支直接检出；新分支从用户确认的基线创建，基线在步骤 1 一并确认。含 submodule 的仓库，submodule 的指针与联合开发按 `user-update-submodule` skill。
- 运行：测试与实验仍在仓库之外的输出目录运行（`50-project-facts.md#no-run-in-repo`），临时 clone 也算仓库目录。
- 删除：只在推送完成且用户明确同意后执行；删除前用 `git -C <目录> status --short` 与 `git -C <目录> log @{u}..` 确认没有未提交或未推送的内容，有则列出并再次询问。

## 轻量路径

单点修改、不新增数据消费、不新增 guard 时，步骤 2 与步骤 9 只对 `checklist.md` 一中的范围、复用与框架、防御与失败三组打分，其余只执行步骤 1、3、4、6、10、11，回复一句话说明沿用了哪处写法。

## 回复内容

- 代码依赖的数据契约、依据与强度，每份一句。
- 保留的每个 guard 及其触发路径，每个一句。
- 沿用的既有写法所在的位置。
- 步骤 2 的 plan-review 与步骤 9 的打分中发现并已修正或交用户确认的问题，每个写问题、处理方式和它违反的原则（标注方式同 `interfaces/code-review.md`）；没有问题时不写。
- 契约无法查证而需要用户确认的点，只问那一项。

## 场景差异

- 处理外部输入：这是信任边界，校验集中在入口处一次完成，通过后内部按契约使用；校验失败按 `principles/failure.md` 报出具体违反项。
- 修复缺陷：先写出能复现缺陷的用例并确认失败；定位根因所在的一方（生产方违反契约，或消费方误解契约），在根因处修；不在下游加兜底来掩盖症状。
- 清理、去重、重构：保持行为不变，没有测试作对照时只报告；规则见 `principles/repo-conventions.md`。
- 修改既有功能：在被改动的函数内保持结构完整，不为了让改动最小而叠加补丁；范围之外的重构先问用户。
