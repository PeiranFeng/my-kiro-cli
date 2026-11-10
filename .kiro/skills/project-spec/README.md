# project-spec 使用说明

把自然语言需求变成目标仓库 `docs/` 下与代码镜像的文档，按已批准的文档开发代码，并持续检查文档与代码是否一致。你负责目标、取舍和验收语义，skill 负责把它们落成文档和代码。

## 工作流程

```text
需求 → 架构与用例 → 代码
 ↑审核    ↑你批准      ↑你批准后才开发
```

- 每份文档有状态：`draft`（待审查）→ `approved`（你已批准）→ `implemented`（代码和测试已完成）。
- 下游只读上游已批准的文档；修改任何文档都会把它改回 `draft`。
- 已有代码的仓库从 `bootstrap` 开始，方向相反：代码 → 架构 → 需求，见下文「bootstrap」。

## 命令

| 命令 | 作用 |
|------|------|
| `help` | 介绍本 skill 的功能，内容取自本文件，并列出五类原则的现状 |
| `bootstrap` | 读取现有仓库，生成三棵文档树和结构文档，全部为 draft；结束时自动自查并修改一轮 |
| `requirements <描述>` | 先审核需求是否已满足、是否可行、skill 是否胜任、是否清晰，通过后才写需求文档 |
| `architecture [要求]` | 为已批准的需求设计架构，写 source 文档、结构文档和用例 |
| `approve [范围]` | 批准 draft 文档；含「待确认」或校验错误的文档不会被批准 |
| `build` | 按已批准的架构和用例写代码与测试 |
| `maintain` | 检查整个项目的文档与实现是否一致，写 `.project-spec/maintain-report.md` |
| `review [范围]` | 按原则审查本次设计或代码 |
| `review bootstrap` | 审查 bootstrap 产出的文档是否忠实于代码与架构；bootstrap 结束时自动执行并修改一轮 |
| `principle <描述>` | 新增、修改、删除或恢复开发原则 |

不点名命令时，skill 按你的意图选择。

## 文档

| 目录 | 内容 | 格式 |
|------|------|------|
| `docs/requirements/` | 按模块的功能点 | EARS 五种句式的原子条目 |
| `docs/architecture/` | 镜像源码树，每个源文件两份文档 | source 文档写职责、决策、约束；结构文档列出类和函数 |
| `docs/test-cases/` | 镜像架构树 | 声明式 Given、When、Then 场景 |
| `.project-spec/` | 校验报告、检查报告、review 报告 | 加入 `.gitignore` |

结构文档 `<文件名>.structure.md` 由脚本从代码生成，说明文字取自 docstring。格式细节和来源见 `references/templates.md`，目录约定见 `references/doc-layout.md`。

## bootstrap

`bootstrap` 只依据现有仓库，架构忠实反映代码现状，需求忠实抽象架构，不美化。需求是从实现推断的，不是你提出的，需要你审查时确认意图。

- 结构文档由脚本从代码生成；source 文档、用例和需求由 Agent 依据代码和架构撰写。
- 现状违反设计原则之处不改写进文档，记入 `.project-spec/bootstrap-report.md`。
- 结束时自动执行 `review bootstrap`：双向核对代码、架构、需求是否一致，并报告覆盖范围；文档与现状不符的发现会修改一轮，现状本身的问题只记入报告。规则见 `references/bootstrap-review.md`。
- 你也可以随时单独运行 `review bootstrap`，再运行普通 `review` 评判现状的设计质量。

## 需求审核

`requirements` 会对不合理的需求说不：已经满足的、很难实现的、skill 无法胜任的，会告诉你原因；描述不清晰时会不断提问，直到你想清楚。你尚未想好时可以明确要求先出一版看看，得到的是一份带「待确认」的 draft 小样。详见 `references/requirements.md`。

## 自定义原则

原则放在 `references/principles/` 的五个目录：`requirement`、`architecture`、`code`、`test`、`review`，每个原则一个文件。用 `principle` 命令新增、修改、删除或恢复；删除的原则进入 `trash/`，可以恢复。review 清单自动取自这些文件。详见 `references/principles/README.md`。

## 脚本

脚本都只用 Python 标准库，路径相对本目录。

| 脚本 | 作用 |
|------|------|
| `scripts/validate_spec.py --project-root <仓库>` | 校验文档结构、引用、需求句式，并核对 implemented 文档与代码 |
| `scripts/gen_structure.py --project-root <仓库> [--write]` | 列出或写入缺失、过期的结构文档，仅支持 Python 源码 |
| `scripts/list_probes.py --project-root <仓库>` | 列出以字符串字面量指向仓库内函数或类的调用，供 `review bootstrap` 枚举能力探测 |
| `scripts/principle.py list｜check｜add｜update｜remove｜restore` | 管理原则文件 |

## 测试

```text
python3 -m unittest discover -s tests
```

## 文件索引

| 文件 | 内容 |
|------|------|
| `SKILL.md` | skill 入口：命令、状态、依赖、安全规则 |
| `references/docs-commands.md` | bootstrap、architecture、approve 的步骤 |
| `references/requirements.md` | requirements 的准入审核与小样 |
| `references/build.md` | build 的步骤 |
| `references/maintain.md` | maintain 的检查项 |
| `references/review.md` | review 的范围、清单与输出 |
| `references/bootstrap-review.md` | `review bootstrap` 的忠实性原则、方法与修改策略 |
| `references/doc-layout.md` | 文档树、frontmatter、引用关系 |
| `references/templates.md` | 各类文档骨架与格式来源 |
| `references/principles/` | 五类原则 |
