---
inclusion: always
---

# git 与远程安全

## 执行 git 前明确目标仓库  {#identify-repo}

执行任何 git 命令前必须明确目标仓库。用户指令中没有明确说明是哪个仓库时，先询问，不得静默执行。涉及的仓库见 `50-project-facts.md` 的仓库关系。

## 影响远程的操作需明确确认  {#confirm-remote-ops}

所有对远程产生外部影响的操作——`git push`、`gh` 发评论/issue/PR、合并 PR、删除远程分支等——一律需用户明确指示后才执行，禁止自动或顺手执行。携带内容的远程操作（评论、PR 描述、issue 正文等），执行前必须先将完整内容展示给用户确认，不得在未经内容确认的情况下直接发送。

## push 前核对项目特有改动  {#pre-push-checks}

`[review]` `git push` 前逐项核对本次改动是否触及以下范围，触及则先与用户确认或处理，未处理的项在每次 push 前都要再问：
- 公开接口变更（函数签名、参数名、返回值结构、事件格式等）：主动提醒用户检查并更新对应的测试用例，不得默认测试会自动跟进。
- 实验产物结构变更（输出目录结构、文件名、文件含义变化）：与 `app2/README.md` 的输出结构描述比对，询问用户是否立即更新 README。

## 合并用 merge 不用 rebase  {#merge-not-rebase}

合并不同分支时必须使用 `git merge`，禁止使用 `git rebase`。rebase 改写提交历史，在多人协作分支上会造成混乱。

## 切换分支前先 fetch  {#fetch-before-checkout}

切换分支前必须先执行 `git fetch origin`，确保本地看到的远程分支状态是最新的。
