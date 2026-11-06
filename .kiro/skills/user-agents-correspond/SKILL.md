---
name: user-agents-correspond
description: 基于本地 Markdown 文件维护协作 work、发布和接收消息，并将有效新消息转交当前 Kiro session。当用户要求多 agent 通信、协作交接、广播或接收其他 worker 的消息、监控消息、点名，或归档、恢复协作 work 时使用。
---

# user-agents-correspond

## 调用

```text
/user-agents-correspond <command> [arguments]
```

第一个参数是命令，其余是该命令的参数。没有命令时，本 skill 只作为与描述相符的用户请求的上下文。

- `update-work`：记录当前 work 的确认进展，是写入 `state/active/<work_id>.md` 的唯一命令。
- `broadcast`：只追加带 UTC 时间戳的新 message，绝不修改已有 message。
- `receive`：一次性接收，由当前 session 直接完成，不使用脚本或 workflow。
- `watch`：启动持续监控，由当前 session 启动的专用 workflow 完成；`watch checkpoint` 取回检查点，`watch stop` 停止监控。
- `archive`：把 work state 从 `state/active/` 移到 `state/archived/`。
- `restore`：把归档的 work state 移回 `state/active/`，恢复为归档前的状态。

`receive` 与 `watch` 使用同一套 [消息有效性规则](references/message-validity.md)，区别只在于执行一次还是持续执行。

## 确定当前 work

执行任何命令前，先确定当前 session 的 `work_id`：

1. 从当前 session 的主任务确定仓库绝对路径（无仓库时为 `not-applicable`）、issue 与 PR（无关联对象时为 `_`）以及用户需求。session 没有可执行的主任务时，不创建 work，直接告知用户。
2. session 已关联完整 `work_id` 时直接复用。
3. 否则在 `state/active/` 与 `state/archived/` 中查找同一协作范围的 state。用户需求恰好对应其中一个 work 时复用它，该 work 已归档时先 `restore`；对应多个或无法判断时，请用户指定 `work_id`。
4. 没有可复用的 work 时新建：`sub-worker` 取该协作范围在 `state/active/` 与 `state/archived/` 中都未使用的最小正整数，再用 `update-work` 创建 state。

## 各命令的执行与报告

- `update-work`：只写入当前 session 已确认的进展；报告 state 路径、`work_id`、`lifecycle` 与进展。
- `broadcast`：把正文写入通信根目录之外的私有临时文件，确认 frontmatter 取值与正文不含秘密信息和未经验证的结论，发送后删除临时文件；报告 message 路径与一句话摘要。
- `receive`：按下文 receive 一节执行；报告有效 message 及据此采取的动作。
- `watch`：按下文 watch 一节启动，报告 workflow ID。`watch checkpoint` 与 `watch stop` 向该 workflow 发送同名控制指令；`stop` 后用 `update-work` 写入返回的检查点。
- `archive`、`restore`：按下文 archive 与 restore 一节执行；报告移动后的 state 路径。

## 文件与标识

- 通信根目录是 `/home/peiran/data/my-kiro-cli/.kiro/agent-correspondence/`：`messages/` 存放 message，`state/active/<work_id>.md` 存放 work state，`state/archived/<work_id>.md` 存放归档的 work state。
- `work_id` 的格式为 `<repo>-<issue>-<pr>-<sub-worker>`。`repo` 是仓库目录名转小写并把 `_` 换成 `-`，无仓库时为 `not-applicable`；`issue`、`pr` 是十进制编号或 `_`；`sub-worker` 是不带前导零的正整数。前三段相同的 worker 属于同一协作范围。
- message 文件名为 UTC 时间 `YYYY-MM-DDTHH-MM-SS-NNNNNNNNNZ.md`，文件名顺序即时间顺序；不符合该格式的文件不属于协议。
- 文本字段不得为空，也不得含 password、passphrase、secret、token、api key、private key、connection string 字样，否则脚本拒绝写入。

## 脚本

`update-work`、`broadcast`、`watch`、`archive`、`restore` 都通过以下方式调用；`--correspondence-dir` 写在子命令之前，默认为通信根目录。出错时退出码为 2，stderr 输出一行错误，stdout 无输出。

```bash
python3 /home/peiran/data/my-kiro-cli/.kiro/skills/user-agents-correspond/scripts/correspond.py [--correspondence-dir "<dir>"] <command> ...
```

### update-work

```bash
... update-work --work-id "<work_id>" --repo "<仓库绝对路径或 not-applicable>" --issue "<issue>" --pr "<pr>" --sub-worker <n> --user-requirement "<需求>" --progress "<进展>" [--last-read-file "<文件名或 none>"] [--accepted-file "<文件名>" ...] [--lifecycle "<active|blocked>"]
```

