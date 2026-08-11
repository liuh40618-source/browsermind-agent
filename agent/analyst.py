"""
Analyst Agent - 把碎片信息变成结构化报告。

这是独立的"收尾 Agent"，和执行循环解耦：
- 执行层负责"抓得全"（尽量多抓准抓）
- 分析层负责"想得深"（不抓了，专心理解已有数据）

输入：
    - 用户原始任务
    - 所有提取的碎片信息（extracted_info）
    - 访问过的页面列表

输出：
    结构化 Markdown 报告
"""

import json
from typing import Any


ANALYST_PROMPT = """You are the Result Analyzer of BrowserMind, an autonomous AI agent.

Your job is to take all the fragmented information gathered by the agent and produce a well-structured Markdown report.

Rules:
1. Write the report in the SAME LANGUAGE as the user's original task.
2. Structure the report with clear headings (##, ###).
3. Use tables when comparing multiple items.
4. Include specific data (numbers, names, URLs) from the gathered info.
5. Add a brief analysis/insight section at the end.
6. If information is missing or incomplete, note it honestly.
7. Do NOT fabricate information. Only use what was actually gathered.

Report structure (adapt to the task):
```
# {报告标题}

## 概述
（任务背景 + 主要发现）

## 详细信息
（按类别/项目组织，用表格或列表）

## 分析与洞察
（对比、趋势、建议）

## 数据来源
（列出访问的页面）
```

Return ONLY the Markdown report, no meta-commentary."""


class Analyst:
    """分析 Agent：碎片信息 → 结构化报告。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def generate_report(
        self,
        task: str,
        extracted_info: list[dict[str, Any]],
        visited_pages: list[str],
        agent_summary: str = "",
    ) -> str:
        """把所有碎片信息整合成结构化 Markdown 报告。

        参数:
            task: 用户原始任务
            extracted_info: Agent 收集的所有信息
            visited_pages: 访问过的页面 URL
            agent_summary: Agent 自己的 finish 摘要（可选）

        返回:
            Markdown 格式的报告
        """
        # 准备给 LLM 的上下文
        context_parts = [f"## 用户任务\n{task}"]

        if agent_summary:
            context_parts.append(f"## Agent 摘要\n{agent_summary}")

        context_parts.append("## 收集的信息")
        for i, info in enumerate(extracted_info, 1):
            context_parts.append(f"\n### 信息块 {i}")
            context_parts.append(json.dumps(info, ensure_ascii=False, indent=2)[:3000])

        if visited_pages:
            context_parts.append(f"\n## 访问的页面\n" + "\n".join(f"- {u}" for u in visited_pages))

        context = "\n".join(context_parts)

        report = await self._llm.chat(
            messages=[
                {"role": "system", "content": ANALYST_PROMPT},
                {"role": "user", "content": context},
            ],
        )

        # 确保是 Markdown 格式
        if not report.strip().startswith("#"):
            report = f"# 分析报告\n\n{report}"

        return report.strip()
