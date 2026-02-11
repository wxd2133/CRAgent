"""
P4-AI-Reviewer — AI 审查模块
构建 Prompt 并调用 LLM 进行代码审查。
"""
import logging
import time
from dataclasses import dataclass

import httpx

from config import (
    AI_API_BASE_URL,
    AI_API_KEY,
    AI_MODEL,
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    FILE_CONTENT_MAX_CHARS,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """单个文件的审查结果"""
    depot_path: str
    review_comment: str   # AI 返回的 Markdown 格式审查意见
    error: str = ""       # 如果调用失败，记录错误信息


def _build_user_prompt(depot_path: str, diff_text: str, full_content: str | None) -> str:
    """
    构建单个文件的 User Prompt。
    使用 XML 标签封装 Diff 和全量文件内容，提供"全量上下文"。
    """
    # 截断超大文件
    truncated_notice = ""
    if full_content and len(full_content) > FILE_CONTENT_MAX_CHARS:
        full_content = full_content[:FILE_CONTENT_MAX_CHARS]
        truncated_notice = "\n<!-- 注意: 文件内容过长，已截断至前 {0} 字符 -->".format(
            FILE_CONTENT_MAX_CHARS
        )

    parts = [
        f"请审查以下文件的代码变更。\n",
        f"**文件路径**: `{depot_path}`\n",
    ]

    # Diff 部分
    parts.append("<diff>")
    parts.append(diff_text if diff_text else "(无差异内容)")
    parts.append("</diff>\n")

    # 全量文件部分
    if full_content is not None:
        parts.append("<full_file_content>")
        parts.append(full_content)
        if truncated_notice:
            parts.append(truncated_notice)
        parts.append("</full_file_content>\n")
    else:
        parts.append("<full_file_content>\n(无法获取全量文件内容，请仅基于 Diff 进行审查)\n</full_file_content>\n")

    parts.append("请给出你的审查意见：")

    return "\n".join(parts)


def review_file(
    depot_path: str,
    diff_text: str,
    full_content: str | None,
) -> ReviewResult:
    """
    对单个文件发起 AI 审查请求。
    使用 OpenAI 兼容的 Chat Completions API。
    """
    user_prompt = _build_user_prompt(depot_path, diff_text, full_content)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "max_tokens": AI_MAX_TOKENS,
        "temperature": AI_TEMPERATURE,
    }

    url = f"{AI_API_BASE_URL.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    logger.info("正在审查文件: %s (prompt 长度: %d 字符)", depot_path, len(user_prompt))
    start_time = time.time()

    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        elapsed = time.time() - start_time
        logger.info("文件 %s 审查完成, 耗时 %.1fs", depot_path, elapsed)

        # 提取回复内容
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return ReviewResult(depot_path=depot_path, review_comment=content)
        else:
            return ReviewResult(
                depot_path=depot_path,
                review_comment="",
                error="API 返回了空的 choices",
            )

    except httpx.HTTPStatusError as e:
        error_body = ""
        try:
            error_body = e.response.text[:500]
        except Exception:
            pass
        error_msg = f"HTTP {e.response.status_code}: {error_body}"
        logger.error("审查文件 %s 失败: %s", depot_path, error_msg)
        return ReviewResult(depot_path=depot_path, review_comment="", error=error_msg)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error("审查文件 %s 失败: %s", depot_path, error_msg)
        return ReviewResult(depot_path=depot_path, review_comment="", error=error_msg)


def review_files_batch(
    file_data: list[tuple[str, str, str | None]],
) -> list[ReviewResult]:
    """
    批量审查多个文件。
    file_data: [(depot_path, diff_text, full_content), ...]
    按顺序逐个调用（避免并发请求过多触发 rate limit）。
    """
    results: list[ReviewResult] = []
    total = len(file_data)

    for idx, (depot_path, diff_text, full_content) in enumerate(file_data, 1):
        logger.info("[%d/%d] 开始审查: %s", idx, total, depot_path)
        result = review_file(depot_path, diff_text, full_content)
        results.append(result)

    return results