- 该 `work_id` 已归档时拒绝写入，须先 `restore`。
- 除 `--last-read-file`、`--accepted-file` 与 `--lifecycle` 外均必填；`--repo` 的目录名、`--issue`、`--pr`、`--sub-worker` 必须与 `work_id` 对应段一致。
- state 不存在时创建，`lifecycle` 默认为 `active`，`last_read_file` 为 `none`，`accepted_files` 为空。
- 每次调用用新值替换 `user_requirement` 与 `progress`。
- 给出 `--last-read-file` 时替换 cursor，省略时保留原值。
- `--accepted-file` 可重复，追加到 `accepted_files` 并去重，不删除已有记录。
- `--lifecycle` 省略时保留原值。`blocked` 表示 work 因外部依赖或待用户决定而暂停，原因写入 `progress`；`lifecycle` 不影响 `receive`、`watch` 与 `broadcast`。

### broadcast

```bash
... broadcast --work-id "<发送方 work_id>" --source-agent "<发送方标识>" --action "<information|handoff|request|acknowledgement|receipt>" [--body-file "<正文文件>"] [--target-work-id "<完整 work_id 或 broadcast>"] [--requested-acknowledgement-from-work-id "<work_id>" --requested-acknowledgement "<回执正文>"] [--in-reply-to "<request 文件名>"]
```

- 发送方 state 必须已存在；message 的 `repo`、`issue`、`pr`、`sub_worker`、`user_requirement`、`progress` 取自发送方 state。
- `--target-work-id` 默认为 `broadcast`，填完整 `work_id` 即为定向消息。
- 除 `receipt` 外必须给出 `--body-file`，正文取自该文件并去掉末尾换行；`receipt` 不接受 `--body-file`，正文由脚本固定生成。
- `request` 必须同时给出两个回执参数，且 `--target-work-id` 等于 `--requested-acknowledgement-from-work-id`。
- `acknowledgement` 与 `receipt` 必须给出 `--in-reply-to`。`receipt` 引用的 request 必须是发给发送方本人的，且 `--target-work-id` 必须等于该 request 的发送方，否则脚本拒绝发送。
- 其它 action 不使用回执参数与 `--in-reply-to`。
- message 的 frontmatter 字段为 `schema`、`created_at_utc`、`source_agent`、`work_id`、`target_work_id`、`repo`、`issue`、`pr`、`sub_worker`、`user_requirement`、`progress`、`action`；request 另有 `requested_acknowledgement_from_work_id` 与 `requested_acknowledgement`，acknowledgement 与 receipt 另有 `in_reply_to`。正文位于 `## Message` 标题之后。

### watch

```bash
... watch --work-id "<work_id>" [--cursor "<文件名或 none>"] [--accepted-file "<文件名>" ...] [--timeout-seconds <秒>] [--call-timestamp "<本次调用的 UTC 时间>"]
```

- `--call-timestamp` 不影响脚本行为。workflow 每次调用都传入本次调用的 UTC 时间，格式为 `YYYY-MM-DDTHH:MM:SSZ`，使每次调用的命令文本都不相同，避免 Kiro 平台把重复的相同调用判定为死循环而打断 watch。该值必须以字面值写进命令，不能写成 `$(date ...)` 这类由 shell 展开的表达式，否则命令文本仍然相同；无法确定当前时间时，保证它晚于上一次调用的值即可。
- `--cursor` 省略时取 state 的 `last_read_file`；`none` 表示从最早的 message 开始。
- `--accepted-file` 可重复，与 state 的 `accepted_files` 合并；合并结果中的 message 不再输出为 event。
- `--timeout-seconds` 默认 10，不得为负。脚本立即扫描一次，之后每 10 秒扫描一次；读到新 message 时立即返回，否则到时返回。
- 脚本只读，输出一行 JSON：`cursor`；`work`，即当前 work 的 `user_requirement` 与 `progress`；`events`，每个 event 含 `filename`、`action`、`source_work_id`、`target_work_id`、`body`，request 另含 `requested_acknowledgement_from_work_id` 与 `requested_acknowledgement`，acknowledgement 与 receipt 另含 `in_reply_to`，receipt 另含 `progress`，即回执方 state 中的进展。
- 输出的 event 已通过自身消息、目标 `work_id`、协作范围、acknowledgement 与 receipt 的确定性判定。

### archive 与 restore

```bash
... archive --work-id "<work_id>"
... restore --work-id "<work_id>"
```

- 两者都先校验源 state，再把文件原样移到目标目录，不改写任何字段（含 `lifecycle`、`updated_at_utc`、cursor、`accepted_files` 与其它字段），因此 `restore` 后的 state 与归档前逐字节相同。
- 源 state 不存在或目标位置已有同名 state 时报错，不覆盖。
- 只有 `state/active/` 下的 state 能被 `update-work`、`broadcast`、`watch` 使用；该 work 有 `watch` workflow 在运行时，先发 `stop` 并把返回的 cursor 与 accepted_files 用 `update-work` 写入 state，再 `archive`。

