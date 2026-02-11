"""
P4-AI-Reviewer — Diff 解析器
将 Perforce 输出的原始 unified diff 文本解析为结构化对象。
"""
import re
import os
import logging
from dataclasses import dataclass, field

from config import CODE_EXTENSIONS, IGNORE_EXTENSIONS

logger = logging.getLogger(__name__)


@dataclass
class FileDiff:
    """单个文件的 Diff 信息"""
    depot_path: str          # depot 路径，例如 //depot/Engine/Src/Foo.cpp
    local_path: str          # 本地路径（如果可获取）
    action: str              # add / edit / delete / 未知
    diff_text: str           # 原始 unified diff 文本片段
    is_code_file: bool       # 是否为需要审查的代码文件
    cl_number: str = ""      # 所属 CL 编号（CL 模式下有值，用于多 CL 时区分同文件）


def _is_code_file(filepath: str) -> bool:
    """判断文件是否属于需要审查的代码文件"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in IGNORE_EXTENSIONS:
        return False
    if ext in CODE_EXTENSIONS:
        return True
    return False


# ============================================================
# local 模式解析 (p4 diff -du)
# ============================================================

def parse_local_diff(raw: str) -> list[FileDiff]:
    """
    解析 `p4 diff -du` 的输出。
    典型格式:
        ==== //depot/path/file.cpp#3 - /local/path/file.cpp ====
        --- //depot/path/file.cpp	2024-01-01 ...
        +++ /local/path/file.cpp	2024-01-01 ...
        @@ -10,6 +10,8 @@
         context line
        -removed line
        +added line
    """
    results: list[FileDiff] = []

    # 按 "====" 分隔块拆分
    # p4 diff -du 的文件头形如:
    #   ==== //depot/path/file.cpp#3 - <local_path> ====
    file_blocks = re.split(r'^(==== .+? ====)\s*$', raw, flags=re.MULTILINE)

    i = 0
    while i < len(file_blocks):
        block = file_blocks[i].strip()
        if block.startswith("===="):
            # 解析头部
            header = block
            diff_body = file_blocks[i + 1] if i + 1 < len(file_blocks) else ""
            i += 2

            depot_path, local_path = _parse_local_diff_header(header)
            if depot_path:
                results.append(FileDiff(
                    depot_path=depot_path,
                    local_path=local_path,
                    action="edit",
                    diff_text=diff_body.strip(),
                    is_code_file=_is_code_file(depot_path),
                ))
        else:
            i += 1

    logger.info("local 模式解析完成: 共 %d 个文件, 其中 %d 个代码文件",
                len(results), sum(1 for f in results if f.is_code_file))
    return results


def _parse_local_diff_header(header: str) -> tuple[str, str]:
    r"""
    从 ==== ... ==== 行中提取 depot_path 和 local_path。
    示例: ==== //depot/Engine/Foo.cpp#3 - D:\workspace\Engine\Foo.cpp ====
    """
    # 移除首尾 ====
    content = header.strip("= ").strip()
    # 尝试匹配 depot_path#rev - local_path
    m = re.match(r'(//[^\s#]+)(?:#\d+)?\s*-\s*(.+)', content)
    if m:
        return m.group(1), m.group(2).strip()
    # 退化：只拿第一个 // 路径
    m2 = re.match(r'(//[^\s#]+)', content)
    if m2:
        return m2.group(1), ""
    return "", ""


# ============================================================
# CL 模式解析 (p4 describe -du <CL>)
# ============================================================

def parse_cl_describe(raw: str) -> list[FileDiff]:
    """
    解析 `p4 describe -du <CL>` 的输出。
    典型格式:
        Change 12345 by user@ws on 2024/01/01 12:00:00
            描述文字...
        Affected files ...
        ... //depot/path/file.cpp#3 edit
        ... //depot/path/file2.h#1 add

        Differences ...
        ==== //depot/path/file.cpp#3 (text) ====
        --- a/depot/path/file.cpp
        +++ b/depot/path/file.cpp
        @@ ...
    """
    results: list[FileDiff] = []

    # 1) 提取 affected files 中的 action 信息
    action_map: dict[str, str] = {}
    affected_section = re.search(
        r'Affected files \.\.\.\s*\n(.*?)(?:\nDifferences \.\.\.|\Z)',
        raw, re.DOTALL
    )
    if affected_section:
        for line in affected_section.group(1).splitlines():
            line = line.strip()
            # 格式: ... //depot/path/file.cpp#3 edit
            m = re.match(r'\.\.\.\s*(//[^\s#]+)(?:#\d+)?\s+(\w+)', line)
            if m:
                action_map[m.group(1)] = m.group(2)

    # 2) 按 ==== 分隔 diff 块
    diff_section_match = re.search(r'Differences \.\.\.\s*\n(.*)', raw, re.DOTALL)
    if not diff_section_match:
        logger.warning("p4 describe 输出中未找到 Differences 段")
        return results

    diff_section = diff_section_match.group(1)
    file_blocks = re.split(r'^(==== .+? ====)\s*$', diff_section, flags=re.MULTILINE)

    i = 0
    while i < len(file_blocks):
        block = file_blocks[i].strip()
        if block.startswith("===="):
            header = block
            diff_body = file_blocks[i + 1] if i + 1 < len(file_blocks) else ""
            i += 2

            depot_path = _parse_cl_diff_header(header)
            if depot_path:
                action = action_map.get(depot_path, "edit")
                results.append(FileDiff(
                    depot_path=depot_path,
                    local_path="",
                    action=action,
                    diff_text=diff_body.strip(),
                    is_code_file=_is_code_file(depot_path),
                ))
        else:
            i += 1

    logger.info("CL 模式解析完成: 共 %d 个文件, 其中 %d 个代码文件",
                len(results), sum(1 for f in results if f.is_code_file))
    return results


def _parse_cl_diff_header(header: str) -> str:
    """
    从 ==== //depot/path/file.cpp#3 (text) ==== 中提取 depot_path。
    """
    content = header.strip("= ").strip()
    m = re.match(r'(//[^\s#]+)', content)
    return m.group(1) if m else ""
