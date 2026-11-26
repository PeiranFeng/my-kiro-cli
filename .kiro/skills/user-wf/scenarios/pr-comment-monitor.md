# 场景：监控 PR 评论

## 用户需提供参数

- **PR**：组织 `FinAI-Project` 下的仓库名和 PR 编号。用户未指定仓库时从上下文推断；未指定编号时询问。
- **comment 发送方**：具体的 GitHub 账户名。未提供时默认任何发送方都计数（包括 AI/bot reviewer）。
- **baseline 时间**：UTC 时间。未提供时默认工作流启动时刻。

## 工作流 prompt 要求

1. **只读操作**：只调用 `gh api` GET 请求或 `gh pr view`；禁止发评论、编辑、删除任何 GitHub 对象；禁止修改本地或远程文件。
2. **检查内容**：每轮轮询（间隔 120 秒）检查：
   - 行内评论：`repos/FinAI-Project/<repo>/pulls/<n>/comments`
   - PR 级评论：`repos/FinAI-Project/<repo>/issues/<n>/comments`
   - reviews：`repos/FinAI-Project/<repo>/pulls/<n>/reviews`
   三个接口都使用 `--paginate`。
3. **过滤**：
   - 只保留 `created_at` 或 `submitted_at` 晚于 baseline 的项目。
   - 当指定 sender 时，只保留 `user.login` 等于该账户名的项目。
4. **北京时间转换**：将 UTC 时间字符串解析为时间戳后加 8 小时（28800 秒），再格式化为 `YYYY-MM-DD HH:MM:SS`。
5. **通知内容**：每条匹配消息包含：
   - 类型：`inline`（行内）/`pr-level`（PR 级）/`review`
   - 文件路径和行号（仅 `inline` 类型）
   - 创建/提交时间（北京时间）
   - 内容（正文原样引用，总长截断到 3000 字符）
   - URL（`html_url`）
6. **工作流结束**：按生命周期处理（见 `lifecycles.md`）。