"""生成 BrowserMind 全方位演示页（自包含单文件 HTML）。
读取 demo_shots/ 下的实机截图，挑关键帧 → JPEG 压缩 → base64 内嵌，
叠加架构图 / 执行回路 SVG 与三场景讲解，输出 demo.html。
"""
import base64, glob, io, os
from pathlib import Path

SHOTS = Path(r"D:/Trae/trae work produce/test/技术整合——智能代理/browsermind/demo_shots")
OUT = Path(r"D:/Trae/trae work produce/test/技术整合——智能代理/browsermind/demo.html")

def b64(path: Path, max_w=1280, q=82):
    from PIL import Image
    im = Image.open(path)
    if im.width > max_w:
        h = int(im.height * max_w / im.width)
        im = im.resize((max_w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=q)
    return base64.b64encode(buf.getvalue()).decode()

def load(name):
    for ext in (".jpg", ".jpeg", ".png"):
        p = SHOTS / (name + ext)
        if p.exists():
            return b64(p)
    return None

# 关键帧
idle = load("01-idle")
report = load("03-report")
history = load("04-history")
light = load("05-light")
run_files = sorted(glob.glob(str(SHOTS / "02-run-*")))
# 挑选执行帧：<=5 张全用，>5 张均匀取 5 张
n = len(run_files)
if n == 0:
    run_frames = []
elif n <= 5:
    run_frames = [b64(Path(f)) for f in run_files]
else:
    idx = [int(i * (n - 1) / 4) for i in range(5)]
    run_frames = [b64(Path(run_files[i])) for i in idx]

def fig(data, cap, sub=""):
    if not data:
        return ""
    s = f'<figure><img src="data:image/jpeg;base64,{data}" alt="{cap}"/>'
    s += f'<figcaption><b>{cap}</b>'
    if sub:
        s += f"<span>{sub}</span>"
    s += "</figcaption></figure>"
    return s

# 执行帧轮播（横向）
run_gallery = "".join(
    fig(rf, f"执行过程 · 帧 {i+1}", "认知星图五阶段随执行实时点亮，时间线滚动") for i, rf in enumerate(run_frames)
)

ARCH = """
<svg viewBox="0 0 720 360" class="dia" role="img" aria-label="BrowserMind 架构">
  <defs>
    <marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 Z" fill="#E0734F"/></marker>
  </defs>
  <g font-family="Inter,system-ui" font-size="13" fill="#F3EEE6">
    <rect x="20" y="150" width="92" height="48" rx="10" fill="#1B2030" stroke="#3A455E"/>
    <text x="66" y="179" text-anchor="middle">用户任务</text>
    <rect x="140" y="150" width="92" height="48" rx="10" fill="#16263a" stroke="#6FA8E0"/>
    <text x="186" y="170" text-anchor="middle" fill="#6FA8E0">Planner</text>
    <text x="186" y="186" text-anchor="middle" font-size="10" fill="#9AA3B6">规划</text>
    <rect x="262" y="150" width="100" height="48" rx="10" fill="#2a1b16" stroke="#E0734F"/>
    <text x="312" y="170" text-anchor="middle" fill="#E0734F">Agent Loop</text>
    <text x="312" y="186" text-anchor="middle" font-size="10" fill="#9AA3B6">think→act→observe</text>
    <rect x="396" y="40" width="120" height="44" rx="9" fill="#16261f" stroke="#5FC2AE"/>
    <text x="456" y="67" text-anchor="middle" fill="#5FC2AE" font-size="11">BrowserTool</text>
    <rect x="396" y="150" width="120" height="44" rx="9" fill="#2a2416" stroke="#E0B552"/>
    <text x="456" y="177" text-anchor="middle" fill="#E0B552" font-size="11">Search 三级降级</text>
    <rect x="396" y="260" width="120" height="44" rx="9" fill="#241a2a" stroke="#B98FCB"/>
    <text x="456" y="287" text-anchor="middle" fill="#B98FCB" font-size="11">Parser 提炼</text>
    <rect x="548" y="150" width="104" height="48" rx="10" fill="#241a26" stroke="#B98FCB"/>
    <text x="600" y="170" text-anchor="middle" fill="#B98FCB">Reflection</text>
    <text x="600" y="186" text-anchor="middle" font-size="10" fill="#9AA3B6">反思自检</text>
    <rect x="548" y="260" width="104" height="44" rx="9" fill="#1b2230" stroke="#5DC1A0"/>
    <text x="600" y="287" text-anchor="middle" fill="#5DC1A0" font-size="11">Analyst 报告</text>
    <line x1="112" y1="174" x2="138" y2="174" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="232" y1="174" x2="260" y2="174" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="362" y1="168" x2="394" y2="78" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="362" y1="174" x2="394" y2="172" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="362" y1="180" x2="394" y2="270" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="516" y1="172" x2="546" y2="172" stroke="#E0734F" marker-end="url(#ar)"/>
    <line x1="600" y1="198" x2="600" y2="258" stroke="#5DC1A0" marker-end="url(#ar)"/>
    <line x1="652" y1="174" x2="690" y2="174" stroke="#5DC1A0" marker-end="url(#ar)"/>
    <text x="700" y="179" font-size="10" fill="#9AA3B6">报告</text>
    <rect x="262" y="300" width="100" height="34" rx="8" fill="#151923" stroke="#2A3346"/>
    <text x="312" y="321" text-anchor="middle" font-size="10" fill="#69728A">WebSocket 实时可视化</text>
    <line x1="312" y1="300" x2="312" y2="198" stroke="#3A455E" stroke-dasharray="3 3"/>
  </g>
</svg>
"""

LOOP = """
<svg viewBox="0 0 480 300" class="dia" role="img" aria-label="think-act-observe 循环">
  <defs>
    <marker id="ar2" markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">
      <path d="M0,0 L9,5 L0,10 Z" fill="#E0734F"/></marker>
  </defs>
  <g font-family="Inter,system-ui" font-size="13" fill="#F3EEE6">
    <circle cx="240" cy="150" r="30" fill="#2a1b16" stroke="#E0734F"/>
    <text x="240" y="146" text-anchor="middle" fill="#E0734F" font-size="12">Think</text>
    <text x="240" y="162" text-anchor="middle" font-size="9" fill="#9AA3B6">LLM+工具调用</text>
    <circle cx="380" cy="150" r="30" fill="#16261f" stroke="#5FC2AE"/>
    <text x="380" y="147" text-anchor="middle" fill="#5FC2AE" font-size="12">Act</text>
    <text x="380" y="162" text-anchor="middle" font-size="9" fill="#9AA3B6">执行工具</text>
    <circle cx="380" cy="40" r="30" fill="#2a2416" stroke="#E0B552"/>
    <text x="380" y="37" text-anchor="middle" fill="#E0B552" font-size="12">Observe</text>
    <text x="380" y="52" text-anchor="middle" font-size="9" fill="#9AA3B6">回灌上下文</text>
    <path d="M270,150 C330,150 350,150 350,150" stroke="#E0734F" fill="none" marker-end="url(#ar2)"/>
    <path d="M380,120 C380,90 380,72 380,70" stroke="#5FC2AE" fill="none" marker-end="url(#ar2)"/>
    <path d="M350,40 C300,40 250,55 240,82" stroke="#E0B552" fill="none" marker-end="url(#ar2)"/>
    <text x="330" y="200" font-size="10" fill="#69728A">LLM 不再调用工具 →</text>
    <path d="M210,150 C150,150 120,150 90,150" stroke="#9AA3B6" stroke-dasharray="4 3" fill="none" marker-end="url(#ar2)"/>
    <circle cx="60" cy="150" r="30" fill="#241a26" stroke="#B98FCB"/>
    <text x="60" y="147" text-anchor="middle" fill="#B98FCB" font-size="11">Reflect</text>
    <text x="60" y="162" text-anchor="middle" font-size="8" fill="#9AA3B6">完成度评估</text>
    <text x="60" y="200" text-anchor="middle" font-size="9" fill="#69728A">→ Analyst → 报告</text>
  </g>
</svg>
"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BrowserMind · 全方位演示</title>
<style>
:root{{--space:#0B0D13;--space2:#10131B;--surface:#151923;--surface2:#1B2030;--border:#2A3346;--ink:#F3EEE6;--text:#DCD6CC;--text2:#9AA3B6;--text3:#69728A;--accent:#E0734F;--ok:#5DC1A0;--warn:#E0B552;--sp1:4px;--sp2:8px;--sp3:12px;--sp4:16px;--sp5:24px;--sp6:32px;--maxw:980px}}
*{{box-sizing:border-box}}
body{{margin:0;background:radial-gradient(120% 80% at 50% -10%, #15131b 0%, var(--space) 55%);color:var(--text);font-family:Inter,system-ui,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7}}
.nav{{position:sticky;top:0;z-index:20;backdrop-filter:blur(10px);background:rgba(11,13,19,.78);border-bottom:1px solid var(--border);padding:10px 16px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}}
.nav b{{color:var(--ink);font-family:"Fraunces",serif}}
.nav a{{color:var(--text2);text-decoration:none;font-size:13px}}
.nav a:hover{{color:var(--accent)}}
.wrap{{max-width:var(--maxw);margin:0 auto;padding:0 18px 80px}}
.hero{{padding:54px 0 30px;text-align:center}}
.hero h1{{font-family:"Fraunces",serif;font-size:46px;margin:0 0 8px;color:var(--ink);letter-spacing:.5px}}
.hero h1 span{{color:var(--accent)}}
.hero p{{color:var(--text2);font-size:17px;max-width:680px;margin:8px auto}}
.badges{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:14px}}
.badge{{font-size:12px;color:var(--text2);border:1px solid var(--border);background:var(--surface);padding:4px 10px;border-radius:999px}}
h2{{font-family:"Fraunces",serif;color:var(--ink);font-size:27px;margin:46px 0 6px;padding-top:10px}}
h2 .k{{color:var(--accent)}}
.lead{{color:var(--text2);margin:0 0 16px}}
figure{{margin:14px 0;background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden}}
figure img{{width:100%;display:block}}
figcaption{{padding:10px 14px;font-size:13px;color:var(--text2);border-top:1px solid var(--border)}}
figcaption b{{color:var(--ink);margin-right:8px}}
figcaption span{{display:block;color:var(--text3);font-size:12px;margin-top:2px}}
.runrow{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
@media(max-width:680px){{.runrow{{grid-template-columns:1fr}}}}
.dia{{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:8px}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
@media(max-width:680px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
.card h3{{margin:0 0 4px;color:var(--ink);font-size:15px}}
.card p{{margin:0;color:var(--text2);font-size:13px}}
.stages{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}
.stage{{font-size:13px;padding:6px 12px;border-radius:999px;border:1px solid var(--border)}}
.s-plan{{color:#6FA8E0;border-color:#2c4a66}}.s-browse{{color:#5FC2AE;border-color:#1f4a40}}
.s-parse{{color:#E0B552;border-color:#5a4a1f}}.s-analyze{{color:#E0734F;border-color:#5a2f22}}
.s-reflect{{color:#B98FCB;border-color:#3f2f4a}}
code{{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:1px 6px;color:#E0B552;font-family:"JetBrains Mono",monospace;font-size:12px}}
pre{{background:#0c0f16;border:1px solid var(--border);border-radius:10px;padding:14px 16px;overflow:auto;color:#DCD6CC;font-family:"JetBrains Mono",monospace;font-size:12.5px;line-height:1.6}}
.kpi{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}
.kpi div{{flex:1;min-width:120px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center}}
.kpi b{{display:block;color:var(--accent);font-size:22px;font-family:"Fraunces",serif}}
.kpi span{{font-size:12px;color:var(--text2)}}
.scene{{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:10px;padding:12px 16px;margin:10px 0}}
.scene b{{color:var(--ink)}}
.note{{background:#14110d;border:1px solid #3a2f22;border-radius:10px;padding:12px 16px;color:var(--text2);font-size:13px}}
footer{{text-align:center;color:var(--text3);font-size:12px;padding:30px 0}}
</style></head>
<body>
<nav class="nav"><b>✦ BrowserMind</b>
<a href="#demo">实机演示</a><a href="#arch">架构</a><a href="#loop">执行回路</a>
<a href="#feat">核心特性</a><a href="#eng">工程指标</a><a href="#scene">三场景</a>
<a href="#run">如何运行</a></nav>
<div class="wrap">

<div class="hero">
  <h1>BrowserMind <span>· 会思考的浏览器</span></h1>
  <p>一个能自主规划、操控真实浏览器、读懂网页并生成带来源报告的 AI Agent。输入一句自然语言，剩下的「搜什么 / 点哪里 / 读什么 / 怎么总结」全部由它自己完成。</p>
  <div class="badges">
    <span class="badge">FastAPI + WebSocket</span><span class="badge">Playwright 真浏览器</span>
    <span class="badge">OpenAI 兼容 / 多模型</span><span class="badge">Python 异步 think→act→observe</span>
    <span class="badge">71 个 pytest 用例</span><span class="badge">Docker 一键部署</span>
  </div>
</div>

<h2 id="demo">实机<span class="k">演示</span></h2>
<p class="lead">以下截图均来自本次真实启动的服务与真实运行的 Agent 任务（非模拟）。任务：<code>查一下今天 AI 领域有哪些重要新闻，给出 3-5 条摘要，并附上来源链接。</code></p>

{fig(idle, "① 静候 · 认知星图", "启动后界面：左=任务与计划，中=实时时间线，右=报告。五阶段星图待命。")}

<div class="runrow">
{run_gallery}
</div>

{fig(report, "② 报告生成 · Agent 真实产出", "右栏 Markdown 报告成形（含结论与条目），可下载 .md；本次因目标信息可达性存在提取提示，但 Agent 仍自主完成规划→浏览→解析→分析→反思全链路。")}
{fig(history, "③ 星图历史 · 可单删 / 清空", "跑过的任务以星点留存；每条可悬浮删除，顶部「清空历史」带二次确认。")}
{fig(light, "④ 浅色主题 · 羊皮纸", "一键切换深空 / 羊皮纸双主题，演示与答辩皆宜。")}

<h2 id="arch">系统<span class="k">架构</span></h2>
<p class="lead">用户给任务 → Planner 拆步骤 → Agent Loop 调度三类工具（浏览器 / 搜索 / 解析）→ Reflection 反思自检 → Analyst 出报告；全程 WebSocket 实时推到前端认知星图。</p>
{ARCH}

<h2 id="loop">Agent <span class="k">执行回路</span></h2>
<p class="lead">核心是手写异步 <code>think→act→observe</code> 循环（OpenAI function calling），未用 LangChain：每轮把「工具调用+结果」追加进上下文，像人一样边做边看边调整；LLM 不再调用工具即进入反思，再决定是否完成 / 补充 / 暂停等人。</p>
{LOOP}

<h2 id="feat">核心<span class="k">特性</span></h2>
<div class="stages">
  <span class="stage s-plan">规划 Planner</span><span class="stage s-browse">浏览 BrowserTool</span>
  <span class="stage s-parse">解析 Parser</span><span class="stage s-analyze">分析 Analyst</span>
  <span class="stage s-reflect">反思 Reflection</span>
</div>
<div class="grid">
  <div class="card"><h3>自主任务规划</h3><p>自然语言任务自动拆为可执行步骤，模型自己决定先搜谁、先读哪页，流程不写死。</p></div>
  <div class="card"><h3>真实浏览器操控</h3><p>Playwright 打开 / 点击 / 输入 / 滚动 / 截图 / 取文本——真 Chromium，不是假装上网；SPA 四级渐进等待防卡死。</p></div>
  <div class="card"><h3>网页正文提炼</h3><p>BeautifulSoup + Readability + html2text 把广告 / 导航 / 脚本噪声去掉，转成干净 Markdown 喂给 LLM。</p></div>
  <div class="card"><h3>反思与自检</h3><p>评估完成度，决定继续 / 补充 / 暂停等人；多轮追问带「防短路」守卫，逼 LLM 真去重查而非换皮旧报告。</p></div>
  <div class="card"><h3>人在回路</h3><p>Reflection 可暂停，等待「继续 / 调整」并支持追加指令的多轮对话；随时可停止。</p></div>
  <div class="card"><h3>轻量报告重生成</h3><p><code>POST /api/report/regenerate</code> 复用已抓取信息直接重出报告，不重开浏览器、不重爬页面。</p></div>
  <div class="card"><h3>实时可视化工作台</h3><p>认知星图五阶段随执行实时点亮连线，时间线滚动，过程完全看得见。</p></div>
  <div class="card"><h3>多模型兼容</h3><p>对接 OpenAI 兼容 API，运行时切换 Qwen / DeepSeek / GPT / 智谱，密钥按供应商归档且前端不回显。</p></div>
</div>

<h2 id="eng">工程<span class="k">硬指标</span></h2>
<div class="kpi">
  <div><b>71</b><span>pytest 用例 / 11 文件</span></div>
  <div><b>7</b><span>@tool 注册工具</span></div>
  <div><b>6</b><span>agent 模块</span></div>
  <div><b>4</b><span>兼容模型供应商</span></div>
  <div><b>3</b><span>搜索降级层级</span></div>
  <div><b>0</b><span>ruff / mypy 告警</span></div>
</div>
<p class="lead">Docker + docker-compose 一键部署（数据卷持久化）、GitHub Actions CI 自动跑测试、可选 <code>AUTH_TOKEN</code> 鉴权（公网可加锁）、运行日志落盘可追溯。</p>

<h2 id="scene">三<span class="k">场景</span>一句话</h2>
<div class="scene"><b>毕设答辩</b>：重工程完整性与选型理由——手写循环 vs LangChain、Playwright vs Selenium、前端做轻后端做重；坦诚不足反而加分。</div>
<div class="scene"><b>简历 / 面试</b>：一句话定位 + 量化指标 + STAR 深挖（Agent 内核可中断、工具注册表开闭原则、多轮防短路）。</div>
<div class="scene"><b>路演 / 黑客松</b>：Hook 抓人 → 现场点亮星图 → 「它有手有眼，真会上网」→ 差异化（带来源报告，非套壳复述）。</div>

<h2 id="run">如何<span class="k">运行</span></h2>
<pre># 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置（填入 LLM_API_KEY）
cp .env.example .env

# 3. 启动
python main.py          # 打开 http://localhost:8000

# 或一键容器化
docker compose up -d --build</pre>
<p class="lead">前端零构建单文件，部署只需一个静态目录；WebSocket 实时驱动，评委复现门槛低。</p>

<h2>坦诚的<span class="k">不足</span></h2>
<div class="note">尚无自动评测数据集（难量化跨任务稳定性）；当前单进程，未做任务队列与水平扩展；报告质量依赖单次 LLM 调用，未做多轮自我精修；前端为单文件未组件化（明确取舍）。这些都是 roadmap，被问到即如实说明——比硬编更得分。</div>

<footer>BrowserMind · 根据项目真实代码生成的全方位演示 · { "" if True else "" }</footer>
</div></body></html>
"""

OUT.write_text(html, encoding="utf-8")
print("DEMO_WRITTEN", OUT, "bytes=", len(html), "run_frames=", len(run_frames),
      "idle=", bool(idle), "report=", bool(report), "history=", bool(history), "light=", bool(light))
