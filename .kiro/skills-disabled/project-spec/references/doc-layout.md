# 文档结构契约

文档不放在目标仓库里，而放在文档根 `~/data/docs/<仓库目录名>/<提交哈希>/`（下称 `<文档根>`），一个提交一个目录，与仓库完全解耦。本文件中的文档路径相对 `<文档根>`；配置里的 `source`、`tests` 和代码、测试路径相对目标仓库根。

## 模块配置

`<文档根>/project-spec.json` 声明模块与源码、测试目录的对应关系，是三棵树镜像代码的唯一依据：

```json
{
  "schemaVersion": 2,
  "sourceSuffixes": [".py"],
  "journeys": {"tests": "<跨模块 journey 测试目录>", "testFile": "test_{stem}.py"},
  "modules": {
    "<module>": {"source": "<源码目录>", "tests": "<测试目录>", "testFile": "test_{stem}.py"}
  }
}
```

- 模块是一个承担独立职责的代码目录，模块内的类共同完成该职责。模块名用小写 kebab-case，不能是 `journeys`。
- `source`、`tests` 是 `/` 分隔的仓库相对路径；`testFile` 是测试文件名模板，`{stem}` 替换为文档文件名去掉 `.md`。
- `sourceSuffixes` 按优先级列出源文件后缀。
- `journeys` 只在存在跨模块 journey 时需要。
- 配置之外的代码目录不受本 Skill 管理。

## 三棵树

```text
requirements/
├── <feature>.md                    项目级功能点或约束
└── <module>/<feature>.md           模块功能点
architecture/
└── <module>/
    ├── README.md                   kind: module，对应 <source>/
    ├── <subdir>/README.md          kind: package，可选
    ├── <path>/<stem>.md            kind: source，对应 <source>/<path>/<stem><suffix>
    └── <path>/<stem>.structure.md  kind: structure，与同路径的 source 文档配对
test-cases/
├── journeys/<name>.md              跨模块 journey，对应 <journeys.tests>/<testFile>
└── <module>/
    ├── <path>/<stem>.md            kind: cases，对应 <tests>/<path>/<testFile>
    └── <dir>/journeys/<name>.md    模块内 journey，对应 <tests>/<dir>/journeys/<testFile>
```

- 需求只有项目级和模块级两层，文件名用小写 kebab-case，一个文件一个功能点或约束。
- 架构树只为公开源文件建文档，文件名保持源文件名去掉后缀。
- 每个模块必须有 `architecture/<module>/README.md`。
- 每个 source 文档必须有同路径的 structure 文档；structure 文档必须有同路径的 source 文档。
- 含公开接口的 structure 文档必须有同路径的 cases 文档。
- journey 放在其全部 targets 所在目录的最近公共目录下的 `journeys/`；公共目录为空时放在 `test-cases/journeys/`。
- `README.md` 只出现在架构树中。

## Frontmatter

每个文档从第一行开始写 frontmatter，只用单行 `key: value`，列表写成单行 JSON 字符串数组，键不重复。

必需字段：`id`、`kind`、`status`（`draft`、`approved`、`implemented`，含义见 SKILL.md）。

| kind | 位置 | id 前缀 | 关系字段 |
|------|------|---------|----------|
| `requirement` / `constraint` | requirements | `req.` | 无 |
| `module` / `package` / `source` | architecture | `arch.` | `requirements`、`depends-on` |
| `structure` | architecture | `struct.` | 无 |
| `cases` | test-cases | `cases.` | `verifies` |
| `journey` | test-cases 的 `journeys/` | `journey.` | `targets`、`verifies` |

表外字段即校验错误。代码与测试位置由路径推出，不写进文档。

## ID 与接口小节

- ID 匹配 `^[a-z][a-z0-9]*(\.[a-z0-9][a-z0-9_-]*)+$`，在三棵树中全局唯一，移动文件不更换。
- 公开接口写成 structure 文档里的二级或三级标题：`## <符号或签名> {#api.<...>}`。标题中括号前最后一个标识符是代码里的符号名；其他 kind 的文档只有 cases 可以声明小节 ID。
- cases 文档为每个接口写同名小节，锚点把 `api.` 换成 `cases.`；不能有架构中不存在的接口小节。
- 代码块内的标题不参与解析。

## 关系规则

- 架构文档的 `requirements` 只引用本模块或项目级需求；`depends-on` 只引用其他架构文档。
- cases 文档的 `verifies` 只引用镜像架构文档 `requirements` 中的需求。
- journey 的 `targets` 引用接口 ID 或架构文档 ID；`verifies` 引用所在模块或项目级需求。
- implemented 需求必须被至少一个架构文档和一个用例引用。

## 正文

四类文档各有固定格式，骨架与来源见 `templates.md`：需求是 EARS 句式的原子条目；structure 文档是类与函数的结构清单，由脚本从代码生成；source 文档陈述职责、含候选方案的决策和不变量与错误约束；用例是声明式的 Given、When、Then 场景。用肯定式描述已决定的目标，未决问题写在 `## 待确认`。

## 一致性判定

校验器只对 implemented 文档检查代码，结果写入 `inconsistencies`：

- 文件：推出的源码或测试文件不存在。
- 符号：接口小节的符号名不在对应源文件中。
- 依赖：approved 或 implemented 文档所依赖的需求是 draft。
- 结构：implemented 的 structure 文档与 `scripts/gen_structure.py` 对源码生成的结构清单不同，说明文字不参与比对。

行为是否一致不能机械判定，以对应测试通过为准，由 `maintain` 核对。approved 文档没有代码只表示待开发，不算不一致。
