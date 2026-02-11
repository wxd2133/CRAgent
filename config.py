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
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "4096"))
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))

# 单个文件全量内容截断阈值（字符数），超过此长度截断并提示模型
FILE_CONTENT_MAX_CHARS = int(os.environ.get("FILE_CONTENT_MAX_CHARS", "60000"))

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

输出规则（务必遵守）：
- 只输出**发现问题的维度**；某维度无问题则不要出现该维度标题或“无问题”等废话。
- 每条建议：标注**行号**（基于 Diff）+ 严重程度 🔴/🟡/🔵，用中文简要说明，不赘述。
- **若全部无问题**：只输出一行「✅ 无问题」，不要任何其他句子。
- 整体精简，不要客套话、总结句、重复说明。
"""
