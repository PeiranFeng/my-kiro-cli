# 清理个人 schema 与本地测试产物

接口是 `scripts/personal_schema_clean.py`（用法与范围见脚本头部）。

1. `list`：按 tag 列出个人 schema 的表、view、存储过程、`PYTHON_STAGE` 文件与本地目录；不带 tag 的对象单独列出。
2. 删除本地目录前，先在 `~/data/exp/` 与相关 issue、PR 正文中搜索该目录路径；被引用的目录里，被引用的文件先移到 `~/data/exp/` 下引用它的实验目录并改写引用，再删除。
3. 用户指定要清理的 tag 后，运行 `clean <TAG>`（只打印清单），把清单完整展示给用户并得到确认。
4. 确认后运行 `clean <TAG> --execute`。该 tag 下仍有存活的后台运行时脚本拒绝删除。
5. 不带 tag 的对象（规则出现之前的遗留）不由脚本删除；用户要清理时，逐个列出完整对象名并得到确认后，用 `drop` 手工删除。
