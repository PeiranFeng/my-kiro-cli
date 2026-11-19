# 测试写入的命名：test tag

个人 schema（`DEV_<USER>`、`DEV_<USER>_PREPROCESS`）上由测试创建的每个对象，以及测试在本地产生的每个文件（zip、manifest、dbt 的 target 与 logs、比对结果），都带上该测试所属的 test tag。清理接口按 tag 找全一次测试的全部产物，名字里没有 tag 的对象只能列出、不会被清理。

- 格式与各类对象的名字模式以 `scripts/test_tag.py` 为准，`python3 scripts/test_tag.py names <TAG>` 打印该 tag 拥有的模式。
- tag 指向测试服务的 PR、issue 或 commit，从当前任务推断：有 PR 用 PR，否则用 issue，都没有用 commit。推断出的 tag 与分支一起交用户确认（`testing/build.md`）。
- 接口（`deploy.sh`、`preprocess_build.py`）自动按 tag 命名；接口之外的临时写入（快照表、比对表等）按 `test_tag.py` 的同一模式手工命名，本地文件放进该 tag 的本地目录。
- `preprocess_build.py` 的上游快照命名为 `<上游表名>__<TAG>__S<时间>`（在 `DEV_<USER>`），每次 build 的输出 clone 命名为 `<层内表名>__<TAG>__B<时间>`（在 `DEV_<USER>_PREPROCESS`）；快照与 build 的记录在 tag 本地目录的 `snapshots/`、`runs/` 下，清理 tag 时一起删除。
- 换连接或换场景前留下的交接记录写进 `notes/`（`SKILL.md` 的连接一节），与快照、build 记录同在 tag 本地目录下。
- preprocess 层自身的 model 表与 view 名字由 dbt 决定、不带 tag，每次 build 覆盖，所有任务共用；要保留某次的结果就 clone 成带 tag 的表。同一时间只允许一个任务在个人 schema 上 build，见 `SKILL.md`「所有场景通用」。
