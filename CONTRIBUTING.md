# 贡献指南（Contributing Guide）

感谢你关注 **BrowserMind**！无论是修 bug、补文档，还是提出新功能，都欢迎参与。

## 行为准则

请保持友善、尊重。我们采用常见的开源社区礼仪：就事论事、对事不对人。

## 开发环境

```bash
# 1. Fork 并 clone 你的副本
git clone https://github.com/<your-name>/browsermind.git
cd browsermind

# 2. 创建虚拟环境（推荐）
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 5. 启动
python main.py
# 浏览器打开 http://localhost:8000
```

## 分支与提交规范

- 从 `main` 切出特性分支：`feat/xxx`、`fix/xxx`、`docs/xxx`
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

  ```
  feat: 新增可插拔搜索工具接口
  fix: 修复 WebSocket 断线后决策队列泄漏
  docs: 补充 API 文档
  ```

## 提交流程（Pull Request）

1. 确保你的改动通过了本地冒烟测试（启动服务、跑一个简单任务）
2. 在 PR 中说明：**改了什么 / 为什么改 / 如何验证**
3. 关联相关 issue（如有）
4. 等待 review，及时回应修改意见

## 代码风格

- Python：遵循 PEP 8，关键逻辑加精简注释
- 新增 API / 工具：同步更新 README 的「API 速览」与「项目结构」
- 不要在代码或提交中写入密钥（`.env` 已被 `.gitignore` 忽略）

## 报 Bug / 提需求

请直接在 GitHub Issues 描述：**复现步骤 / 期望行为 / 实际行为 / 环境信息**。
