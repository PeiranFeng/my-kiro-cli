---
name: user-agents-correspond
description: 基于本地 Markdown 文件维护协作 work、发布和接收消息，并将有效新消息转交当前 Kiro session。
---

# user-agents-correspond

## Commands

- `update-work`：写入 `state/active/<work_id>.md` 的唯一命令。
- `broadcast`：只追加带 UTC 时间戳的新 message，绝不修改已有 message。
- `receive`：一次性接收，由当前 session 直接完成，不使用脚本或 workflow。
- `watch`：持续监控，由当前 session 启动的专用 workflow 完成，直到当前 session 停止它。

`receive` 与 `watch` 使用同一套 [消息有效性规则](references/message-validity.md)，区别只在于执行一次还是持续执行。

## 文件与标识

- 通信根目录是 `/home/peiran/data/my-kiro-cli/.kiro/agent-correspondence/`：`messages/` 存放 message，`state/active/<work_id>.md` 存放 work state。
- `work_id` 的格式为 `<repo>-<issue>-<pr>-<sub-worker>`。`repo` 是仓库目录名转小写并把 `_` 换成 `-`，无仓库时为 `not-applicable`；`issue`、`pr` 是十进制编号或 `_`；`sub-worker` 是不带前导零的正整数。前三段相同的 worker 属于同一协作范围。
- message 文件名为 UTC 时间 `YYYY-MM-DDTHH-MM-SS-NNNNNNNNNZ.md`，文件名顺序即时间顺序；不符合该格式的文件不属于协议。
- 文本字段不得为空，也不得含 password、passphrase、secret、token、api key、private key、connection string 字样，否则脚本拒绝写入。

## 脚本

`update-work`、`broadcast`、`watch` 都通过以下方式调用；`--correspondence-dir` 写在子命令之前，默认为通信根目录。出错时退出码为 2，stderr 输出一行错误，stdout 无输出。

```bash
python3 /home/peiran/data/my-kiro-cli/.kiro/skills/user-agents-correspond/scripts/correspond.py [--correspondence-dir "<dir>"] <command> ...
```

### update-work

```bash
... update-work --work-id "<work_id>" --repo "<仓库绝对路径或 not-applicable>" --issue "<issue>" --pr "<pr>" --sub-worker <n> --user-requirement "<需求>" --progress "<进展>" [--last-read-file "<文件名或 none>"] [--accepted-file "<文件名>" ...]
```

- 除 `--last-read-file` 与 `--accepted-file` 外均必填；`--repo` 的目录名、`--issue`、`--pr`、`--sub-worker` 必须与 `work_id` 对应段一致。
- state 不存在时创建，`lifecycle` 为 `active`，`last_read_file` 为 `none`，`accepted_files` 为空。
- 每次调用用新值替换 `user_requirement` 与 `progress`。
- 给出 `--last-read-file` 时替换 cursor，省略时保留原值。
- `--accepted-file` 可重复，追加到 `accepted_files` 并去重，不删除已有记录。

### broadcast

```bash
... broadcast --work-id "<发送方 work_id>" --source-agent "<发送方标识>" --action "<information|handoff|request|acknowledgement>" --body-file "<正文文件>" [--target-work-id "<完整 work_id 或 broadcast>"] [--requested-acknowledgement-from-work-id "<work_id>" --requested-acknowledgement "<回执正文>"] [--in-reply-to "<request 文件名>"]
```

- 发送方 state 必须已存在；message 的 `repo`、`issue`、`pr`、`sub_worker`、`user_requirement`、`progress` 取自发送方 state。
- `--target-work-id` 默认为 `broadcast`，填完整 `work_id` 即为定向消息。
- 正文取自 `--body-file`，去掉末尾换行。
- `request` 必须同时给出两个回执参数，且 `--target-work-id` 等于 `--requested-acknowledgement-from-work-id`；`acknowledgement` 必须给出 `--in-reply-to`；其它 action 不使用这三个参数。
- message 的 frontmatter 字段为 `schema`、`created_at_utc`、`source_agent`、`work_id`、`target_work_id`、`repo`、`issue`、`pr`、`sub_worker`、`user_requirement`、`progress`、`action`；request 另有 `requested_acknowledgement_from_work_id` 与 `requested_acknowledgement`，acknowledgement 另有 `in_reply_to`。正文位于 `## Message` 标题之后。

