# 消息有效性判定

监控 workflow 首先忽略当前 worker 自己发送的所有 message。其余 message 按以下顺序决定是否送入当前 session：

1. `target_work_id` 为完整 `work_id` 时，只有该 worker 有效，其他 worker 无效。
2. `target_work_id` 为 `broadcast` 时，消息源与订阅 worker 的 `work_id` 必须同 repo、同 issue、同 PR。
3. 前两项通过后，workflow 的 AI 判断 message 是否与当前任务相关；相关时才用 `send_message` 转交当前 session。

acknowledgement 还必须引用存在的 request，且 request 的发送 worker、指定回应 worker、acknowledgement 的目标 worker 和精确正文均一致。

workflow 在内存保存 cursor、已访问列表和有效列表。当前 session 在 `update-work` 或任务结束时保存这些检查点。
