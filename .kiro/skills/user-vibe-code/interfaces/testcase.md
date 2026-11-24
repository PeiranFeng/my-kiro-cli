# 接口：testcase

设计并写测试用例。运行测试用 `user-run-tests` skill，不在此执行。

## 步骤

1. 判被测方法的复杂度，按 `20-engineering.md#coverage-standard` 选覆盖标准。
2. 列出被测方法对外承诺的行为和它依赖的数据契约。
3. 按 `principles/testing.md` 的等价类、边界值、决策表、状态转换推出用例；每个用例对应一个行为。
4. 给每个用例定期望值，来源须独立于被测实现。
5. 写测试：沿用仓库既有的测试位置、命名与夹具写法（`principles/repo-conventions.md`），测试的运行位置遵循 `50-project-facts.md#no-run-in-repo`。
6. 交出前按 `objects/测试.md` 列项，按 `checklist.md` 的四逐项打分，再回复。

## 回复内容

- 选用的覆盖标准及理由。
- 每个用例对应的等价类、边界、分支或行为。
- 期望值的来源。
