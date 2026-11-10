# maintain

maintain 检查整个项目的文档与实现是否一致，只写 `.project-spec/maintain-report.md`，不改其他文件。它不评价设计好坏，那是 `review` 的职责。

## 检查

1. 结构：运行校验，`errors` 列出三棵树违反结构规则的地方，`unmappedSources` 列出没有架构文档的源文件。逐个判断这些源文件是否公开；公开的算缺失文档。
2. 需求与架构：每个 implemented 需求，引用它的架构设计能否真正满足它的验收条件。
3. 架构与代码：校验报告的 `inconsistencies` 给出文件、符号和结构清单层面的不一致；再逐个阅读 implemented 的 source 文档，核对「约束」中的不变量和错误是否与代码一致。
4. 用例与测试：implemented 的 cases 文档中每个场景是否有对应测试，测试断言是否与场景期望一致；运行这些测试并记录结果。

不一致的结论附文件、符号或命令输出作为证据，遵守 stage 含 `review` 的全部原则。

## 报告

每条不一致写明位置、证据和处理方向：

- 代码是对的：用 `bootstrap` 补文档，或用 `requirements`、`architecture` 修改文档。
- 文档是对的：把文档改回 approved 后用 `build` 修复代码。

向用户简短汇报各层的不一致数量和最重要的几条。
