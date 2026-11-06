---
name: user-agents-correspond
description: 基于本地 Markdown 文件维护协作 work、发布消息，并将有效新消息转交当前 Kiro session。
---

# user-agents-correspond

## Commands

- `update-work` 是写入 `state/active/<work_id>.md` 的唯一命令。
- `broadcast` 只追加一个带规范 UTC 时间戳的新 message，绝不修改已有 message。
- `watch` 是监控 workflow 使用的固定脚本；每次运行最多等待 10 秒，扫描 cursor 之后的新 message，并输出 JSON。

## Work state

work 使用 `user-agents-correspond-state/v2`，保存任务要求、确认进展、`last_read_file`、`read_files` 和 `accepted_files`。监控期间 cursor 与列表只保存在 workflow 内存。当前 session 在手动 `update-work` 或任务结束时，以 `--last-read-file`、`--read-file` 和 `--accepted-file` 保存检查点。

## Message validity

规则详见 [references/message-validity.md](references/message-validity.md)。`watch` 确定性地筛选明确目标 work、同 repo/issue/PR 的广播和结构正确的 acknowledgement。workflow 按该文件中的 AI 相关性规则决定是否用 `send_message` 把 event 送入当前 session，并将当前内存检查点随消息一同报告。workflow 只运行 `watch` 并转交消息，不得修改文件、skill 或任务。

## Workflow boundary

workflow 只用于消息监控。`update-work`、`broadcast`、协议修改、skill 修改、测试和任务执行均由当前 session 完成。用户决定是否启动监控。

## Watch invocation

```bash
python3 /home/peiran/data/my-kiro-cli/.kiro/skills/user-agents-correspond/scripts/correspond.py watch --work-id "<work_id>" --cursor "<in-memory cursor>" --timeout-seconds 10
```

`watch` 不写 state 或 messages。workflow 保存 JSON 输出的 cursor，在下一轮传回 `--cursor`。重启 workflow 时，当前 session 从 work 的已保存 `last_read_file` 建立新的内存 cursor。
