# 原则目录

原则按分类放在本目录的子目录里，一个原则一个文件，文件名是原则 ID：

| 目录 | ID 前缀 | 分层名 | 管理的内容 |
|------|---------|--------|------------|
| `requirement/` | Q | Requirement | 需求的写法 |
| `architecture/` | A | Architecture | 架构设计 |
| `code/` | C | Code | 代码编写 |
| `test/` | T | Test | 测试用例覆盖 |
| `review/` | R | Review | review 的方法 |

每个目录里的原则都可以新增、修改、删除；删除是把文件移入 `trash/`，可以恢复。

## 文件格式

```markdown
---
id: <前缀><编号>
title: <名词短语>
summary: <一句话摘要>
stages: ["requirement", "design", "code", "test", "review"]
---

<原则正文。>
```

- `stages` 取值：`requirement` 写需求时生效，`design` 写架构时生效，`code` 写生产代码时生效，`test` 写用例文档和自动化测试时生效，`review` 约束 review 本身的方法。
- `title` 是名词短语，`summary` 是一句话摘要，二者都是单行；`help` 与 `list --summary` 输出「ID 名词短语：摘要」。
- 正文只写普适规则，不写具体例子。
- 新增原则的编号取该前缀在目录和 `trash/` 中的最大编号加一，已删除的编号不会被复用。

## 使用

- 写需求、架构、代码、测试时，遵守 `stages` 含对应阶段的全部原则，不论它在哪个目录。
- review 引用原则时写成「ID [分层名] 名词短语」。
- 列出：`python3 <本-Skill目录>/scripts/principle.py list [--stage <阶段>]`。
- 校验：`python3 <本-Skill目录>/scripts/principle.py check`，修改任何原则文件后运行。

## 维护原则

用户用 `principle` 命令新增、修改、删除或恢复原则，由 Agent 执行：

1. 阅读 `list` 的输出，定位涉及的原则。新增或修改后的原则与已有原则重复或矛盾时指出冲突，由用户决定合并、替换还是放弃。
2. 新增时依据用户的描述确定目录、`title`、`summary`、`stages` 和正文，修改时确定要改的项；其中任何一项无法从描述推断时，只问那一项。
3. 把正文写入私有临时文件，再运行对应子命令，脚本分配编号并写文件：
   - 新增：`scripts/principle.py add --category <目录> --title <标题> --summary <摘要> --stage <阶段> [--stage <阶段>] --body-file <临时文件>`
   - 修改：`scripts/principle.py update --id <ID> [--title <标题>] [--summary <摘要>] [--stage <阶段>] [--body-file <临时文件>]`，只改给出的项
   - 删除：`scripts/principle.py remove --id <ID>`，文件移入 `trash/<ID>.md`
   - 恢复：`scripts/principle.py restore --id <ID>`；`scripts/principle.py list --trash` 列出垃圾箱中的文件
4. 运行 `check`，向用户报告变更后的 ID 和路径。删除后告知用户该原则在垃圾箱中，可用 `restore` 恢复。
