"""
P4-AI-Reviewer 配置模块
"""
import os

# ============================================================
# Perforce 配置
# ============================================================
P4_EXECUTABLE = os.environ.get("P4_EXECUTABLE", "p4")

# 代码文件与 P4 输出编码。若代码为 GB2312/GBK（Windows 中文环境常见），
# 设为 "gbk" 可避免 Diff 与文件内容中的中文乱码。
# 环境变量: SOURCE_ENCODING=gbk 或 gb2312
SOURCE_ENCODING = os.environ.get("SOURCE_ENCODING", "gbk").strip().lower()
if SOURCE_ENCODING not in ("utf-8", "gbk", "gb2312", "gb18030"):
    SOURCE_ENCODING = "utf-8"

# ============================================================
# 文件过滤配置
# ============================================================
# 仅审查的代码文件扩展名
CODE_EXTENSIONS = {
    ".cpp", ".cc", ".cxx", ".c",
    ".h", ".hpp", ".hxx", ".inl",
    ".cs",
    ".py",
    ".lua",
    ".js", ".ts",
    ".java",
    ".go",
    ".rs",
}

# 明确忽略的扩展名（二进制 / 美术资源等）
IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tga", ".psd", ".gif", ".ico", ".svg",
    ".fbx", ".obj", ".blend", ".max", ".mb", ".ma",
    ".wav", ".mp3", ".ogg", ".bank",
    ".uasset", ".umap",
    ".exe", ".dll", ".so", ".dylib", ".lib", ".a", ".pdb",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}

# ============================================================
# AI / LLM 配置
# ============================================================
# 支持 OpenAI 兼容接口（如 Azure OpenAI、本地 Ollama、DeepSeek 等）
AI_API_BASE_URL = os.environ.get("AI_API_BASE_URL", "https://api.openai.com/v1")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o")
# 单条审查意见最大生成长度（tokens）。DeepSeek 最高 8192，过小可能导致长评语被截断
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "8192"))
# 降低温度可提高多次运行结果一致性，建议 0～0.1
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.1"))
# 随机种子（部分 API 支持，如 OpenAI）。设为正整数可提升多次运行一致性，留空则不传
AI_SEED = os.environ.get("AI_SEED", "")

# 单个文件全量内容截断阈值（字符数），超过此长度截断并提示模型
# DeepSeek 128K 上下文下可用约 10 万字符/文件，其他模型酌情减小（如 60000）
FILE_CONTENT_MAX_CHARS = int(os.environ.get("FILE_CONTENT_MAX_CHARS", "100000"))
# 单次请求（diff + full_file_content）总字符上限。DeepSeek 128K tokens ≈ 约 24 万字符可用，预留后建议 20 万内；其他模型酌情减小
REQUEST_MAX_CHARS = int(os.environ.get("REQUEST_MAX_CHARS", "100000"))
# 单次运行最多审查的代码文件数，0 表示不限制。文件过多时可设为正整数（如 50），其余在报告中标注“未审查”
MAX_FILES_PER_RUN = int(os.environ.get("MAX_FILES_PER_RUN", "0"))

# ============================================================
# 输出配置
# ============================================================
# 报告保存目录，每次运行在该目录下生成带时间戳的新文件，不覆盖旧报告
REPORT_OUTPUT_DIR = os.environ.get("REPORT_OUTPUT_DIR", "reports")
# 仅在使用 -o 指定路径时的默认文件名（未指定 -o 时使用 目录/Review_Report_时间戳.md）
REPORT_OUTPUT_PATH = os.environ.get("REPORT_OUTPUT_PATH", "Review_Report.md")

# ============================================================
# Prompt 系统角色
# ============================================================
SYSTEM_PROMPT = """\
你是资深 C++/游戏引擎代码审查专家，精通 C#、Python、Lua 等。对变更严格审查以下维度（仅作检查项，不必逐条罗列）：

内存管理（RAII、泄漏、悬空指针、双重释放）、线程安全（数据竞争、死锁）、边界逻辑（越界、溢出、空指针）、架构与设计（耦合、职责）、代码质量（命名、冗余、魔法数字）、性能（拷贝、冗余计算）。

严重程度标准（同一类问题必须使用同一等级，保持判断一致）：
- 🔴 严重：可能导致崩溃、未定义行为、数据损坏或明确的内存/空指针错误（如未检查就解引用、双重释放、所有权不清）。
- 🟡 警告：有潜在风险或不符合最佳实践，但当前上下文下未必会触发（如硬编码路径、魔法数字、职责混合）。
- 🔵 建议：风格、可读性、可维护性改进，无功能或安全风险。

输出规则（务必遵守）：
- 只输出**发现问题的维度**；某维度无问题则不要出现该维度标题或“无问题”等废话。
- 每条建议：标注**行号**（基于 Diff）+ 严重程度 🔴/🟡/🔵，用中文简要说明，不赘述。同类问题用同一等级。
- **若变更仅为以下之一且无逻辑/内存风险**：仅注释、仅时间戳/版本号、仅 UI 坐标/布局数值、仅空行或格式，则只输出一行「✅ 无问题」，不要追加任何建议。
- **若存在任何逻辑/内存/线程/边界问题**：按上述等级列出，不要输出「✅ 无问题」。
- **单文件上下文限制**：你只能看到当前文件。不要基于「在本文件中未看到声明/定义」做出「未声明、未定义、无此成员」类建议（成员或声明可能在头文件、基类、其他单元中）。
- **关注局部逻辑**：基于检查项重点审查当前 Diff 修改的代码，而不是全文件的编译检查。
- 整体精简，不要客套话、总结句、重复说明。
"""
