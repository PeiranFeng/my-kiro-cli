# preprocess 层的结构事实

`feature-lab` 的 `models/preprocess/` 层把 mart 层的原始因子整理成 `preprocess_evaluate` 存储过程的输入，调用该过程做 fill 与 normalize，再发布结果与统计。本文只记录跨 model、跨仓库、看单个文件看不出的机制；model 清单与数据流随分支变化，不写在 skill 里。

## 数据流：按分支生成

`scripts/layer_flow.py --ref <ref>`（用法见脚本头部）从一个 git ref 解析出该层每个 model 的物化方式、`ref()` 依赖与按名字读写的兄弟表；`--against <ref>` 列出两个 ref 之间增删的 model 与边。

- 回答"线上现在怎么流"，用 `--ref origin/dev`（PROD 用 `origin/main`）；回答某个分支或 PR 的结构，用它的 head 分支。
- 存在改动该层结构的未合并分支时，用 `--ref origin/dev --against <分支>` 说明合并后会变成什么，并注明它尚未合并。
- 各 model 的粒度、语义与列说明以 model 文件头注释和 `_preprocess_models.yml` 为准，按上面输出的名字去读对应 ref 的文件（`git show <ref>:<路径>`）。
- 新增原始因子接入时，只改汇总原始因子的那个 model：在目标 ref 的输出里，它是 stock 侧直接 `ref()` 多张 mart 因子表的 model；其下游的过滤 view 与 fill model 读它的全部列，无需改动。

## 读兄弟表不走 dbt 的 relation 解析

Python model 读同层输入与写 `*_scale_audit` 时，用 `preprocess_evaluate` 的 `orchestration.sibling_relation(dbt.this, name)`：取 `dbt.this` 的 database 与 schema，拼上兄弟表名。由此：

- 个人测试时读写的都是 `DEV_<USER>_PREPROCESS` 下的表，`--defer`/`--state`/`--favor-state` 改变不了；这一层必须在个人 schema 里整层 `--full-refresh` 构建，上游 mart 层可以 defer。
- 模型里的 `dbt.ref(...)` 只让 DAG 排出顺序，实际读的是 `sibling_relation` 拼出的路径，两者可能不一致；判断一个 Python model 能否 defer，看它的 helper 是否按名字拼表，不看是否写了 `dbt.ref`。层外的 model 被按名字引用时同理，例如 `fact_pool_weight_source` 读 `fact_weight_dense`。

## 存储过程与 zip 的定位

`_preprocess_models.yml` 中每个 Python model 的 `imports` 默认是 `@<target.database>.<target.schema>.PYTHON_STAGE/preprocess_evaluate/current/preprocess_evaluate.zip`，`meta.procedure` 默认是 `<target.database>.<target.schema>.PREPROCESS_FACTORS`，可分别用 dbt 变量 `preprocess_bundle`、`preprocess_procedure` 覆盖。`macros/preprocess_runtime.sql` 只在 `prod` target 拒绝覆盖。个人测试一律用 `testing/deploy.md` 部署出的 zip 与过程，并以这两个变量指过去。

## 因子列的发现

因子列由 dbt 在运行时从 relation 元数据发现（如读取评分表的现有列并展开 ARRAY 列），宏与源码不能代替部署后的核验。核对列数或血缘时，查目标 schema 的 `INFORMATION_SCHEMA.COLUMNS`，分别比对输入 relation 与输出 relation 的列集合。按名字写入的兄弟表（如 normalize 写出的 scale 审计表）不是 dbt model，只出现在 `layer_flow.py` 的 by name 一栏。
