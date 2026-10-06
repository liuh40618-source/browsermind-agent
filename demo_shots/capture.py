"""BrowserMind 真机演示截图脚本。
用 Playwright 驱动真实前端：截初始界面 → 跑任务 → 抓执行过程（星图点亮）→ 报告 → 历史 → 浅色主题。
依赖：隔离 venv 的 playwright（python -m venv 后 pip install -r requirements.txt）。
"""
import asyncio, os, base64, json
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(r"D:/Trae/trae work produce/test/技术整合——智能代理/browsermind/demo_shots")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8000"
TASK = "查一下今天 AI 领域有哪些重要新闻，给出 3-5 条摘要，并附上来源链接。"
MAX_WAIT = 360  # 秒

async def shot(page, name):
    p = OUT / name
    await page.screenshot(path=str(p), full_page=False, type="jpeg", quality=82)
    print("shot:", name)
    return p

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900},
                                       device_scale_factor=1)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1.5)
        await shot(page, "01-idle.png")

        # 填任务并运行
        await page.fill("#task-input", TASK)
        await page.click("#run-btn")
        print("task submitted")

        done = False
        t = 0
        i = 0
        last_logs = 0
        while t < MAX_WAIT:
            await asyncio.sleep(5)
            t += 5
            i += 1
            # 星图点亮过程多截几张
            await shot(page, f"02-run-{i:02d}.png")
            # 报告是否出现
            rep_visible = await page.evaluate(
                "() => { const r=document.querySelector('#report'); const dl=document.querySelector('#dl-btn');"
                " return r && dl && getComputedStyle(r).display!=='none' && getComputedStyle(dl).display!=='none'; }")
            # 记录 timeline 节点数，便于判断进度
            logs = await page.evaluate("() => document.querySelectorAll('#timeline .tl-node').length")
            print(f"t={t}s logs={logs} rep_visible={rep_visible}")
            if rep_visible:
                done = True
                await asyncio.sleep(2)
                await shot(page, "03-report.png")
                break
            # 若长时间无新日志，提前结束避免空等
            if logs == last_logs and t > 60:
                # 给一点余量再判断
                if logs == 0:
                    print("no logs after 60s, breaking")
                    break
            last_logs = logs

        if not done:
            await shot(page, "03-report.png")

        # 历史记录视图
        try:
            await page.click("#tab-gallery")
            await asyncio.sleep(2)
            await shot(page, "04-history.png")
        except Exception as e:
            print("gallery err:", e)

        # 浅色主题
        try:
            await page.click("#theme-btn")
            await asyncio.sleep(1.5)
            await shot(page, "05-light.png")
        except Exception as e:
            print("theme err:", e)

        await browser.close()
        print("CAPTURE_DONE", json.dumps({"done": done, "seconds": t, "errors": errors[:5]}))

asyncio.run(main())