### watch

```bash
... watch --work-id "<work_id>" [--cursor "<文件名或 none>"] [--accepted-file "<文件名>" ...] [--timeout-seconds <秒>]
```

- `--cursor` 省略时取 state 的 `last_read_file`；`none` 表示从最早的 message 开始。
- `--accepted-file` 可重复，与 state 的 `accepted_files` 合并；合并结果中的 message 不再输出为 event。
- `--timeout-seconds` 默认 10，不得为负。脚本立即扫描一次，之后每 10 秒扫描一次；读到新 message 时立即返回，否则到时返回。
- 脚本只读，输出一行 JSON：`cursor`；`work`，即当前 work 的 `user_requirement` 与 `progress`；`events`，每个 event 含 `filename`、`action`、`source_work_id`、`target_work_id`、`body`，request 另含 `requested_acknowledgement_from_work_id` 与 `requested_acknowledgement`。
- 输出的 event 已通过自身消息、目标 `work_id`、协作范围与 acknowledgement 的确定性判定。

## Work state

work state 使用 `user-agents-correspond-state/v2`，至少包含任务需求、进展、`last_read_file` 与 `accepted_files` 等预定义字段；其它字段允许存在，`update-work` 改写 state 时原样保留。接收过程中的 cursor 与 accepted_files 保存在执行接收的一方：`receive` 保存在当前 session 上下文，`watch` 保存在 workflow 内存。当前 session 仅在 `update-work` 或任务结束时把它们写入 state。

## Cursor 与采纳记录

`last_read_file` 是接收游标，表示最近读取过的 message 文件，与 message 是否有效或是否被采纳无关。每个新 message 一经读取就推进 cursor，使下一轮只处理文件名时间戳更晚的 message。`accepted_files` 只记录通过完整判定的有效 message。cursor 用于划分已读与未读，`accepted_files` 用于记录已采纳信息，两者表达不同事实。

## receive

当前 session 按文件名顺序读取 `messages/` 中文件名晚于 cursor 的规范 message，逐条按规则判断，对有效 message 采取任务动作。首次接收的 cursor 与 accepted_files 取自 state。

## watch

当前 session 启动 workflow 时，在 prompt 中给出 `work_id` 与本 skill 路径，要求它只执行本节。workflow 循环调用 `watch` 脚本，直到收到 `stop`：首次调用省略 `--cursor` 与 `--accepted-file`，之后每次传入内存中的 cursor 与全部 accepted_files。workflow 依据输出中的 `work` 对广播 event 做 AI 相关性判断。

workflow 对每条有效 event，把文件名加入 accepted_files，再用 `send_message`（severity `info`）把 event 全部字段、最新 cursor 与 accepted_files 发给当前 session。

当前 session 用 `send_message` 向 workflow 的 step session 发送控制指令：

- `checkpoint`：workflow 回复最新 cursor 与 accepted_files（severity `info`），继续监控。
- `stop`：workflow 回复最新 cursor 与 accepted_files，并以 severity `success` 结束。

workflow 不修改任何文件，也不做上述以外的工作。

## 回复 request

被 request 指定的 worker 用 `broadcast --action acknowledgement --target-work-id "<请求者 work_id>" --in-reply-to "<request 文件名>"` 回复，正文与 `requested_acknowledgement` 完全一致。

## Workflow 边界

workflow 只用于 `watch`，用户决定是否启动。`update-work`、`broadcast`、`receive`、skill 修改与测试均由当前 session 完成。
