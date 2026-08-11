"""
BrowserMind Tools - 工具名常量集中定义

所有工具名在此处维护一次，agent_loop / llm 等模块统一引用。
"""

# 浏览器控制类工具
BROWSER_TOOLS = {"open_page", "open", "click", "type", "scroll", "screenshot", "get_text"}

# 搜索类工具
SEARCH_TOOLS = {"search"}

# 所有可用工具（不含 finish）
ALL_TOOLS = BROWSER_TOOLS | SEARCH_TOOLS
