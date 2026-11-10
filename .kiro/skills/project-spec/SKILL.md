---
name: project-spec
description: 把自然语言需求编译成目标仓库 docs/ 下与代码结构镜像的需求树、架构树和测试用例树，按已批准的架构开发代码，并检查文档与实现的一致性。当用户要求初始化 repo 文档、写或改需求、设计或改架构、批准文档、按文档开发、检查项目一致性、review 设计或代码、新增、修改、删除或恢复开发原则时使用。
---

# project-spec

用户负责目标、关键取舍和验收语义；本 Skill 把它们写成三棵与代码镜像的文档树，再按文档开发代码。

执行前声明"依据 project-spec skill"。

## 命令

| 命令 | 输入 | 写 | 细节 |
|------|------|----|------|
| `help` | 无 | 无，向用户介绍功能 | `README.md` |
| `bootstrap` | 无，只读当前仓库 | 三棵树（draft） | `references/docs-commands.md` |
| `requirements <自然语言>` | 自然语言 | 需求树（draft），经准入审核；用户明确要求时可写含待确认项的小样 | `references/requirements.md` |
| `architecture [要求]` | approved 的需求，可附自然语言要求 | 架构树和用例树（draft） | `references/docs-commands.md` |
| `approve [scope]` | 默认全部 draft | 只改 status：draft → approved | `references/docs-commands.md` |
| `build` | approved 的架构和用例 | 代码、测试，status：approved → implemented | `references/build.md` |
| `maintain` | 全部文档与代码 | `.project-spec/maintain-report.md` | `references/maintain.md` |
| `review [scope]` | 本 session 的 design 或 code | `.project-spec/reviews/` | `references/review.md` |
| `principle <描述>` | 用户要新增、修改、删除或恢复的原则 | `references/principles/<目录>/` | `references/principles/README.md` |

`help` 读取 `README.md`，按用户关心的部分简短介绍命令、流程和自定义方式；再运行 `scripts/principle.py list --summary`，按分类列出现有原则（ID 名词短语：摘要）。不写任何文件，内容不在此重复。

用户没有点名命令时按意图选择：询问功能或用法用 `help`；仓库还没有 `docs/project-spec.json` 或要求从代码整理文档用 `bootstrap`；描述要做什么用 `requirements`；要求设计实现方式用 `architecture`；表示批准用 `approve`；要求开发用 `build`；要求检查整个项目一致性用 `maintain`；要求审查本次工作用 `review`；新增、修改、删除或恢复开发原则用 `principle`。

## 状态与依赖

每个文档的 `status` 取三值：

- `draft`：最近一次 `bootstrap`、`requirements` 或 `architecture` 的产出，等待批准。
- `approved`：已批准，等待下游处理。
- `implemented`：下游已完成。架构和用例文档表示代码和测试已实现并通过；需求表示满足它的架构全部 implemented。

依赖链是需求 → 架构与用例 → 代码：

- `architecture` 只读 approved 和 implemented 的需求，draft 需求不作为输入。
- `build` 只处理 approved 的架构和用例文档。
- `requirements` 或 `architecture` 修改任何文档，都把它改回 `draft`。
- 审查 draft 是作者的义务。每个命令开始和结束时，若校验报告的 `drafts` 非空，提醒用户审查并 `approve`；只提醒，不拒绝执行。

## 自动 review

`bootstrap`、`requirements`、`architecture` 校验通过后，以及 `build` 完成后，各自动执行一次 `review`，只给用户简短反馈，不阻塞流程。`bootstrap` 之后还要按 `references/docs-commands.md` 根据发现修改文档。

## 文档结构与原则

```text
<repo>/docs/project-spec.json   模块到源码目录和测试目录的映射
<repo>/docs/requirements/       按模块组织的功能点
<repo>/docs/architecture/       镜像源码树，一个公开源文件一个 source 文档和一个 structure 文档
<repo>/docs/test-cases/         镜像架构树
<repo>/.project-spec/           校验报告和检查报告，加入 .gitignore
```

- 结构规则见 `references/doc-layout.md`，文档骨架和格式来源见 `references/templates.md`，写文档前读取。
- structure 文档由 `scripts/gen_structure.py` 从代码生成：`--project-root <目标仓库>` 列出缺失或过期的文档，加 `--write` 写入。
- 设计、编码、写测试时遵守 `references/principles/` 中 stage 匹配的原则，review 以它们为清单；需求的写法和准入审核见 `references/requirements.md`。
- 宿主项目的规则是补充，与本 Skill 冲突时以宿主为准。

## 目标仓库

1. 用户给出路径时以该路径为目标，相对路径从当前工作目录解析。
2. 否则使用 `git rev-parse --show-toplevel`。
3. 仍不能唯一确定时只询问目标路径。

Skill 安装目录、用户主目录、上一次处理的仓库都不能成为隐式目标。涉及多个仓库时，每个仓库独立维护自己的 `docs/` 和 `.project-spec/`，文件引用不跨仓库。

## 安全

不修改 Git 历史、远程分支、Issue、PR 或部署环境；不覆盖或回退开始前已存在的用户改动。用户另外要求 commit、push 或开 PR 时，先展示内容并遵循目标仓库的 Git 规则。

## 校验

每次修改文档后运行：

```text
<python> <本-Skill目录>/scripts/validate_spec.py --project-root <目标仓库>
```

选择本机已有的 `python3`、`python` 或 Windows `py -3`，不安装依赖。报告写到 `.project-spec/validation.json`：

- `errors`：文档结构或引用错误，退出码 1。不得为通过校验删除或弱化有效需求与用例。
- `inconsistencies`：implemented 文档与代码对不上，供 `maintain` 使用。
- `unmappedSources`：没有架构文档的源文件，供 `maintain` 判断是否公开。
- `drafts`：全部 draft 文档 ID，供各命令提醒作者。
- `paths`：每个文档对应的源码或测试路径。
- `specFingerprint`：排除 status 行后的文档指纹。

## 汇报

简短汇报命令、目标仓库、改动的语义（不是文件清单）、校验结果、自动 review 结论和下一步命令。测试未运行时写"未验证"。
