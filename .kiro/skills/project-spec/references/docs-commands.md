# 文档命令

这些命令只写 `<文档根>` 和 `.kiro/project-spec/<仓库目录名>/`，不改代码和测试。写完都运行校验。

## 通用规则

- 内部区分用户明确要求、代码现状、推荐设计；不把后两者说成用户要求。
- `requirements` 的提问规则见 `requirements.md`。其他命令只在答案会改变模块边界、公开契约、数据所有权或验收语义，且无法从上下文推断时才提问；多个问题合并成一份简短摘要。
- 有未决问题的文档写 `## 待确认`。
- 以 ID 定位文档，不按标题猜测；移动文件不换 ID。
- 不覆盖与本任务无关的用户改动。
- 开始和结束时读取校验报告的 `drafts`；存在 draft 时提醒用户：审查并 `approve` 是作者的义务，未批准的内容不会进入下游。只提醒，不拒绝执行。

## bootstrap

不接收自然语言，只依据当前仓库。方向与开发流程相反：代码 → 架构 → 需求。架构忠实还原代码现实，需求从架构抽象而来。

先运行 `scripts/docs_cache.py prepare --project-root <目标仓库>`，按返回的 `state` 分支：

- `exact`：该提交的文档已存在，无需 bootstrap，告知用户。
- `none`：已创建空的文档根，按下面的全量步骤写入。
- `incremental`：已把基准提交 `base` 的文档复制到新文档根，只对返回的 `changes` 做增量 bootstrap，见后文。

### 全量步骤

1. 文档根没有 `project-spec.json` 时，识别模块：每个承担独立职责的代码目录是一个模块，写入配置。
2. 运行校验，读取 `unmappedSources`：依据代码为每个公开源文件生成 source 文档，缺少的模块 README 一并生成。structure 文档不手写，运行 `scripts/gen_structure.py --project-root <目标仓库> --write` 生成。source 文档遵守 `bootstrap-review.md` 的「架构忠实于代码」，只陈述现有的职责、约束和代码中可确认的决策；现状违反设计原则之处记入 `.kiro/project-spec/<仓库目录名>/bootstrap-report.md`，由 review 判断。
3. 为每个 source 文档写同路径 cases 文档：现有测试覆盖的接口，场景从测试归纳；没有现有测试的接口，在对应小节写明「无现有测试」，不虚构场景。
4. 依据架构文档（不再直接读代码）抽象模块需求点，写入需求树；需求遵守 stage 含 `requirement` 的原则和 `bootstrap-review.md` 的「需求忠实于架构」，只保留调用方可观察的行为，内部机制留在架构文档。需求是从实现推断的，不是用户提出的，`bootstrap-report.md` 记明这一点，由用户审查时确认意图。
5. 回填架构文档的 `requirements` 与 cases 文档的 `verifies`，把三棵树连通。
6. 已有 approved 或 implemented 文档不覆盖。代码与它们不一致时，把差异写入 `bootstrap-report.md`，由用户决定改文档还是改代码。
7. 新生成的文档全部为 `draft`。
8. 校验通过后执行一次 `review bootstrap`，按 `bootstrap-review.md` 的「修改」一节修改一轮，再重新校验。

### 增量步骤

`changes` 的每一行含变更状态、类别（source 或 test）、模块、路径，以及已存在的相关文档 `docs`。

1. source 的 A、M：运行 `scripts/gen_structure.py --project-root <目标仓库> --write` 更新结构文档；按变更更新 `docs` 列出的 source 文档与 cases 文档中受影响的陈述；`docs` 为空的新文件按全量步骤 2 至 3 生成文档。
2. source 的 D：删除 `docs` 列出的文档，并清理其他文档对它们的引用。
3. test 的变更：更新对应 cases 文档的场景和「无现有测试」标注。
4. 依据变化后的架构，只重新抽象受影响的需求。
5. 新增或移动了模块目录时更新 `project-spec.json`。
6. 被修改的文档改回 `draft`，未改动的文档保持复制来的 status；其余规则同全量步骤。
7. 校验通过后执行 `review bootstrap`，范围是本次改动与新增的文档，按 `bootstrap-review.md` 修改一轮并重新校验。

## architecture [要求]

1. 范围是 status 为 approved 的需求；draft 需求不作为输入，以及依赖它们的现有架构文档。
2. 对每个需求决定新增或修改哪些源文件，遵守 stage 含 `design` 的全部原则选择设计模式；为每个源文件写 source 文档和同路径 structure 文档（代码尚不存在，按 `templates.md` 手写），新增模块时同步写入配置和模块 README。
3. 为每个 source 文档写同路径 cases 文档，遵守 `principles/test/` 的原则覆盖每个接口；跨接口流程写 journey。
4. 被修改的 implemented 或 approved 文档改回 `draft`。
5. 运行校验，通过后自动 review。

## approve [scope]

1. 默认范围是全部 draft；用户点名时只处理点名范围。
2. 范围内有 `## 待确认` 或校验错误时不批准，指出最小阻塞项。
3. 只把 `status: draft` 改为 `status: approved`，再运行校验。
