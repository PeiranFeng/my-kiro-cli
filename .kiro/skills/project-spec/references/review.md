# review

review 审查本 session 关心的设计或代码是否符合 `principles.md`，只写 `.project-spec/reviews/`。它不检查整个项目的一致性，那是 `maintain` 的职责。

## 范围

- 自动触发：`requirements` 或 `architecture` 后审查本次产出的 draft 文档；`build` 后审查本次改动的代码和测试。
- 用户调用 `review [scope]`：审查 scope 中的 ID 或文档子树及其对应代码；未给 scope 时审查本 session 最近一次命令的范围。

## 清单

- 需求文档：Q1 至 Q3。
- 架构与用例文档：A1 至 A8、T1、T2。
- 代码与测试：A2 至 A8、C1 至 C4、T1、T2。

结论遵守 R1、R2。

## 输出

报告写入 `.project-spec/reviews/<yyyy-mm-dd>-<scope>.md`，每条发现包含严重程度（blocking、important、suggestion）、原则 ID、位置和证据。

向用户只给简短反馈：各严重程度的数量，以及 blocking 和 important 发现各一句话。review 不修复，也不阻塞流程。
