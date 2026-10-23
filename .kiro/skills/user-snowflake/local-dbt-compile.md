# 本地编译 dbt project，不用 Snowflake 侧编译

`feature-lab` 的 dbt project 既可以用 `dbt` CLI 在本机编译执行，也可以作为 Snowflake-hosted dbt Projects on Snowflake 对象在云端编译执行（`snowflake-guide.md#cicd-gates-status` 提到的 "Transformations → dbt Projects"）。本地测试、改 import 路径等场景优先用本机 CLI，理由是：

- **不产生 Snowflake 侧的编译/执行 credit 开销**——本机 `dbt compile`/`dbt build` 只在真正执行 SQL/Snowpark 时才消耗 warehouse credit，编译阶段本身在本机完成。
- **可以临时改动不进 git 历史**——用 `--vars` 覆盖 `preprocess_bundle`/`preprocess_procedure` 等变量（见 `python-stage-upload.md`）是运行时参数，不改仓库文件，不产生 commit；比直接改 `_preprocess_models.yml` 再 `git checkout` 复原更不容易留下误 commit 的痕迹。

## 编译产物不能放进仓库目录

按本控制台的架构约束（不在仓库内跑实验/测试），dbt 的编译产物（`target/`、`logs/`、`dbt_packages/`）不能留在 `~/data/feature-lab` 下，即使只是本地验证也要先确认 `.gitignore` 是否已排除，并优先在仓库外执行：

```bash
mkdir -p ~/data/test/<测试目录名>
cd ~/data/feature-lab   # dbt 项目文件需要在仓库内被发现，但产物目录重定向到仓库外
uv run dbt build --target personal --profiles-dir . \
  --target-path ~/data/test/<测试目录名>/target \
  --log-path ~/data/test/<测试目录名>/logs \
  --select <selector> \
  --vars '{...}'
```

`--target-path`/`--log-path` 把编译产物重定向到仓库外，执行完毕后到 `~/data/test/<测试目录名>` 下查看 `run_results.json`、编译后的 SQL 等产物，不依赖仓库内的 `target/` 目录。验证完成后清理该临时目录。

## 和 Snowflake 侧编译的差异

Snowflake-hosted dbt Projects 编译发生在 Snowflake 侧，project 代码需要先部署（`CREATE DBT PROJECT` 或等价操作）才能执行，不支持在不部署的情况下临时改 `--vars`。本机 CLI 编译不需要这个部署步骤，改完 `--vars` 立即生效，更适合一次性验证。两条路径读写的是同一套 Snowflake 对象（表、stage、存储过程），区别只在"谁执行 dbt 的编译和调度"，不影响最终数据落地位置的判断方法（见 `personal-schema-testing.md`）。

## 本机 CLI 连接 Snowflake 的凭据

`profiles.yml` 的每个 target 都用 `env_var('SNOWFLAKE_USER', ...)`/`SNOWFLAKE_PASSWORD`/`SNOWFLAKE_ACCOUNT` 读取连接凭据，这三个只认运行时的进程环境变量，不接受命令行参数、也不读 `snow` CLI 的 `~/.config/snowflake/config.toml`（两套凭据机制互相独立，配置好 `snow sql` 能连不代表 `dbt` 能连）。

凭据值在 `.kiro/local-context.sh` 里维护（见 `50-project-facts.md#local-context`），执行 dbt 命令前显式 `source` 到当前 shell，这是本控制台里少数几个必须 `source` 而非"读取后拼参数"的场景（因为 `env_var()` 不接受参数传值）：

```bash
cd ~/data/feature-lab
source ~/data/my-kiro-cli/.kiro/local-context.sh
export DBT_PERSONAL_ROLE=FEATURELAB_PERSONAL_<USER> DBT_PERSONAL_SCHEMA=DEV_<USER>
uv run dbt build --target personal ...
```

`DBT_PERSONAL_ROLE`/`DBT_PERSONAL_SCHEMA` 不放进 `local-context.sh`（不是机器相关值，是项目里"我是谁"的身份标识，按用户名可以从 `SNOWFLAKE_USER` 推导，但 `profiles.yml` 要求显式赋值，不会自动从其他变量派生）。

这套凭据机制不是 `personal` target 专属——`profiles.yml` 的 `dev`/`prod` target 同样读 `SNOWFLAKE_ACCOUNT`/`SNOWFLAKE_USER`/`SNOWFLAKE_PASSWORD`，但个人角色（`FEATURELAB_PERSONAL_<USER>`）通常没有被授予 `FEATURELAB_DEV`/`FEATURELAB_PROD` 这两个 role，**不要用 `--target dev`/`--target prod` 执行任何会触发真实 Snowflake 连接的命令**（`dbt debug`、`dbt build`、`dbt run`、`dbt test` 等）——连接会在权限校验阶段被拒绝，而且这类尝试本身就不该发生：改 `DEV`/`PROD` schema 的数据只能通过 CI/CD 走审批流程（见 `snowflake-guide.md` 的 access control 章节），不是本地个人可以绕过的操作。

`dbt parse` 是例外，纯本地解析 Jinja/YAML/依赖图，不连接 Snowflake、不需要任何角色权限，`--target` 只是选用哪个 target 的变量值做编译，不代表会用该 target 的身份登录（见 `personal-schema-testing.md` 的 manifest 获取方法，用的正是 `dbt parse --target prod`）。只有 `dbt parse` 可以安全地指定 `--target prod`，其余 dbt 子命令一律只用 `--target personal`。
