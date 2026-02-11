"""
P4-AI-Reviewer — 报告生成器
将审查结果汇总为 Markdown 报告。
"""
import logging
from datetime import datetime

from diff_parser import FileDiff
from ai_reviewer import ReviewResult

logger = logging.getLogger(__name__)


def generate_report(
    mode: str,
    cl_number: str | None,
    file_diffs: list[FileDiff],
    review_results: list[ReviewResult],
    output_path: str,
) -> str:
    """
    生成 Markdown 格式的审查报告。

    参数:
        mode: "local" 或 "cl"
        cl_number: CL 编号（CL 模式下有值）
        file_diffs: 解析后的文件 diff 列表
        review_results: AI 审查结果列表
        output_path: 报告输出路径

    返回:
        生成的报告内容字符串
    """
    # 构建 depot_path -> ReviewResult 映射
    result_map: dict[str, ReviewResult] = {r.depot_path: r for r in review_results}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    # ── 报告头 ─────────────────────────────────────
    lines.append("# P4-AI-Reviewer 代码审查报告")
    lines.append("")
    lines.append(f"- **生成时间**: {now}")
    if mode == "local":
        lines.append("- **审查模式**: 本地未提交修改 (`local`)")
    else:
        lines.append(f"- **审查模式**: 变更列表 CL `{cl_number}`")

    # 统计
    total_files = len(file_diffs)
    code_files = [f for f in file_diffs if f.is_code_file]
    skipped_files = [f for f in file_diffs if not f.is_code_file]
    reviewed = [r for r in review_results if not r.error]
    failed = [r for r in review_results if r.error]

    lines.append(f"- **变更文件总数**: {total_files}")
    lines.append(f"- **代码文件数**: {len(code_files)}")
    lines.append(f"- **跳过（非代码文件）**: {len(skipped_files)}")
    lines.append(f"- **审查成功**: {len(reviewed)}")
    if failed:
        lines.append(f"- **审查失败**: {len(failed)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 跳过的文件 ──────────────────────────────────
    if skipped_files:
        lines.append("## 跳过的文件（非代码文件）")
        lines.append("")
        for f in skipped_files:
            lines.append(f"- `{f.depot_path}`")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── 逐文件审查结果 ──────────────────────────────
    lines.append("## 审查结果")
    lines.append("")

    if not code_files:
        lines.append("> 没有需要审查的代码文件。")
        lines.append("")
    else:
        for f in code_files:
            result = result_map.get(f.depot_path)
            filename = f.depot_path.rsplit("/", 1)[-1] if "/" in f.depot_path else f.depot_path

            lines.append(f"### {filename}")
            lines.append(f"**路径**: `{f.depot_path}`  ")
            lines.append(f"**操作**: {f.action}")
            lines.append("")

            # Diff 折叠显示
            if f.diff_text:
                lines.append("<details>")
                lines.append(f"<summary>查看 Diff（点击展开）</summary>")
                lines.append("")
                lines.append("```diff")
                lines.append(f.diff_text)
                lines.append("```")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            # AI 审查意见
            if result and not result.error:
                lines.append("#### AI 审查意见")
                lines.append("")
                lines.append(result.review_comment)
                lines.append("")
            elif result and result.error:
                lines.append("#### AI 审查意见")
                lines.append("")
                lines.append(f"> ⚠️ 审查失败: {result.error}")
                lines.append("")
            else:
                lines.append("> 未获取到审查结果。")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ── 报告尾 ─────────────────────────────────────
    lines.append("---")
    lines.append(f"*报告由 P4-AI-Reviewer 自动生成 | {now}*")
    lines.append("")

    report_text = "\n".join(lines)

    # 写入文件
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("审查报告已保存至: %s", output_path)
    except IOError as e:
        logger.error("写入报告失败: %s", e)

    return report_text
