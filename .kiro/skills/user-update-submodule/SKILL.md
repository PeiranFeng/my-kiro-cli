---
name: user-update-submodule
description: compass-app-jasper 与其 submodule（compass-core）的联合开发流程，包括正常功能开发与临时 debug 修改的规范。当用户要求更新 submodule 指针、在 core 下开发或提交 submodule 相关改动时使用。
---

# user-update-submodule

`compass-app-jasper/core/` 是 submodule，源仓库是 `compass-core`（见 `50-project-facts.md#repos`）。

## 正常功能开发流程

1. 在源仓库（`~/data/compass-core`）开发、提交、推送。
2. 在主仓库更新 submodule 指针：

   ```bash
   cd ~/data/compass-app-jasper/core
   git checkout <新 commit hash 或分支>
   cd ~/data/compass-app-jasper
   git add core
   git commit -m "update submodule: ..."
   ```

禁止在 jasper 的 `core/` 子目录下直接提交功能修改。

## Debug / 临时修改

- 可以在 `compass-app-jasper/core/` 内直接改代码。
- 禁止将这类修改 push 到远程。
- 若验证有效，须回到源仓库重新提交，再走正常流程更新指针。

## 注意事项

- submodule 在 jasper 中是 detached HEAD 状态，`git checkout` 到具体 commit 才生效。
- 切换 jasper 分支会影响后台运行的实验；多分支同时跑需使用不同仓库目录。
- git 操作遵循 `40-git-safety.md`：明确目标仓库、影响远程需确认、合并用 merge、切分支前 fetch。
