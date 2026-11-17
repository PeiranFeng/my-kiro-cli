# 接口：archive

把 comments 与 review 的结果记录到 `~/data/pr/<repo>/<number>.md`。本接口只负责汇集与写入，不另做分析。

## 步骤

### 1. 确定目标

按 `SKILL.md` 的"确定目标 PR"。批量归档时，对列表中的每个 PR 逐个处理。

### 2. 覆盖确认

检查待处理编号在 `~/data/pr/<repo>/` 下是否已有 `.md`：

```bash
ls ~/data/pr/<repo>/<number>.md 2>/dev/null
```

已存在时，向用户确认覆盖策略（覆盖即删除重写，或跳过即仅处理不存在的编号）后固定下来。删除已有文件有副作用，须先确认再执行。覆盖策略下先 `rm` 再写入；跳过策略下已存在的直接略过。

### 3. 汇集结果

- 使用当前会话中已有的 comments 与 review 的输出。
- 缺哪个接口的结果，先按对应接口执行得到结果，再写入。
- 用户明确只归档某一部分时，只写该部分，其余各节写"本次未执行"。

### 4. 写入

写作规则：正文用中文，专有名词后括注英文原文；代码块保持原文不翻译；图片替换为 `【此处有一张图片，无法解析】`；其他无法解析的内容注明 `【此处有附件/媒体内容，无法解析】`。格式：

```markdown
# PR #<number>：<翻译后的标题>

- **编号（Number）**：#<number>
- **网址（URL）**：<url>
- **状态（State）**：开放中（open）/ 已合并（merged）/ 已关闭（closed）
- **作者（Author）**：<author>
- **源分支（Head Branch）**：<headRefName>
- **目标分支（Base Branch）**：<baseRefName>
- **创建时间（Created At）**：<createdAt>
- **合并时间（Merged At）**：<mergedAt>（未合并则省略）
- **关闭时间（Closed At）**：<closedAt>（未关闭则省略）
- **标签（Labels）**：<labels>（无则省略）
- **指派人（Assignees）**：<assignees>（无则省略）

---

## 变更摘要（Change Summary）

<review 接口的变更摘要>

---

## 独立代码审查

<review 接口的逐条审查结论>

---

## GitHub 审查意见与评估

<comments 接口的逐条评估，每条含来源标签、原文关键段落、评估、理由、处理状态，以及总体结论>
```

### 5. 汇报

```
已归档 PR：
  <repo>: #<n1>, #<n2>（共 <count> 条）
文件位置：~/data/pr/
```
