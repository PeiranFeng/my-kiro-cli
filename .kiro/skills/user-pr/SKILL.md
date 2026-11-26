---
name: user-pr
description: GitHub PR 的四个相互独立的接口：comments 查阅并评估 PR 上已有的 review 意见，requirement 验证 PR 的需求与方案是否成立，review 对线上 PR 的代码做独立审查（默认先执行 requirement），archive 把结果记录到 ~/data/pr/<repo>/<number>.md。当用户要求查看或分析 PR 的 review 意见、验证 PR 需求、审查 PR 代码、归档或记录 PR 时使用。
---

# user-pr — GitHub Pull Request

所有 gh 命令针对组织 `FinAI-Project` 下的仓库（列表见 `50-project-facts.md#repos`）。本 skill 里的 gh 操作全部只读；发评论、合并等写操作按 `40-git-safety.md` 需用户明确指示。

## 接口

四个接口相互独立，用户只要求其中一个时，只执行该接口，不顺带执行其他接口；唯一例外见下文「review 前置 requirement」。

| 接口 | 做什么 | 输出 | 写文件 | 细则 |
|---|---|---|---|---|
| comments | 查阅 PR 上已有的 review 意见，逐条对照源码评估 | 回复正文 | 否 | `comments.md` |
| requirement | 验证 PR 的需求来源、前提、副作用、达成度与方案最优性 | 回复正文 | 否 | `requirement.md` |
| review | 对 PR 的 diff 做独立代码审查 | 回复正文 | 否 | `review.md` |
| archive | 把 comments 与 review 的结果记录到本地文件 | `~/data/pr/<repo>/<number>.md` | 是 | `archive.md` |

选择接口的依据是用户的话：

- 要求查看、分析 review 意见或评论：comments。
- 要求验证 PR 的需求或方案是否成立：requirement。
- 要求审查或 review PR 的代码：review。
- 要求归档、保存或记录：archive。
- 仍无法判断时，只问用户要哪个接口。

## review 前置 requirement

用户要求 review 时，先执行 requirement 接口，再执行 review 接口，两者结果在同一条回复里依次呈现。用户明确要求跳过需求验证时才只执行 review。用户只要求 requirement 时，只执行 requirement。

## 确定目标 PR

优先从用户指令和对话上下文推断参数，不铺选项询问（见 `user-explain/principles/content.md` 的"直接回答"）。

- 用户给了 PR 编号和仓库：以此为目标。
- 用户未给编号：读取仓库（无法推断时必须直接问，不默认处理全部仓库）、时间范围（默认最近 7 天）、发布者（默认不限制），再列出 PR：

```bash
gh pr list \
  --repo FinAI-Project/<repo> \
  --state all \
  --search "created:>=<YYYY-MM-DD>" \
  [--author <author>] \
  --json number,title,url,state,createdAt \
  --limit 200
```

设置了发布者才追加 `--author <login>`。列表为空则告知用户该仓库无 PR 并跳过。

## 共用细则

- 读取 PR 对应的远程分支源码，按 `reading-source.md`。
- 每个对话输出型接口（comments、review）的最后一步是按 `user-explain` 写回复并过验收清单，该步骤写在各接口自己的步骤里。
