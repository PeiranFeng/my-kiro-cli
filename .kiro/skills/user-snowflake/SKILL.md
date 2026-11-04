---
name: user-snowflake
description: Snowflake CLI 查询与 stage 操作，以及 FeatureLab dbt、个人 schema 测试、本地编译和个人 Python bundle 发布的按需工作流入口。用户要求这些操作或相关规范时使用。
---

# user-snowflake

访问入口、连接配置位置、认证限制见 `50-project-facts.md#snowflake`。

## 按需数仓背景

- FeatureLab dbt 开发工作流、权限、评审、验收和 DEV migration：读取 [snowflake-guide.md](snowflake-guide.md) 的相关标题；涉及当前仓库状态时同时核对 `feature-lab` 代码。
- 个人 schema 使用 PROD 数据测试：读取 [personal-schema-testing.md](personal-schema-testing.md)。
- 本地编译或执行 dbt：读取 [local-dbt-compile.md](local-dbt-compile.md)。
- 个人 `PYTHON_STAGE` 上传 zip 或确认 zip 对应 commit：读取 [python-stage-upload.md](python-stage-upload.md)。
- preprocess 因子 source、物化 schema、上游 relation 或因子列数：读取 [preprocess-factor-lineage.md](preprocess-factor-lineage.md)。

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
