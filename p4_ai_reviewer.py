#!/usr/bin/env python3
"""
P4-AI-Reviewer — 主入口
Perforce AI 代码审查助手

用法:
    python p4_ai_reviewer.py local              # 审查本地未提交修改
    python p4_ai_reviewer.py 12345              # 审查指定 CL
    python p4_ai_reviewer.py local -o report.md # 自定义输出路径
"""
import argparse
import logging
import sys
import os
from datetime import datetime

# 确保模块可以被找到
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import REPORT_OUTPUT_PATH, REPORT_OUTPUT_DIR
from p4_client import (
    get_diff_local,
    get_diff_cl,
    get_file_content_local,
    get_file_content_cl,
)
from diff_parser import parse_local_diff, parse_cl_describe, FileDiff
from ai_reviewer import review_files_batch
from report_generator import generate_report


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_local_mode(output_path: str):
    """
    本地模式：审查工作区中未提交的修改。
    """
    logger = logging.getLogger("main")

    # 1. 获取 diff
    logger.info("=" * 60)
    logger.info("P4-AI-Reviewer — 本地模式")
    logger.info("=" * 60)

    raw_diff = get_diff_local()
    if not raw_diff.strip():
        logger.warning("没有检测到本地未提交的修改。")
        print("\n✅ 没有检测到本地未提交的修改，无需审查。")
        return

    # 2. 解析 diff
    file_diffs = parse_local_diff(raw_diff)
    if not file_diffs:
        logger.warning("Diff 解析结果为空。")
        print("\n✅ Diff 解析结果为空，无需审查。")
        return

    code_diffs = [f for f in file_diffs if f.is_code_file]
    logger.info("共 %d 个变更文件, %d 个代码文件需要审查",
                len(file_diffs), len(code_diffs))

    if not code_diffs:
        logger.info("没有需要审查的代码文件。")
        # 仍然生成报告（记录跳过的文件）
        generate_report("local", None, file_diffs, [], output_path)
        print(f"\n📄 报告已生成: {output_path}")
        return

    # 3. 获取全量文件内容并组装数据
    file_data: list[tuple[str, str, str | None]] = []
    for fd in code_diffs:
        full_content = None
        # 优先使用 local_path，否则尝试 depot_path
        if fd.local_path:
            full_content = get_file_content_local(fd.local_path)
        elif fd.depot_path:
            full_content = get_file_content_local(fd.depot_path)
        file_data.append((fd.depot_path, fd.diff_text, full_content))

    # 4. 调用 AI 审查
    logger.info("开始 AI 审查 (%d 个文件) ...", len(file_data))
    results = review_files_batch(file_data)

    # 5. 生成报告
    report = generate_report("local", None, file_diffs, results, output_path)

    # 打印摘要
    success_count = sum(1 for r in results if not r.error)
    fail_count = sum(1 for r in results if r.error)
    print(f"\n{'=' * 60}")
    print(f"  P4-AI-Reviewer 审查完成")
    print(f"  审查文件: {len(code_diffs)} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  报告路径: {os.path.abspath(output_path)}")
    print(f"{'=' * 60}")


