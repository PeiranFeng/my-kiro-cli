# 生命周期

## 首次即终止

收到第一匹配消息后立即结束。处理流程：

1. 收到匹配消息时，发送通知到主 session（`send_message`，`sessionId: "parent"`，`severity: "info"`）。
2. 紧接着发送 `send_message`（`severity: "success"`）通知主 session 此步骤完成并结束工作流。
3. 未收到匹配消息时，按轮询间隔休眠后继续检查，不自行结束。

## 持续监控

持续运行直到用户主动要求主 session 关闭。处理流程：

1. 执行监控检查（按轮询间隔休眠）。
2. 收到匹配消息时，发送通知到主 session（`send_message`，`severity: "info"`）。
3. 工作流保持运行，继续下一轮轮询。
4. 用户通知主 session 关闭时，主 session 调用 `update_workflow`（`action: "update_status"`，`status: "completed"`，`nodeId` 为工作流的 run node id）终止工作流。

## 定时

运行至用户指定的北京时间截止时间。处理流程：

1. 执行监控检查（按轮询间隔休眠）。
2. 收到匹配消息时，发送通知到主 session（`send_message`，`severity: "info"`）。
3. 每轮检查前比较当前时间与截止时间；达到截止时间后：
   - 发送最终通知（`send_message`，`severity: "success"`）。
   - 结束工作流。