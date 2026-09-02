---
name: user-run-tests
description: compass-app-jasper / compass-core / fenghe-nn 三个仓库的测试运行命令模板与测试框架判定规则。当用户要求跑测试、验证代码改动时使用。
---

# user-run-tests

三个仓库的测试运行方式。运行前先读 `.kiro/local-context.sh` 取 `CONDA_ENV` 等机器相关变量（见 `50-project-facts.md#local-context`），命令自带 `conda run -n $CONDA_ENV` 前缀，不依赖预先注入的环境。

## 测试框架不可按目录预判

jasper 仓库内 unittest（继承 `unittest.TestCase`）和 pytest（普通函数 + `assert`/pytest fixture）风格的测试文件都可能存在，不能按目录或仓库预判框架。执行前先打开目标脚本确认写法，再选用对应命令模板。

## compass-core

```bash
cd ~/data/compass-core
env CUBLAS_WORKSPACE_CONFIG=:4096:8 conda run -n $CONDA_ENV python -m pytest test/
```

## fenghe-nn

```bash
cd ~/data/fenghe-nn/python
pip install -e .   # 安装（含 C++ 扩展编译）
conda run -n $CONDA_ENV pytest test/
```

Python 包名 `finai`，import 路径 `from fenghe.xxx import ...`。

## compass-app-jasper

pytest 风格：

```bash
cd ~/data/compass-app-jasper
env PYTHONSAFEPATH=1 PYTHONPATH=$PWD/core:$PWD/app2:$PWD/lib:$PWD/lib2/python \
  conda run -n $CONDA_ENV python -m pytest <test_file_or_dir> -v
```

unittest 风格：统一直接执行脚本文件，不用 `unittest discover`——`discover -s <dir>` 会把该目录插到 `sys.path[0]`，若目录下存在与依赖模块同名的 fixture 目录会撞名导致导入错误。前提是文件末尾有 `if __name__ == "__main__": unittest.main()`：

```bash
cd <测试文件所在目录>
env PYTHONSAFEPATH=1 PYTHONPATH=$HOME/data/compass-app-jasper/core:$HOME/data/compass-app-jasper/app2:$HOME/data/compass-app-jasper/lib:$HOME/data/compass-app-jasper/lib2/python \
  conda run -n $CONDA_ENV python <测试文件名>.py -v
```

## 注意事项

- `fenghe` 是命名空间包，`lib/fenghe/` 和 `lib2/python/fenghe/` 合并；unittest 不执行 conftest，需手动在 PYTHONPATH 包含两个路径。
- tensor 相关测试必须跑在 GPU 环境（见 `30-domain-gpu.md#test-on-gpu`）。
