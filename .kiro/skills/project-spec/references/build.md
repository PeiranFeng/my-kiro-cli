# build

build 实现 approved 的架构和用例文档，不修改文档内容；唯一允许的文档改动是 status 从 approved 改为 implemented。

## 开始

1. 运行校验。存在 errors 时停止并报告；`drafts` 非空时提醒用户审查并 `approve`，draft 文档不进入本次 build。
2. 记录报告中的 `specFingerprint` 和 `git status`。
3. 范围是全部 approved 的 source、cases 和 journey 文档。代码与测试路径取自报告的 `paths`。
4. 按依赖顺序拆成纵向任务，每个任务包含一个 source 文档、它的 cases 文档和相关 journey。

## 每个任务

1. 读取接口小节和用例小节。
2. 按用例和原则 T1 写测试，运行一次。测试已通过且代码与接口一致时，跳过实现。
3. 按原则 A、C 写满足接口的最小代码，不扩展范围。
4. 运行测试；同一失败最多修复三轮，仍失败时停止该任务并记录原因，不跳过测试、不放宽断言、不改文档。
5. 测试通过后把该 source 文档、cases 文档和已通过的 journey 改为 `implemented`。

一口气完成全部任务，中途不询问用户。

## 结束

1. 把子树内全部 source 文档 implemented 的 module 和 package 文档改为 `implemented`。
2. 把满足它的架构文档全部 implemented 的 approved 需求改为 `implemented`。
3. 运行项目约定的回归、构建和静态检查，无法运行的标为未验证。
4. 再次运行校验，`specFingerprint` 必须与开始时一致，否则说明 build 改了 status 以外的文档内容，报告失败。
5. 对比开始时的 `git status`，区分本次改动和用户原有改动。
6. 对本次全部改动执行 `review`，简短汇报完成和未完成的文档、失败原因、review 结论。

发现需求或架构需要变化时停止相关任务，报告给用户并建议用 `requirements` 或 `architecture` 修改。
