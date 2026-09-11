---
inclusion: always
---

# 项目事实

## 项目概述  {#overview}

这个控制台目录（`~/data/my-kiro-cli`）存放 Kiro 配置（steering、skills），用于操控 `~/data` 下的多个项目仓库。`compass-app-jasper` 是量化研究平台主仓库，`compass-core` 是它唯一 submodule 的源仓库，两者共用本控制台的配置。fenghe-nn 的代码已并入 `compass-core` 的 `lib/fenghe-nn`。

## 仓库关系  {#repos}

| 仓库路径 | 角色 | 主分支 |
|---------|------|--------|
| `~/data/compass-app-jasper` | 主仓库（量化研究平台），含一个 submodule `core/` | — |
| `~/data/compass-core` | submodule `core/` 的源仓库（底层数值运算，含 `lib/fenghe-nn` 的 GPU 内核 / PyTorch 绑定） | `develop` |
| `~/data/fenghe-nn` | 历史独立仓库，代码已并入 `compass-core`，不再作为开发入口 | `develop` |
| `~/data/test/` | 临时实验输出目录 | — |
| `~/data/exp/` | 持久化实验输出目录 | — |
| `~/data/review/<repo>/<branch>/` | review 输出目录，按仓库+分支分类，避免同名冲突 | — |

`compass-app-jasper/core/` 是 submodule，对应 `compass-core`，在 jasper 中是 detached HEAD 状态，`git checkout` 到具体 commit 才生效。submodule 联合开发流程见 `user-update-submodule` skill。

## 架构约束  {#architecture-constraints}

### 不在仓库内跑实验/测试  {#no-run-in-repo}

`[review]` 实验和测试一律在独立输出目录（`test/`、`exp/`）运行，禁止在仓库目录内直接运行——Hydra 等会生成 `outputs/`、`train/`、`merged/` 等产物污染仓库代码。运行前确认工作目录在仓库之外。

### Hydra 管理的工作通过配置，不硬编码  {#hydra-config-not-hardcode}

`[review]` 凡由 Hydra 负责的工作（实例化、超参设置等），其配置一律在 `app2/conf/` 下对应的 config group 中书写，禁止硬编码到代码中。需新增配置项而对应配置文件不存在时，先询问用户该配置应如何增加，不自行在代码里绕过 Hydra 配置体系。

### app2 是当前版本  {#app2-current}

新工作一律用 `app2/`，`app/` 是旧版 v3。

## 本机配置  {#local-context}

机器相关配置（conda 环境名、路径等）集中在本机文件 `.kiro/local-context.sh`，该文件不纳入版本控制（每台机器自建，模板见 `.kiro/local-context.sh.example`）。执行任何实验或测试前先读取该文件确认变量值，禁止把机器相关值硬编码进 steering、skill 或命令。命令自带环境激活前缀（如 `conda run -n $CONDA_ENV ...`），不依赖预先注入的环境。具体用法见 `user-run-experiment`、`user-run-tests` skill。
