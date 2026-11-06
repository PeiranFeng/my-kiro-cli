# roll-call：点名

发起方广播一条点名 message，同一协作范围内所有 active 的 worker 各自用一条定向 message 回复发起方，回复 message 的 `work_id` 字段即汇报的 work_id。

## 前提

- 发起方的 state 已存在于 `state/active/<work_id>.md`；不存在时不发起，先告知用户。
- 广播只送达与发起方同 repo、同 issue、同 PR 的 worker（见 [消息有效性判定](../references/message-validity.md) 第 2 项），点名范围即该协作范围。
- 已归档的 worker 不参与：其 state 不在 `state/active/` 下，无法接收也无法发送。

## 发起

正文文件内容为一行：

```
pattern: roll-call
```

```bash
... broadcast --work-id "<发起方 work_id>" --source-agent "<发起方标识>" --action information --body-file "<正文文件>"
```

脚本输出的 message 文件名是本次点名的标识。

## 回复

收到正文首行为 `pattern: roll-call` 的有效广播时，worker 回复一次，正文文件内容为两行：

```
pattern: roll-call-reply
in_reply_to: <点名 message 文件名>
```

```bash
... broadcast --work-id "<回复方 work_id>" --source-agent "<回复方标识>" --action information --target-work-id "<点名 message 的 work_id>" --body-file "<正文文件>"
```

## 汇总

发起方用 `receive` 或 `watch` 接收定向回复，把正文 `in_reply_to` 等于本次点名文件名的 message 的 `work_id` 字段汇总成列表报告给用户。点名没有结束信号，汇总结果只包含报告时已收到的回复。
