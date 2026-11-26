---
name: user-wf
description: 主 session 通过 run_workflow 启动后台工作流（qwen3-coder-next 模型）监控指定目标并实时通知主 session，支持首次即终止、持续监控、定时三种生命周期。当用户要求启动监控工作流时使用。
---

# user-wf — 启动监控工作流

## 流程

1. **判断场景**：读取 `scenarios/` 目录下的文件，匹配用户指令对应的场景。未匹配任何场景时使用 `scenarios/custom.md`。
2. **收集参数**：按匹配场景文件的要求，从用户指令和对话中提取必要参数。缺失时只问缺失项。
3. **确定生命周期**：从用户指令或对话中确定生命周期（首次即终止/持续监控/定时）。用户未说明时只问这一项。
4. **启动工作流**：调用 `run_workflow`，`workflowPath: "agent://wf-coder"`，`modelId: "qwen3-coder-next"`，`prompt` 由场景文件的 prompt 要求与 `lifecycles.md` 中对应生命周期的文本拼接而成。
5. **告知用户**：报告工作流 ID 和生命周期。

## 生命周期

| 名称 | 工作流何时结束 | 每条消息的操作 |
|---|---|---|
| 首次即终止 | 收到第一匹配消息后自动结束 | 发送 severity info 到 parent，再发送 severity success 结束工作流 |
| 持续监控 | 用户主动要求主 session 关闭 | 每次匹配消息发送 severity info 到 parent，持续运行 |
| 定时 | 达到用户指定的北京时间截止时间 | 每次匹配消息发送 severity info 到 parent；截止时刻发送 severity success 并结束 |

`lifecycles.md` 保存各生命周期的详细指示，供拼接到工作流 prompt。

## 场景

- `scenarios/pr-comment-monitor.md`：监控 GitHub PR 的评论，按 sender 和 baseline 过滤。需用户提供 PR（组织+仓库+编号）和可选的 comment 发送方账户名。
- `scenarios/custom.md`：自定义模式。当无场景匹配时触发，主 session 与用户交互收集监控目标、检查方式、匹配条件、轮询间隔和通知内容。