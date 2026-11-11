---
name: user-session-review
description: 依据当前 session 正在进行的任务类型，在 steering 中找对应部分的原则，自我监控工作质量。分单次、严格、定时三种模式。
---

# user-session-review

依据当前 session 正在进行的任务类型，在 steering 中找对应部分的原则，自我监控工作质量。

## 调用

```text
/user-session-review <单次|严格|定时> [参数]
```

## 单次模式

查一次，non-blocking：先完成手头工作，再自查。自查哪些部分由当前 session 依据任务类型自由决定；发现需要修改的地方，自行判断是否调整。

## 严格模式

停止手头工作，按照 steering 的全部原则进行自查，重新思考整个工作方针。自查结果与调整后的方针和用户确认后，再继续工作。

## 定时模式

```text
/user-session-review 定时 [间隔秒数] [单次|严格]
```

当前 session 用 `run_workflow` 启动一个简单的 workflow：`workflowPath` 为 `agent://wf-coder`，`runLabel` 为 `session-review-timer`，`prompt` 取自 [定时 workflow prompt 模板](references/timer-workflow-prompt.md)，把其中的 `<间隔秒数>` 与 `<模式>` 替换为调用参数。`<间隔秒数>` 省略时为 3600（一小时），`<模式>` 省略时为 `单次`。

该 workflow 每隔 `<间隔秒数>` 向当前 session 发送一条 message，提醒按 `<模式>` 执行一次自查，消息中注明来源是 wf；当前 session 收到提醒后按对应模式执行。

某次收到 wf 的提醒时，若 session 已经进入稳定的实验阶段，当前 session 直接停下该 workflow，不询问用户，并在回复中告知用户已停下。

当前 session 记下返回的 workflow ID；停止时用 `update_workflow`（action `update_status`，省略 nodeId，status `aborted`）结束该 workflow。