## Work state

work state 使用 `user-agents-correspond-state/v2`，至少包含任务需求、进展、`last_read_file` 与 `accepted_files` 等预定义字段；其它字段允许存在，`update-work` 改写 state 时原样保留。接收过程中的 cursor 与 accepted_files 保存在执行接收的一方：`receive` 保存在当前 session 上下文，`watch` 保存在 workflow 内存。当前 session 仅在 `update-work` 或任务结束时把它们写入 state。

## Cursor 与采纳记录

`last_read_file` 是接收游标，表示最近读取过的 message 文件，与 message 是否有效或是否被采纳无关。每个新 message 一经读取就推进 cursor，使下一轮只处理文件名时间戳更晚的 message。`accepted_files` 只记录通过完整判定的有效 message。cursor 用于划分已读与未读，`accepted_files` 用于记录已采纳信息，两者表达不同事实。

## receive

当前 session 按文件名顺序读取 `messages/` 中文件名晚于 cursor 的规范 message，逐条按规则判断，对有效 message 采取任务动作。首次接收的 cursor 与 accepted_files 取自 state。

## watch

当前 session 用 `run_workflow` 启动 workflow：`workflowPath` 为 `agent://wf-coder`，`runLabel` 为 `watch-<work_id>`，输入 `prompt` 取自 [watch workflow prompt 模板](references/watch-workflow-prompt.md)，并把其中的 `<work_id>` 全部替换为当前 `work_id`。session 记下返回的 workflow ID 与 step session ID（可用 `inspect_workflow` 查到），用于发送控制指令。以下是模板规定的行为。

workflow 循环调用 `watch` 脚本，直到收到 `stop`：首次调用省略 `--cursor` 与 `--accepted-file`，之后每次传入内存中的 cursor 与全部 accepted_files；每次调用都传入新的 `--call-timestamp`。workflow 依据输出中的 `work` 对广播 event 做 AI 相关性判断。

workflow 对每条有效 event，把文件名加入 accepted_files，再用 `send_message`（severity `info`）把 event 全部字段、最新 cursor 与 accepted_files 发给当前 session。若该 event 的 action 为 `request`，workflow 随后立即发送送达回执，其它 action 不发送：

```bash
python3 /home/peiran/data/my-kiro-cli/.kiro/skills/user-agents-correspond/scripts/correspond.py broadcast --work-id "<work_id>" --source-agent "watch workflow" --action receipt --target-work-id "<event 的 source_work_id>" --in-reply-to "<event 的 filename>"
```

当前 session 用 `send_message` 向 workflow 的 step session 发送控制指令：

- `checkpoint`：workflow 回复最新 cursor 与 accepted_files（severity `info`），继续监控。
- `stop`：workflow 回复最新 cursor 与 accepted_files，并以 severity `success` 结束。

脚本退出码非 0 时，workflow 用 `send_message`（severity `error`）报告 stderr 原文并结束。

除上述送达回执外，workflow 不写任何文件，也不做上述以外的工作。

## 送达回执

送达回执（`receipt`）只表示 request 已被接收方的 watch 收到并转交主 session，不代表 request 已处理，也不能代替 `acknowledgement`。回执的 frontmatter `progress` 取自接收方 state，因此主 session 开始一次长时间阻塞的调用前，先用 `update-work` 把进展写成正在执行的任务与预计结束时间，回执就会带上这条进展。

发送方据此区分两种情况：收到送达回执但尚未收到正式回复，表示接收方在忙，进展见回执的 `progress`；发出 request 后约 30 秒内连送达回执都没有，表示接收方没有 watch 在运行。receipt 本身不触发任何回执。

## 回复 request

被 request 指定的 worker 用 `broadcast --action acknowledgement --target-work-id "<请求者 work_id>" --in-reply-to "<request 文件名>"` 回复，正文与 `requested_acknowledgement` 完全一致。

## 预设通信模式

`patterns/<name>.md` 定义预设通信模式，正文首行为 `pattern: <name>` 的 message 按对应文件处理。这类广播在同一协作范围内直接有效，不做 AI 相关性判断。用户要求某种模式时，按对应文件发起。

- [roll-call](patterns/roll-call.md)：点名，让同一协作范围内所有 active 的 worker 定向回报自己的 work_id。

## Workflow 边界

workflow 只用于 `watch`，用户决定是否启动；workflow 唯一的写操作是对有效 request 发送送达回执。`update-work`、`broadcast`、`receive`、`archive`、`restore`、skill 修改与测试均由当前 session 完成。
