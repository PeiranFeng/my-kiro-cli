---
name: user-snowflake
description: 用 snow CLI 查询、建表、传文件到 Snowflake 的命令模板与操作流程；FeatureLab dbt 项目的开发工作流建议（access control、PR/code review、测试验收、DEV migration）；在个人/私有 schema 只读 PROD 做测试的方法与限制；本地编译 dbt project 的方法；手动上传 zip 到个人 PYTHON_STAGE 的命名规范。当用户要求查询 Snowflake 数据、执行 SQL、上传/下载 stage 文件，询问 feature-lab 仓库的 dbt 开发流程、PR 规范、环境隔离、测试策略，要在个人/私有 schema 里用 PROD 数据做 dbt 测试，要本地编译/运行 dbt 而不消耗 Snowflake 侧 credit，或要手动上传 preprocess_evaluate 等 Python zip 到 PYTHON_STAGE 时使用。
---

# user-snowflake

访问入口、连接配置位置、认证限制见 `50-project-facts.md#snowflake`。

## FeatureLab dbt 开发手册

`feature-lab` 仓库（dbt on Snowflake 项目，见 `50-project-facts.md#repos`）的团队开发工作流规范记录在同目录的 `snowflake-guide.md`，覆盖 access control、PR 与 AI review、生产正确性验收、DEV 环境迁移四个部分，按 `### 标题 {#slug}` 组织，每条可用锚点引用。

用户询问 FeatureLab 的 dbt 开发流程、权限边界、PR 该附带什么证据、测试该怎么分层、如何安全地做 DEV migration 等问题时，读取 `snowflake-guide.md` 取对应章节作答，不要整段转述——先定位用户的具体问题落在哪个章节（如"写错 schema"对应 §1 access control，"PR 该带什么"对应 §2.4，"测试没通过但数据已经写进去了"对应 §3 release evidence），再基于该章节给出针对用户场景的具体建议，并指出该章节记录的限制（如"这是目标状态还是现状"，见 §4.3 cicd-gates-status 的现状/目标区分）。

guide 中的示例（Alice/Bob/Carter、source/x/y/z）是说明机制用的占位，给真实 `feature-lab` 仓库建议时需替换为实际 model 名、实际开发者 role、实际 schema，必要时先用 `code`/`grep` 工具核对仓库当前配置与 guide 记录是否一致——guide 本身也标注了部分机制（如 DEV deployment 是否已启用）记录的是写作时点状态，不代表当前必然如此。

用户要在个人 schema 里只读 PROD 做测试时，先读 `personal-schema-testing.md`——记录了判断某个 model 能否 defer 的方法（看依赖声明方式，不是看它在哪个目录下）、以及 `models/preprocess` 层为什么是已知的例外，不能 defer 必须 full-refresh 到自己 schema（`sibling_relation` 绕过 `ref()` 解析）。

涉及本地跑 dbt 编译/执行而不是 Snowflake 侧编译时，读 `local-dbt-compile.md`——记录为什么优先本地编译（省 credit、改 `--vars` 不留 commit 痕迹）以及编译产物如何重定向到仓库外。

要手动上传 zip 到个人 `PYTHON_STAGE`、或要确认 stage 上某个 zip 对应哪个 commit 时，读 `python-stage-upload.md`——记录个人上传 zip 必须带 commit 短 hash、和官方 CI 自动上传的固化包如何区分，以及 `imports=`/`preprocess_procedure` 变量怎么用 `--vars` 指向个人上传的版本。

## 连接名

连接名取值见 `.kiro/local-context.sh` 的 `SNOWFLAKE_CONNECTION`，执行前先读取该文件。所有命令显式带 `-c "$SNOWFLAKE_CONNECTION"`，不依赖默认连接。

## SQL 查询

```bash
snow sql -c "$SNOWFLAKE_CONNECTION" -q "<SQL 语句，对象名写全限定形式 <db>.<schema>.<object>>"
```

多行 SQL 用文件：

```bash
snow sql -c "$SNOWFLAKE_CONNECTION" -f <sql文件路径>
```

## Stage 文件操作

列出 stage 内容：

```bash
snow stage list-files -c "$SNOWFLAKE_CONNECTION" "<db>.<schema>.<stage名>"
```

上传文件（跨出个人 `DEV_<name>` schema 的写操作先与用户确认，见 `50-project-facts.md#snowflake`）：

```bash
snow stage copy -c "$SNOWFLAKE_CONNECTION" <本地文件路径> "@<db>.<schema>.<stage名>"
```

下载文件：

```bash
snow stage copy -c "$SNOWFLAKE_CONNECTION" "@<db>.<schema>.<stage名>/<文件名>" <本地目标目录>
```

## 注意事项

- 禁止给 `snow` 命令加 `conda run` 前缀——`snow` 由 `uv tool` 独立安装，位于 conda 之外。
- 禁止把 `config.toml` 中的口令、私钥内容或其它取值复述进回复、仓库、steering、skill。
- 遇到 `authenticator = "SNOWFLAKE_JWT"` 报 JWT 无效，不调参重试，改用口令连接或请有权限者注册公钥。
