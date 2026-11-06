---
name: user-agents-correspond
description: 基于本地 Markdown 文件维护协作 work、发布和接收消息，并将有效新消息转交当前 Kiro session。
---

# user-agents-correspond

- `update-work` 是写入 `state/active/<work_id>.md` 的唯一命令。
- `broadcast` 只追加带 UTC 时间戳的新 message，绝不修改已有 message。
- `receive` 是当前 session 的一次性接收：扫描 cursor 之后的 message，输出候选 JSON 后结束。
- `watch` 是持续监控：当前 session 启动专用 workflow，workflow 每 10 秒运行一次固定的 `receive` 脚本。首次接收不传 cursor，脚本从 state 读取 `last_read_file` 与 `accepted_files`；后续接收传入 workflow 内存的 cursor 和 accepted_files。workflow 按 [消息有效性规则](references/message-validity.md) 判断并以 `send_message` 转交有效消息，直到当前 session 手动停止监控。

work state 使用 `user-agents-correspond-state/v2`，保存任务、进展、`last_read_file` 与 `accepted_files`。workflow 在内存中保存本次监控的 cursor 与 accepted_files；当前 session 仅在 `update-work` 或任务结束时保存检查点。

## Cursor 与采纳记录

`last_read_file` 是接收游标，表示 workflow 最近读取过的 message 文件，与 message 是否有效或是否被采纳无关。每个新 message 一经读取，workflow 就在内存中推进 cursor，使下一轮只处理文件名时间戳更晚的 message。`accepted_files` 只记录通过完整判定并实际送入当前 session 的 message。cursor 用于划分已读与未读，`accepted_files` 用于记录已采纳信息，两者表达不同事实。

固定接收脚本：

```bash
python3 /home/peiran/data/my-kiro-cli/.kiro/skills/user-agents-correspond/scripts/correspond.py receive --work-id "<work_id>" --cursor "<in-memory cursor>" --accepted-file "<accepted message filename>" --timeout-seconds 10
```

`receive` 不写 state 或 messages。监控 workflow 只运行这个脚本、判断规则并调用 `send_message`；不得修改文件、skill 或任务。
