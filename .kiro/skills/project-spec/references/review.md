# review

review 审查本 session 关心的设计或代码是否符合 `principles/` 中的原则，只写 `.project-spec/reviews/`。它不检查整个项目的一致性，那是 `maintain` 的职责。

## 范围

`review bootstrap` 是独立的模式，审查 `bootstrap` 产出的文档是否忠实于现状，规则见 `bootstrap-review.md`；本文件描述的是普通 review。

- 自动触发：`requirements` 或 `architecture` 后审查本次产出的 draft 文档；`build` 后审查本次改动的代码和测试。
- 用户调用 `review [scope]`：审查 scope 中的 ID 或文档子树及其对应代码；未给 scope 时审查本 session 最近一次命令的范围。

## 清单

清单取自原则文件的 `stages`，运行 `scripts/principle.py list --stage <阶段>` 得到，新增的原则自动进入清单：

- 需求文档：stage 含 `requirement` 的原则。
- 架构与用例文档：stage 含 `design` 或 `test` 的原则。
- 代码与测试：stage 含 `code` 或 `test` 的原则。
- review 自身的结论：stage 含 `review` 的原则，对每次 review 都生效。

## 输出

报告写入 `.project-spec/reviews/<yyyy-mm-dd>-<scope>.md`，每条发现包含严重程度（blocking、important、suggestion）、原则（写成「ID [分层名] 名词短语」，分层名见 `principles/README.md`）、位置和证据。

向用户只给简短反馈：各严重程度的数量，以及 blocking 和 important 发现各一句话；提到原则时同样用该格式，不只写 ID。review 不修复，也不阻塞流程。