def run_cl_mode(cl_numbers: list[str], output_path: str):
    """
    CL 模式：审查指定变更列表（支持多个 CL）。
    """
    logger = logging.getLogger("main")
    cl_display = ", ".join(cl_numbers)

    logger.info("=" * 60)
    logger.info("P4-AI-Reviewer — CL 模式 (CL: %s)", cl_display)
    logger.info("=" * 60)

    # 1. 逐个 CL 获取 describe 输出并解析
    all_file_diffs: list[FileDiff] = []
    for cl_num in cl_numbers:
        raw_describe = get_diff_cl(cl_num)
        if not raw_describe.strip():
            logger.warning("CL %s 的 describe 输出为空，跳过。", cl_num)
            continue
        file_diffs = parse_cl_describe(raw_describe)
        for fd in file_diffs:
            fd.cl_number = cl_num
            all_file_diffs.append(fd)

    if not all_file_diffs:
        logger.warning("未解析到任何文件变更。")
        print(f"\n⚠️ CL {cl_display} 未解析到文件变更，请确认 CL 编号正确。")
        return

    file_diffs = all_file_diffs
    code_diffs = [f for f in file_diffs if f.is_code_file]
    logger.info("共 %d 个变更文件, %d 个代码文件需要审查",
                len(file_diffs), len(code_diffs))

    if not code_diffs:
        logger.info("没有需要审查的代码文件。")
        generate_report("cl", cl_display, file_diffs, [], output_path)
        print(f"\n📄 报告已生成: {output_path}")
        return

    # 2. 获取全量文件内容
    file_data: list[tuple[str, str, str | None]] = []
    for fd in code_diffs:
        full_content = None
        if fd.action != "delete":
            full_content = get_file_content_cl(fd.depot_path, fd.cl_number)
        file_data.append((fd.depot_path, fd.diff_text, full_content))

    # 3. 调用 AI 审查
    logger.info("开始 AI 审查 (%d 个文件) ...", len(file_data))
    results = review_files_batch(file_data)

    # 4. 生成报告
    generate_report("cl", cl_display, file_diffs, results, output_path)

    # 打印摘要
    success_count = sum(1 for r in results if not r.error)
    fail_count = sum(1 for r in results if r.error)
    print(f"\n{'=' * 60}")
    print(f"  P4-AI-Reviewer 审查完成 (CL: {cl_display})")
    print(f"  审查文件: {len(code_diffs)} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  报告路径: {os.path.abspath(output_path)}")
    print(f"{'=' * 60}")


def main():
    # Windows 控制台默认 GBK，避免打印中文/emoji 时 UnicodeEncodeError
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="P4-AI-Reviewer: Perforce AI 代码审查助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\

环境变量:
  AI_API_BASE_URL    LLM API 地址 (默认: https://api.openai.com/v1)
  AI_API_KEY         LLM API 密钥
  AI_MODEL           模型名称 (默认: gpt-4o)
  AI_MAX_TOKENS      最大生成 token 数 (默认: 4096)
  AI_TEMPERATURE     生成温度 (默认: 0.2)
        """,
    )

    parser.add_argument(
        "target",
        nargs="+",
        help="审查目标: 'local' 表示本地未提交修改; 或一个或多个 CL 编号 (如 12345 12346 或 12345,12346)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help=f"输出报告路径。不指定时在 {REPORT_OUTPUT_DIR}/ 下生成 Review_Report_时间戳.md，不覆盖旧报告",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="启用详细日志输出",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # 检查 API Key
    from config import AI_API_KEY, AI_API_BASE_URL, AI_MODEL
    if not AI_API_KEY:
        print("⚠️  未设置 AI_API_KEY 环境变量。请设置后再运行。")
        print("   例如: set AI_API_KEY=sk-xxxx  (Windows)")
        print("   或:   export AI_API_KEY=sk-xxxx  (Linux/Mac)")
        sys.exit(1)

    logger = logging.getLogger("main")
    logger.info("AI 配置: API=%s, Model=%s", AI_API_BASE_URL, AI_MODEL)

    # 未指定 -o 时：在报告目录下生成带时间戳的新文件，不覆盖旧报告
    output_path = args.output
    if output_path is None:
        os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(REPORT_OUTPUT_DIR, f"Review_Report_{timestamp}.md")
        logger.info("报告将保存至: %s", output_path)
    else:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    # 解析 target：支持 local 或 12345 12346 或 12345,12346
    targets = args.target
    if len(targets) == 1 and targets[0].strip().lower() == "local":
        run_local_mode(output_path)
    else:
        cl_numbers: list[str] = []
        for t in targets:
            for part in t.replace(",", " ").split():
                part = part.strip()
                if part.isdigit():
                    cl_numbers.append(part)
        if cl_numbers:
            run_cl_mode(cl_numbers, output_path)
        else:
            print(f"⚠️  无效的目标参数: {targets}")
            print("   请使用 'local' 或 CL 编号 (如 12345 或 12345 12346 或 12345,12346)。")
            sys.exit(1)


if __name__ == "__main__":
    main()
