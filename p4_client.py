"""
P4-AI-Reviewer — Perforce 客户端模块
负责通过 p4 命令行获取 Diff 和全量文件内容。
"""
import subprocess
import logging
import os
from typing import Optional

from config import P4_EXECUTABLE, SOURCE_ENCODING

logger = logging.getLogger(__name__)


def _run_p4(args: list[str], timeout: int = 120) -> str:
    """
    执行 p4 命令并返回 stdout 文本。
    使用 SOURCE_ENCODING（如 gbk）解码，避免 Windows 下 Diff 中文乱码。
    如果命令失败则抛出异常。
    """
    cmd = [P4_EXECUTABLE] + args
    logger.debug("执行命令: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            encoding=SOURCE_ENCODING,
            errors="replace",
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"找不到 p4 可执行文件 '{P4_EXECUTABLE}'。"
            "请确保 Perforce 命令行工具已安装并在 PATH 中。"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"p4 命令超时 ({timeout}s): {' '.join(cmd)}")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # p4 diff 在没有差异时也可能返回非零，但 stderr 为空
        if stderr:
            raise RuntimeError(f"p4 命令失败 (rc={result.returncode}): {stderr}")

    return result.stdout


# ----------------------------------------------------------------
# Diff 获取
# ----------------------------------------------------------------

def get_diff_local() -> str:
    """
    获取本地工作区未提交的修改 (p4 diff -du)。
    返回 unified diff 格式的原始文本。
    """
    logger.info("获取本地未提交修改 (p4 diff -du) ...")
    return _run_p4(["diff", "-du"])


def get_diff_cl(cl_number: int | str) -> str:
    """
    获取指定 CL 的变更描述和 diff (p4 describe -du <CL>)。
    返回 unified diff 格式的原始文本。
    """
    logger.info("获取 CL %s 的变更 (p4 describe -du) ...", cl_number)
    return _run_p4(["describe", "-du", str(cl_number)])


# ----------------------------------------------------------------
# 全量文件获取
# ----------------------------------------------------------------

def get_file_content_local(depot_or_local_path: str) -> Optional[str]:
    """
    本地模式：直接从磁盘读取文件内容。
    depot_or_local_path 可以是 depot 路径或本地路径。
    """
    # 如果是 depot 路径，先用 p4 where 转换为本地路径
    local_path = depot_or_local_path
    if local_path.startswith("//"):
        local_path = _depot_to_local(local_path)
        if local_path is None:
            logger.warning("无法将 depot 路径映射到本地: %s", depot_or_local_path)
            return None

    # 使用配置的编码读取（SOURCE_ENCODING=gbk 时兼容 GB2312/GBK 代码文件）
    try:
        with open(local_path, "r", encoding=SOURCE_ENCODING, errors="replace") as f:
            return f.read()
    except (OSError, IOError) as e:
        logger.warning("读取本地文件失败 %s: %s", local_path, e)
        return None


def get_file_content_cl(depot_path: str, cl_number: int | str) -> Optional[str]:
    """
    CL 模式：通过 p4 print 获取特定版本的文件快照。
    """
    file_spec = f"{depot_path}@{cl_number}"
    logger.debug("获取文件快照: p4 print -q %s", file_spec)
    try:
        content = _run_p4(["print", "-q", file_spec])
        return content
    except RuntimeError as e:
        logger.warning("获取文件快照失败 %s: %s", file_spec, e)
        return None


def _depot_to_local(depot_path: str) -> Optional[str]:
    """
    使用 p4 where 将 depot 路径转换为本地路径。
    """
    try:
        output = _run_p4(["where", depot_path])
        # p4 where 输出格式: //depot/path //client/path /local/path
        parts = output.strip().split(" ")
        if len(parts) >= 3:
            # 最后一个部分是本地路径（可能含空格，取最后一段）
            # 实际上 p4 where 对含空格的路径处理较复杂，这里取简单策略
            local_path = parts[-1]
            if os.path.exists(local_path):
                return local_path
        # 备选：尝试取最后一列
        lines = output.strip().splitlines()
        if lines:
            last_line_parts = lines[0].split(" ")
            if len(last_line_parts) >= 3:
                return last_line_parts[-1]
    except RuntimeError:
        pass
    return None


def get_opened_files() -> list[str]:
    """
    获取当前工作区已 open 的文件列表（用于 local 模式补全路径信息）。
    返回 depot 路径列表。
    """
    try:
        output = _run_p4(["opened"])
        files = []
        for line in output.strip().splitlines():
            # 格式: //depot/path/file.cpp#rev - action change CL (type)
            if line.startswith("//"):
                depot_path = line.split("#")[0]
                files.append(depot_path)
        return files
    except RuntimeError:
        return []
