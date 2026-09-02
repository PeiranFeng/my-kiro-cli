---
inclusion: always
---

# 领域：GPU / tensor

## 不手动指定 tensor 的 device  {#no-manual-device}

`[review]` 项目通过 `try_to_use_gpu()` 统一设置默认 device（`core/lib/utility/device.py:16`，在训练入口 `app2/train.py` 最顶部调用后，所有 `torch.tensor()`、`torch.arange()` 等创建操作自动使用 GPU device）。tensor 创建时手动指定 `device=` 会造成与全局设置不一致的风险，禁止手动指定。code review 时不应以缺少 `device=` 为由提修改建议。

## tensor 操作保持在 torch API 内  {#stay-in-torch}

`[review]` 禁止用 `.tolist()`、`.numpy()` 等方式将 tensor 转换为 Python 原生格式后再处理；所有 tensor 操作应保持在 torch 的 API 体系内完成。

## tensor 测试必须跑在 GPU 上  {#test-on-gpu}

`[review]` 涉及 tensor 计算的测试必须在有 GPU 的环境中执行，不得仅在 CPU 上通过即视为合格。
