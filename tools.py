
# ==================== 工具函数 ====================
def read_file(file_path: str) -> str:
    """
    读取文件内容，注意需要传入文件的绝对路径
    Args:
        file_path: 文件的绝对路径

    Returns: 文件内容
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def write_to_file(file_path: str, content: str) -> str:
    """
    将内容写入文件，注意需要传入文件的绝对路径
    Args:
        file_path: 文件的绝对路径
        content: 写入文件的内容

    Returns: 文件写入是否成功
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return "写入成功"


def run_terminal_command(command: str) -> str:
    """执行终端命令"""
    import subprocess
    run_result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return run_result.stdout


def web_search(query: str) -> str:
    """搜索网络信息（模拟）"""
    # 实际使用时，可替换为真实的搜索 API（如 Tavily、博查等）
    return f"模拟搜索结果：关于“{query}”，未找到真实数据。"

