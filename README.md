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

### 2. 设置环境变量

```bash
# Windows (PowerShell)
$env:AI_API_KEY = "sk-your-api-key"
$env:AI_API_BASE_URL = "https://api.openai.com/v1"  # 可选，默认 OpenAI
$env:AI_MODEL = "gpt-4o"                             # 可选，默认 gpt-4o

# Linux / Mac
export AI_API_KEY="sk-your-api-key"
export AI_API_BASE_URL="https://api.openai.com/v1"
export AI_MODEL="gpt-4o"
```

### 3. 运行

```bash
# 审查本地未提交修改（报告保存到 reports/Review_Report_时间戳.md）
python p4_ai_reviewer.py local

# 审查指定 CL
python p4_ai_reviewer.py 12345

# 自定义输出路径 + 详细日志
python p4_ai_reviewer.py 12345 -o reports/my_review.md -v
```

## 环境变量一览

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AI_API_BASE_URL` | `https://api.openai.com/v1` | LLM API 基础地址 |
| `AI_API_KEY` | *(必填)* | LLM API 密钥 |
| `AI_MODEL` | `gpt-4o` | 模型名称 |
| `AI_MAX_TOKENS` | `4096` | 最大生成 token 数 |
| `AI_TEMPERATURE` | `0.2` | 生成温度（越低越确定性） |
| `FILE_CONTENT_MAX_CHARS` | `60000` | 单文件全量内容截断阈值（字符） |
| `REPORT_OUTPUT_DIR` | `reports` | 报告输出目录；不指定 `-o` 时在该目录下生成 `Review_Report_时间戳.md`，不覆盖旧报告 |
| `REPORT_OUTPUT_PATH` | `Review_Report.md` | 仅在使用 `-o` 时的默认文件名参考 |
| `P4_EXECUTABLE` | `p4` | Perforce 命令行工具路径 |
| `SOURCE_ENCODING` | `utf-8` | 代码文件与 P4 输出编码。若代码为 GB2312/GBK（如 Windows 中文环境），设为 `gbk` 可避免 Diff 与报告中中文乱码。 |

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
