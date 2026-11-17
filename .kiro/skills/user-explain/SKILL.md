---
name: user-explain
description: 解释、回答、说明类回复的判断与写作流程，覆盖严格推导、因果机制、排查诊断、比较建议、结构说明、概念解释六类场景，另有 short、analysis、static、learn、embed 五个模式。当用户要求解释代码、数据表、公式、原理、方案，追问一条回复的依据，要求简短回答，要求只读静态解释，要求向 domain 补充背景知识，或要求让其他 skill 接入本 skill 时使用。
---

# user-explain

解释类回复的流程。本文件只写步骤；场景细则在 `scenarios/`，通用原则在 `principles/`，验收在 `checklist.md`，背景知识在 `domain/`。回复中不出现本 skill 的技巧术语，只呈现结论和依据。

## 模式

用户未指明时使用默认模式。`short` 由 AI 按问题判定进入，或由用户要求进入，可与默认、`static`、`analysis` 组合；`learn`、`embed` 单独使用。

| 模式 | 作用 | 细则 |
|---|---|---|
| 默认 | 完整流程 | 本文件 |
| short | 3 到 5 句的简短回复，详略判定见 `principles/length.md` | `modes/short.md` |
| analysis | 重建上一条回复的推导记录 | `modes/analysis.md` |
| static | 只读静态解释，不运行任何代码 | `modes/static.md` |
| learn | 用户明确提出时向 `domain/` 写入背景知识 | `modes/learn.md` |
| embed | 用户要求让其他 skill 接入本 skill 时，给出接入建议 | `modes/embed.md` |

## 流程

1. 转命题：把用户的话转成待判断的命题，区分"质疑是否成立"与"已接受、只问原因"，缺指称才问用户。细则见 `principles/logic.md`。
2. 判场景：从 `scenarios/` 选一个最贴近的场景并读取，该文件给出方法与必答要素。
3. 取材：对每个必答要素找答案和依据。需要背景知识时，先读 `domain/INDEX.md` 并只读相关文件；没有再 web 搜索或用模型内部知识，来源与可信度的处理见 `principles/content.md`。
4. 取舍：先判定详略（`principles/length.md`），再按用户目的决定哪些信息写出、哪些舍弃（`principles/content.md`）。
5. 写作：结构与句间关系见 `principles/writing.md`，用语见 `principles/wording.md`，涉及代码见 `principles/code-description.md`。
6. 验收：逐项过 `checklist.md` 和所选场景文件的验收项，任何一项为否就回到第 3 步或第 5 步修改。

## 纠错

用户指出某条知识或原则过时、不成立或版本不对时，按 `correction.md` 执行。

## 写入限制

`domain/` 只在用户明确提出时写入，任何模式和流程都不得自行追加或修订。
