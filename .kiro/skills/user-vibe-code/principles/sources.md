# 出处与取舍

`principles/` 各文件里的规则所依据的文献与公开实践。条目的验证情况：文献指已读取该链接的内容，二手指只读到他人的摘要或转述，未核实指仅凭模型内部知识。核实日期 2026-11-23。

## 防御与失败方式

### 契约式设计

- 概念：调用方与被调方对各自的权利与责任达成约定；前置条件满足时，被调方保证后置条件。这是第一道防御，让每一方只对自己的部分负责。
- 适用边界：通用。
- 验证情况：文献，[The Pragmatic Programmer, Topic 23](https://www.informit.com/articles/article.aspx?p=2982114)；术语由 Bertrand Meyer 提出，见 [TechTarget 的转述](https://www.techtarget.com/it-infrastructure/feature/Learn-5-defensive-programming-techniques-from-experts)。

### 死程序不说谎，崩溃而非破坏

- 概念：发现"不可能"的事已发生时，程序已不可信，应尽快终止；死程序造成的损害通常小于残废程序。先捕获再原样抛出的写法会使调用方与被调方的异常列表耦合，应省去。
- 适用边界：可以安全退出的环境；需要释放资源、收尾事务的环境，原则不变，退出前做必要清理。Erlang 系语言用监督树管理失败。
- 验证情况：文献，[The Pragmatic Programmer, Topic 24](https://www.informit.com/articles/article.aspx?p=2982114&seqNum=2)。

### Art of Unix Programming 的相关规则

- 概念：Rule of Repair，必须失败时要尽早、响亮地失败；Rule of Silence，没有意外要报告就保持沉默；Rule of Simplicity，设计求简，只在必须时加复杂度；Rule of Parsimony，只在证明别无他法时才写大程序；Rule of Clarity，清晰优于技巧；Rule of Robustness，健壮来自透明与简单；Rule of Representation，把知识折进数据，使程序逻辑简单而健壮。
- 适用边界：通用设计原则，不是可机械执行的检查项。
- 验证情况：文献，[规则列表的转录](https://gist.github.com/jiafulow/6fbfe0844a116c4cbfcf98da75ed495f)，其原文来源为该书第 1 章第 6 节。

### 接口易于正确使用、难以错误使用

- 概念：设计接口时考虑使用者可能犯的错，使错误用法无法表达。
- 适用边界：通用，示例以 C++ 为主。
- 验证情况：文献，Scott Meyers 的 [The Most Important Design Guideline?](https://www.aristeia.com/Papers/IEEE_Software_JulAug_2004_revised.htm)，对应 Effective C++ 的该条目。

### 对输入的宽容接受

- 概念：Postel 的"发送保守、接收宽容"原则在互操作的短期内有利，对主动维护的协议长期有害，应避免。
- 适用边界：协议设计场景；迁移到一般代码是类比，未核实。
- 验证情况：文献，[RFC 9413](https://www.rfc-editor.org/info/rfc9413/)。

### AI 生成代码的静默兜底

- 概念：被要求谨慎时，代码生成模型倾向于包一层 try/catch、为每个失败加兜底、出错时返回看似安全的值，使程序不崩但也不报错。区别在于防御"错误输入"与防御"程序暴露出错误"，前者有益，后者有害。
- 适用边界：来自一篇产品博客，引用了社区讨论，属二手经验，不是研究结论。
- 验证情况：文献（二手），[The Fallback Trap](https://www.braingrid.ai/blog/the-fallback-trap)。

### 校验放在信任边界（壁垒）

- 概念：在信任边界上校验所有外来数据的类型、长度、范围，边界以内视为安全；发现坏数据后要决定处理策略（立即报错、返回中性值、替换），在健壮与正确之间取舍，策略清晰一致；用断言记录假设与"不可能"的情形；异常处理只在需要时使用；防御性编程不是吞掉错误或隐藏缺陷。
- 适用边界：Code Complete（Steve McConnell）防御式编程一章。
- 验证情况：文献（二手摘要），[being just-enough paranoid](https://gist.github.com/alexandervantrijffel/007ac7a45dac6382f7bb)；未读原书。

## 设计复杂度与一致性

### 把错误从设计中定义掉

- 概念：异常处理是软件复杂度最大的来源之一；处理特殊情形的代码比处理正常情形的难写。减少需要处理异常的地方有四种手段：改变语义使错误不存在、在低层屏蔽、把多处异常聚合到一处处理、直接崩溃。限度是，调用方需要知道的错误不能被隐藏。
- 适用边界：A Philosophy of Software Design（John Ousterhout，Stanford）第 10 章。
- 验证情况：文献（二手摘要），[thedeployguy 的章节摘要](https://thedeployguy.com/2019-06-16-a-philosophy-of-software-design-summary-part-2-cp10-end/)；未读原书。

### 一致性与入乡随俗

- 概念：一致性减少错误，在一处学到的东西可用于理解其他处。最重要的约定是看到像约定的东西就遵循；不随意改既有约定，要改就改到底，使旧约定不留痕迹。修改既有代码时，改完的结构应像一开始就这样设计的，不靠补丁。
- 适用边界：APOSD 第 16、17 章。
- 验证情况：文献（二手摘要），同上链接。
- 概念：编辑代码时先看周围代码的风格并照做；新加入的代码与周围代码差异过大会打断读者。一致性的适用在局部更强，也不能成为不考虑新风格好处的借口。
- 适用边界：Google Python 风格指南的结尾部分，对其他语言同理。
- 验证情况：文献，[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)。

### Yagni

- 概念：不构建为推测的未来需求而写的功能。理由有三：推测常常是错的，已有研究显示被精心分析过的功能也只有约三分之一改善了目标指标；构建它会延迟其他有价值的功能；它增加的复杂度提高之后每个功能的修改成本。为未来灵活性而加的抽象，若让当前需求的代码更难读，默认有罪。
- 适用边界：只针对"现在引入、之后才用到"的复杂度；不禁止重构，也不禁止自测试代码等使代码易于修改的做法。
- 验证情况：文献，[Martin Fowler, Yagni](https://martinfowler.com/bliki/Yagni.html)。

## 测试设计

### 等价类划分

- 概念：把输入按预期得到相同结果分成类，每类取代表值，用较少用例覆盖大量输入。前提是同类中一个值正确则其余值也正确。
- 适用边界：黑盒设计；分类依据须来自需求，不是随意划分。
- 验证情况：文献，[Complete Guide to EP Testing](https://mastersoftwaretesting.com/testing-fundamentals/equivalence-partitioning)。

### 边界值分析

- 概念：缺陷倾向聚集在取值区间的边缘，对每个边界取边界上与两侧的值。
- 适用边界：输入有明确的有序区间时。
- 验证情况：文献，[Complete Guide to BVA Testing](https://mastersoftwaretesting.com/testing-fundamentals/boundary-value-analysis)。

### 决策表与状态转换

- 概念：标准测试设计技术共五种：等价类划分、边界值分析、决策表、状态转换、用例测试。决策表用于多条件组合，状态转换用于行为取决于历史。
- 适用边界：通用。
- 验证情况：文献，[Test Case Design Techniques Explained](https://testpad.com/test-case-design/)。

### 测试行为而非方法

- 概念：按行为而非按方法组织用例；通过公开接口测试，断言状态而非内部交互；用例名称说明所测行为；用例内不放逻辑；用例自成一体，完整而简洁。
- 适用边界：单元测试；对测试辅助代码，允许为清晰而违反 DRY（即 DAMP 优先）。
- 验证情况：文献，[Software Engineering at Google, 第 12 章](https://abseil.io/resources/swe-book/html/ch12.html)，在线全文。

## 约束 AI 编程的公开实践

### 阅读过的来源

- [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md)：四条原则，先想后写（列出假设与多种解读）、简单优先、手术式改动（每行改动可追溯到请求，只清理自己造成的孤儿）、目标驱动（把任务转成可验证的标准）。全文已读。
- [guard-skills 的 ai-failure-modes](https://github.com/amElnagdy/guard-skills/blob/master/skills/clean-code-guard/references/ai-failure-modes.md)：15 种 AI 代码失败模式，每条附出处与规则。全文已读；其中的出处是该文件的引用，我没有逐一核对原论文。
- [code-humanizer](https://github.com/LeonardNJU/code-humanizer)：16 种 AI 代码坏味道，三条铁律（行为保持、无测试不修改、一类一提交），并有"有理由则豁免"的误报防护。README 已读。
- [boring-engineering](https://github.com/alvindemesadev/boring-engineering/blob/main/SKILL.md)：需求过滤、先复用、先用内置、抽象准入三问。全文已读。
- [GitClear 研究页](https://gitclear.com/the_ai_code_quality_maintainability_gap)：只读到搜索摘要，未读全文。摘要称 2024 年是首次出现同一提交内的复制粘贴代码多于被移动（重构）的代码，含重复块的提交在两年内增长约 10 倍。

### 已采纳

- 每行改动可追溯、清理自己造成的孤儿、多种解读时列出（Karpathy）。采纳于 `principles/scope.md`。
- 抽象须有两处以上现存使用方、先复用再新写、新增依赖要有确认的需求（guard-skills、boring-engineering）。采纳于 `principles/repo-conventions.md`。
- 每个 import 与外部调用核实实际安装的版本（guard-skills）。采纳于 `principles/data-contract.md`。
- 未实现时显式失败，不返回占位成功值，不改测试求通过（guard-skills）。采纳于 `principles/failure.md` 与 `principles/testing.md`。
- 清理类改动保持行为不变，包括错误类型；无测试时只报告（code-humanizer）。采纳于 `principles/repo-conventions.md`。
- 豁免规则：信任边界的校验、有书面理由的兜底、仓库既有约定、声明为探索的代码（code-humanizer、boring-engineering）。采纳于 `interfaces/code-review.md`。
- 无效测试：只断言 mock、字面量断言、场景重复（code-humanizer）。采纳于 `principles/testing.md`。

### 没有采纳

- 函数长度、参数个数、圈复杂度的数值上限：属于通用代码设计，归 `user-review`。
- "发现无关的死代码时提一句"：与 `00-collaboration.md#stay-on-task` 冲突，范围外问题不处理。
- "输入校验与错误处理在任何情形都可保留"：与边界以内的三问冲突，只采纳信任边界处的部分。
- "内联优于抽取""尽量单行"：属风格偏好，以仓库既有写法为准。
- "模型倾向吞异常的根因是训练时的奖励信号"：来源未给出可核实的依据，不作为结论，只作为一种待验证的解释。

## 阅读范围

- 已读到可核实内容：The Pragmatic Programmer、The Art of Unix Programming、Code Complete（二手摘要）、A Philosophy of Software Design（二手摘要，见 `design-and-consistency.md`）、Software Engineering at Google（原文，见 `test-design.md`）。
- 《编程之美》是约 60 道算法与程序设计题的集合，不含编程原则，未收录。
- 《编程的原则：改善代码质量的101个方法》与《Effective Python》未能找到可核实的内容，未收录。
