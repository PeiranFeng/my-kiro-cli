# 读取 PR 源码

comments 与 review 两个接口共用。

## 方法

不切换分支。先 fetch 再用 `git show` 读远程分支文件；每一步验证成功后才继续，因为读到的内容是后续分析的唯一依据，读错而未发现会让全部分析建立在错误内容上：

```bash
git -C ~/data/<repo> fetch origin
git -C ~/data/<repo> show origin/<headRefName>:<path/to/file>
```

执行 git 命令前先明确目标仓库。

- fetch 失败（网络、路径错）：停止并报告，不用可能过期的本地 `origin/<headRefName>` 继续。
- `git show` 失败（分支或路径不存在、`fatal: invalid object name` 等）：停止，核对 `headRefName` 与路径和 PR 元数据一致后重试，不凭猜测继续。
- 每次 `git show` 前确认路径出现在 diff 里；需要追到 diff 之外的类型实现时，路径须来自 diff 中的引用。

## 阅读入口

- compass-app-jasper：从 `app2/Makefile` 或 `app2/train.py` 出发，追踪 diff 涉及的模块。
- compass-core、fenghe-nn：从 diff 涉及的 `test/` 测试文件出发，追到实现。
- 其他仓库：从 diff 涉及的文件出发，追到实现。

## 核实规则

- diff 涉及的自定义类型，以及被指控有问题的代码所涉类型，必须追到实现文件、验证实际行为后再下结论。
- 用搜索确认"某调用不存在""某字段无人使用"时，适用 `20-engineering.md#empty-search-not-absence`：空结果须换一种方法二次确认。
