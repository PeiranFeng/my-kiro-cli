---
name: user-review
description: Code review 方法论、checklist 动态生成规则与回复规范。当用户要求做 code review、审查本地改动、审查 PR，或需要生成 review 检查清单时使用。
---

# user-review

Code review 的方法论、checklist 生成方式与回复规范。检查项本身不在此硬编码，而是运行时从 steering 文件的 `[review]` 标记动态生成——保证检查项唯一事实源在 steering，改原则不必同步本 skill。

## 生成 checklist

review checklist 由扫描所有 steering 文件中带 `[review]` 标记的语义标题动态生成，不手工维护清单：

```bash
grep -rn '\[review\]' .kiro/steering/
```

收集到的每个带标记的语义标题即一个检查项（如"复用优先"、"Tell Don't Ask"、"名实一致"）。标题是自解释的目的短语，生成的 checklist 直接可读。逐项对照被审查的改动核查。

## review 方法

- 悲观核查：默认假定可能仍有问题，不乐观假定没事。
- 下"已修复/非 bug/不受影响"这类结论前，必须实地调查验证（实际运行、写最小复现、追代码与配置链路），不得仅凭 commit message、他人描述或纯推理下结论。结论必须有调查证据支撑。
- 判断"某事物不存在"时遵循 `20-engineering.md#empty-search-not-absence`：搜索空结果须换一种方法二次确认。
- tensor 相关检查项须在 GPU 环境验证（见 `30-domain-gpu.md#test-on-gpu`）。

## 回复规范

- 回复须简短明确。已按意见修改的回复 "Agreed, fixed."；不认可的回复 "Not an issue." 并一句话说明原因。
- 回复位置必须与 comment 类型一致：inline comment 在对应 inline comment 下回复，top-level comment 在 top-level 下回复，禁止错位。
- 引用原则时用语义标题或 slug 锚点，且在当前句给足上下文，不使用裸锚点（见 `10-communication.md#self-contained-refs`）。

## 输出位置

review 结果按仓库+分支归类输出到 `~/data/review/<repo>/<branch>/`，避免跨仓库分支同名冲突。
