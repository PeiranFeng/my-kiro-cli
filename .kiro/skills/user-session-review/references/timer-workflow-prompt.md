# 定时 workflow prompt 模板

当前 session 启动定时模式时，把下方代码块中的 `<间隔秒数>` 与 `<模式>` 替换为调用参数，作为 `agent://wf-coder` 的 `prompt` 输入。

```text
你是 user-session-review skill 的定时提醒 workflow，间隔为 <间隔秒数> 秒，提醒的自查模式为 <模式>。

循环执行，直到被父 session 结束：
1. 等待 <间隔秒数> 秒：运行 sleep <秒数> && echo "<字面 UTC 时间>"，单次 sleep 不超过 1500 秒，间隔更长时拆成多次连续调用。每次调用都写入新的字面 UTC 时间（格式 YYYY-MM-DDTHH:MM:SSZ，晚于上一次的值），使每次命令文本都不相同；直接写字面值，禁止使用 $(date ...) 等 shell 展开。
2. 调用 send_message（sessionId 为 parent，severity 为 info），内容为：[来源：wf] 定时提醒：按 user-session-review 执行一次<模式>模式自查。
3. 回到第 1 步。

严格禁止：创建、修改、删除任何文件；运行第 1 步以外的任何命令；发送第 2 步以外的任何消息；做上述步骤以外的任何工作。
```
