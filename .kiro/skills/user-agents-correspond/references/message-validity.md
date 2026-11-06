# 消息有效性判定

执行接收的一方按本规则判断 message：`receive` 由当前 session 判断，`watch` 由监控 workflow 判断。

首先忽略当前 worker 自己发送的所有 message。其余 message 按以下顺序判定，前一项已给出结论时，后续项不改变该结论：

1. `target_work_id` 为完整 `work_id` 时，只有该 worker 视为有效，其他 worker 视为无效。
2. `target_work_id` 为 `broadcast` 时，消息源与当前 worker 的 `work_id` 必须同 repo、同 issue、同 PR，否则无效。
3. 满足第 2 项的广播，由 AI 依据当前 work 的任务需求与进展判断是否相关，相关才有效。

acknowledgement 还必须引用存在的 request，且 request 的发送 worker、指定回应 worker、acknowledgement 的目标 worker 和精确正文均一致。

有效 message 的文件名加入 accepted_files。
