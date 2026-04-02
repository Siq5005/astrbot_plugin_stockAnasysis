# 更新日志

本项目的所有重要更改均会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.1.0] - 2026-04-02

### 新增

- ✨ **PDF 导出开关** — 新增 `export_pdf` 配置项（默认开启），关闭后报告以 Markdown 分模块逐段发送，适合移动端阅读、防止消息截断
- 📋 **报告分模块输出** — 关闭 PDF 导出时，报告按 `##` 标题自动拆分为 6 段（标题信息、市场技术面、基本面、新闻面、多空辩论、风险评估）逐段发送
- 🔤 **内嵌中文字体** — PDF 生成使用项目自带 `fonts/NotoSansSC-Regular.ttf` 和 `fonts/NotoSansSC-Bold.ttf`，不再依赖系统字体，Docker 部署无需额外安装字体

### 修复

- 🐛 **PDF 中文渲染方块问题** — 修复 CSS `@font-face` 中 `format("opentype")` 与 `.ttf`（TrueType）字体格式不匹配，解决 PDF 导出中文显示"口口口"方块的问题

### 变更

- 🖼️ 更新插件头像

---

## [1.0.0] - 2026-03-26

### 初始发布

- 🔍 **智能股票分析** — 输入股票代码或名称，生成完整的分析报告
- 🤖 **多智能体架构** — 基于 LangGraph 编排市场分析师、基本面分析师、新闻分析师
- ⚖️ **多空辩论机制** — 多方研究员与空方研究员进行投资辩论，碰撞观点
- 🛡️ **风险评估裁判** — 风险裁判综合评估整体投资风险等级
- 🌐 **多市场支持** — A 股（沪深）、港股、美股全覆盖
- 📊 **多数据源** — akshare（A 股/港股/美股实时行情）+ yfinance（港股/美股基本面与新闻）
- 📄 **PDF + Markdown 双格式报告导出**
- 📱 **移动端支持** — 报告适配移动端查看
- 🔧 **OpenAI 兼容协议** — 支持智谱 GLM、DeepSeek、OpenAI、MiniMax 等多厂商模型

---

[1.1.0]: https://github.com/YYY7C/TradingAgents-AstrBot/releases/tag/v1.1.0
[1.0.0]: https://github.com/YYY7C/TradingAgents-AstrBot/releases/tag/v1.0.0
