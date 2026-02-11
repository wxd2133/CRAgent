# P4-AI-Reviewer — Perforce AI 代码审查助手

通过 Perforce 命令行获取代码变更，结合"全量上下文"调用大模型进行代码审查，自动输出 Markdown 报告。

## 功能特性

- **双模式支持**：`local`（本地未提交修改）和 `CL`（指定变更列表）
- **全量上下文**：每个文件同时发送 Diff 和全量文件内容给 AI，提升审查精度
- **智能过滤**：自动识别代码文件（`.cpp`, `.h`, `.cs`, `.py`, `.lua` 等），跳过二进制和美术资源
- **结构化报告**：Markdown 格式，按文件折叠 Diff，以列表展示审查建议（标注行号与严重程度）
- **兼容性强**：支持 OpenAI 兼容接口（Azure OpenAI、DeepSeek、Ollama 等）

## 项目结构

```
D:\CRAgent\
├── p4_ai_reviewer.py     # 主入口（CLI）
├── config.py              # 配置（API 地址、模型、过滤规则等）
├── p4_client.py           # Perforce 命令交互
├── diff_parser.py         # Diff 解析器
├── ai_reviewer.py         # AI 审查（Prompt 构建 + LLM 调用）
├── report_generator.py    # Markdown 报告生成
├── requirements.txt       # Python 依赖
└── README.md              # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初次使用前修改 config.py

在项目根目录打开 `config.py`，按需修改以下配置（**无需每次设置环境变量**）：

| 配置项 | 说明 |
|--------|------|
| `AI_API_KEY` | LLM API 密钥（必填） |
| `AI_API_BASE_URL` | API 地址，如 `https://api.openai.com/v1`、`https://api.deepseek.com/v1` |
| `AI_MODEL` | 模型名，如 `gpt-4o`、`deepseek-chat` |
| `SOURCE_ENCODING` | 代码与 P4 输出编码，默认 `gbk`（中文环境）；UTF-8 代码改为 `utf-8` |
| `REPORT_OUTPUT_DIR` | 报告输出目录，默认 `reports` |

保存后即可长期使用；若需临时覆盖，仍可设置同名环境变量。

### 3. 运行

```bash
# 审查本地未提交修改（报告保存到 reports/Review_Report_时间戳.md）
python p4_ai_reviewer.py local

# 审查指定 CL
python p4_ai_reviewer.py 12345

# 审查多个 CL（空格或逗号分隔）
python p4_ai_reviewer.py 12345 12346
python p4_ai_reviewer.py 12345,12346

# 自定义输出路径 + 详细日志
python p4_ai_reviewer.py 12345 -o reports/my_review.md -v
```

## 配置说明

以上项均在 `config.py` 中修改即可；若设置了同名环境变量，会覆盖 config 中的值。

| 配置项 | 说明 |
|--------|------|
| `AI_API_BASE_URL` | LLM API 基础地址 |
| `AI_API_KEY` | LLM API 密钥（必填） |
| `AI_MODEL` | 模型名称 |
| `AI_MAX_TOKENS` / `AI_TEMPERATURE` | 生成长度与温度（温度建议 0～0.1，利于结果稳定） |
| `AI_SEED` | 随机种子，设为正整数可提升多次运行一致性（留空不传，部分 API 支持） |
| `FILE_CONTENT_MAX_CHARS` | 单文件全量内容截断阈值（字符） |
| `REQUEST_MAX_CHARS` | 单次请求（diff+全量）总字符上限，超则截断或仅发 diff，避免超出模型上下文 |
| `MAX_FILES_PER_RUN` | 单次运行最多审查的代码文件数，0=不限制；超过时只审查前 N 个，其余在报告中列出 |
| `REPORT_OUTPUT_DIR` | 报告输出目录 |
| `P4_EXECUTABLE` | Perforce 可执行路径 |
| `SOURCE_ENCODING` | 代码与 P4 输出编码（默认 `gbk`） |

## 输出示例

生成的 `Review_Report.md` 结构如下：

```markdown
# P4-AI-Reviewer 代码审查报告

- **审查模式**: 变更列表 CL `12345`
- **变更文件总数**: 5
- **代码文件数**: 3

---

### Foo.cpp
**路径**: `//depot/Engine/Src/Foo.cpp`

<details>
<summary>查看 Diff（点击展开）</summary>
... diff 内容 ...
</details>

#### AI 审查意见

- 🔴 **第 42 行**: `new` 分配的内存未使用 `delete` 释放...
- 🟡 **第 78 行**: 缺少对 `nullptr` 的检查...
- 🔵 **第 103 行**: 建议将魔法数字 `1024` 提取为常量...
```

## 工作流程

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  CLI 输入    │────▶│  P4 客户端    │────▶│  Diff 解析器  │
│ local / CL  │     │ diff/describe│     │  结构化对象   │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                    ┌──────────────┐              │
                    │  全量文件获取  │◀─────────────┘
                    │ open/p4 print│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌──────────────┐
                    │  AI 审查模块  │────▶│  报告生成器   │
                    │ Prompt + LLM │     │ Markdown 输出 │
                    └──────────────┘     └──────────────┘
```

## 注意事项

- 运行前请确保 `p4` 命令行工具已安装并已登录（`p4 login`）
- 工作区需要正确配置 Perforce client mapping
- 大型 CL（大量文件）审查耗时较长，请耐心等待
- 全量文件超过 60000 字符会被截断（可通过 `FILE_CONTENT_MAX_CHARS` 调整）
