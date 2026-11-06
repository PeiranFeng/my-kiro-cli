# 线上 build 报错调查

适用于 `FEATURELAB` 的 DEV/PROD 定时 build 或部署失败的排查。个人身份只能读，不能写 DEV/PROD，整个调查用只读查询和个人 schema 内的复现完成。

## 1. 先拿到完整报错

- 告警和 Snowsight 摘要里的报错会被截断，根因常常在被截掉的那一段（嵌套存储过程、UDTF 注册这类二层调用栈里）。只根据截断后的报错下结论容易归错原因。
- 报错末尾提示的 `system$get_dbt_log('<query id>')` 只有 DEV/PROD dbt project 的 owner 能查。个人 role 以及 `FEATURELAB_DEV_READ`/`FEATURELAB_PROD_READ` 都会返回 "DBT project not found or access denied"。`snow` 会话是受限会话，不能执行 `USE ROLE`/`USE SECONDARY ROLES`。拿不到完整日志时，直接转到第 4 步复现。

## 2. 用只读元数据判断各环境的影响范围

- `FEATURELAB.INFORMATION_SCHEMA.TABLES` 的 `LAST_ALTERED` 记录每张表最后一次重建的时间。把同一 schema 里上下游表的时间放在一起比，就能看出哪些 model 这次建成了、哪些停在了上一次成功的时间。拿不到日志的环境（通常是 PROD）就靠这个推断失败的 model。
- `FEATURELAB.INFORMATION_SCHEMA.COLUMNS` 可以查表的列数和列名长度，用来核对 schema 变化以及和对象定义长度有关的限制。
- 时区要统一换算：Snowflake 返回的是账号时区（`-08:00`），`gh run list` 是 UTC，告警是 Asia/Shanghai。

## 3. 建时间线，确认环境实际跑的代码版本

- 把三类事件按时间排在一起：feature-lab 和依赖库各自的 `gh run list`（合并、Deploy、bundle 上传），以及表的 `LAST_ALTERED`。第一次失败的 build 之前最近的一次代码变更就是首要嫌疑。
- 某个环境用的是哪个分支的依赖包，由 feature-lab `.github/workflows/deploy.yaml` 的 promote 步骤决定。按该步骤的规则和依赖库现有分支推出实际来源，不要假设 PROD 只跑 main 的代码。
- 依赖包更新后，环境要等下一次 Deploy 才会切换到新包。判断某次 build 用的哪个版本，要看这次 build 前最近一次 Deploy 的时间，而不是包上传的时间。

## 4. 在个人 schema 复现

- 共享 stage `FEATURELAB.PUBLIC.FEATURE_LAB_PYTHON_STAGE` 和环境 stage 个人都不能读，所以在仓库外用 `git archive <commit> | tar -x` 导出可疑 commit，再按 `python-stage-upload.md` 打包，上传到个人 `PYTHON_STAGE`，并建一个带 hash 后缀的存储过程。
- `snow stage copy` 默认不覆盖：目标路径已有同名文件时，状态显示 `SKIPPED`，stage 上留的还是旧文件。上传后检查状态列，出现 `SKIPPED` 就换一个新路径重新上传，否则复现跑的不是目标 commit。
- 复现时直接 `CALL` 个人过程，参数照抄线上 model 的调用参数（配置名、rule、stage），输入表用 DEV 的上游表（`FEATURELAB_DEV_READ` 可读）。这样不用跑 dbt 就能复现单个失败的调用，拿到完整报错。
- 复现得到的调用栈要和线上报错逐行比对，文件名和行号都一致才能认定是同一个问题。

## 5. 定位引入变更

- 对嫌疑合并用 `git diff <merge>^1 <merge> --stat`，再用 `git log <merge>^1..<merge>^2 -- <路径>` 找出改了线上路径文件的那几个 commit。
- 新入口、实验版、标注了 "test-only" 的代码，仍可能改到正式入口也在调用的共享函数。要从正式入口（如存储过程 handler）出发，用 grep 找出被改函数的所有调用位置，确认改动是否进了正式路径。
- 想知道限制到底是哪个维度触发的（列数、名字长度、数据量等），在个人 schema 里建只改变这一个维度的最小临时对象来分别测试，不要靠推测。

## 6. 结论与修复

- 结论里分开写两类：复现直接证实的，和从时间线或元数据推断的。推断的部分要说明依据。
- 本地 Snowpark 测试不会真的在 Snowflake 上建对象，所以 UDF/UDTF/存储过程的定义长度、签名之类的目录限制只会在真实 warehouse 里报错。这类问题的修复要附一次个人 schema 的真实调用作为验证。
- 修复只能走 git 推送触发 CI（见 `50-project-facts.md#preprocess-evaluate-stage`）。PROD 要等下一次 Deploy 把新包复制过去才会恢复，修复说明里写清楚这一点。
- 调查结束后，告诉用户在个人 schema 里留下的临时过程和 stage 文件，由用户决定是否清理。
