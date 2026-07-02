# astrbot_plugin_stockAnasysis 📈

[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.9-green.svg)](https://python.org)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.14-Plugin-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/Version-2.0.0-brightgreen.svg)]()

基于 **国信证券 API + AstrBot SubAgent** 的多智能体金融分析插件，支持 A 股、港股、美股的智能分析报告生成和自然语言选股。

> 📌 **Fork 自 [TradingAgents-AstrBot](https://github.com/YYY7C/TradingAgents-AstrBot)**（作者 [YYY7C](https://github.com/YYY7C)），感谢原项目的优秀工作。
>
> 💡 原项目灵感来源于 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 和 [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) 的多智能体辩论架构。
>
> **v2.0 大重构**（本仓库）：
> - 数据源：akshare/yfinance → 国信证券官方 API（4 个 Skill，纯 stdlib）
> - 编排引擎：LangGraph → AstrBot SubAgent 原生框架
> - 依赖简化：9 个 → 2 个，零爬取依赖
> - 新增：`/选股` 命令、宏观经济数据、财报深度分析

## ✨ 功能特性

- 🗣️ **自然语言交互** — 支持"分析一下平安银行"等自然语言输入，LLM 自动识别意图
- 🔍 **智能股票分析** — 输入股票代码或名称，生成完整的多智能体分析报告
- ⚡ **快速分析模式** — 跳过多空辩论，更快生成分析报告（`/快速分析`）
- 🔎 **自然语言选股** — 用中文描述条件即可筛选股票（`/选股 市盈率小于20的银行股`）
- 🌍 **宏观经济查询** — 内置全球宏观经济数据（GDP/CPI/PMI/汇率/商品期货等）
- 📊 **财报深度分析** — A股/H股资产负债表、利润表、现金流量表（PE/PB/ROE/ROA 等核心指标）
- 🤖 **多智能体协作** — 7 个专业子智能体并行分析（市场/基本面/新闻/多方/空方/辩论主管/风险评估）
- ⚖️ **多空辩论机制** — 多方与空方研究员独立研究，研究主管综合辩论
- 🛡️ **风险评估裁判** — 综合评估整体投资风险等级
- 📄 **PDF/TXT 报告导出** — 支持 PDF 附件（需系统依赖）或 Markdown 分模块发送
- 📱 **移动端支持** — 在移动设备上也能查看分析报告

## 📋 报告示例

| 市场 | 股票 | 报告 |
|------|------|------|
| 🇨🇳 A 股 | 厦门港务 (000905) | [查看报告](reports/example_A股_厦门港务_000905.md) |
| 🇭🇰 港股 | 腾讯控股 (0700.HK) | [查看报告](reports/example_港股_腾讯控股_0700.md) |
| 🇺🇸 美股 | 苹果 (AAPL) | [查看报告](reports/example_美股_苹果_AAPL.md) |

## 🔧 安装

### 1. 安装插件

在 AstrBot 插件市场搜索 `tradingassistant` 安装，或手动克隆：

```bash
git clone https://github.com/Siq5005/astrbot_plugin_stockAnasysis.git AstrBot/data/plugins/astrbot_plugin_stockanalysis
```

> ⚠️ **重要**：AstrBot 要求插件目录名与 `metadata.yaml` 的 `name` 字段一致，且全部小写。必须克隆到 `astrbot_plugin_stockanalysis` 目录中，否则 AstrBot 会提示"找不到 metadata.yaml"。

### 2. 安装依赖

```bash
pip install markdown weasyprint
```

> 国信 API 数据源使用纯 Python stdlib，零额外依赖。PDF 导出需要系统依赖（`libglib2.0-0`、`libpango`、`libcairo2` 等），否则将自动降级为 TXT。

### 3. 获取国信 API Key

访问 [https://www.guosen.com.cn/gs/xxskills/index.html](https://www.guosen.com.cn/gs/xxskills/index.html) 注册获取 API Key（免费）。

## ⚙️ 配置

### 插件配置（WebUI）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `gs_api_key` | 国信证券 API Key（必填） | — |
| `export_pdf` | 是否导出 PDF 报告 | `true` |
| `default_market` | 默认市场 | `AUTO` |

### 环境变量

```bash
export GS_API_KEY="你的国信API密钥"
```

### SubAgent 编排配置（WebUI → SubAgent 编排）

v2.0 的核心是 **AstrBot SubAgent 多智能体协作**，需要在 WebUI 中创建 7 个子智能体：

| 子智能体 | Agent Name | 分配工具 | Persona 文件 |
|----------|-----------|---------|-------------|
| 市场技术面分析师 | `market_analyst` | K线、实时行情、资金流向、涨跌排名 | [market_analyst.md](subagent_personas/market_analyst.md) |
| 基本面分析师 | `fundamentals_analyst` | 财务报表、实时行情 | [fundamentals_analyst.md](subagent_personas/fundamentals_analyst.md) |
| 新闻宏观分析师 | `news_analyst` | 宏观经济、实时行情、资金流向 | [news_analyst.md](subagent_personas/news_analyst.md) |
| 多方研究员 | `bull_researcher` | K线、实时行情、资金流向 | [bull_researcher.md](subagent_personas/bull_researcher.md) |
| 空方研究员 | `bear_researcher` | K线、实时行情、资金流向 | [bear_researcher.md](subagent_personas/bear_researcher.md) |
| 研究主管 | `research_manager` | 无工具（纯综合） | [research_manager.md](subagent_personas/research_manager.md) |
| 风险评估官 | `risk_judge` | K线、实时行情、资金流向、宏观经济 | [risk_judge.md](subagent_personas/risk_judge.md) |

创建每个子智能体时：
1. 填写 Agent Name（自动生成 `transfer_to_*` 工具）
2. 在 Persona 编辑器中粘贴对应 `.md` 文件的全部内容
3. 在工具分配中选择对应的工具组
4. Description 填写一句话说明（如"负责股票技术面分析，可调用行情和K线数据"）

> 详细工具分组参考 [astrbot_tools.py](astrbot_tools.py) 的 `TOOL_GROUPS`。

## 📖 使用方法

支持**斜杠命令**和**自然语言**两种方式，LLM 自动识别意图并路由。

| 功能 | 斜杠命令 | 自然语言 |
|------|----------|----------|
| 股票分析 | `/股票分析 000001` | "帮我分析一下平安银行"、"茅台怎么样" |
| 快速分析 | `/快速分析 平安银行` | "快速看看腾讯"、"简单分析下AAPL" |
| 选股 | `/选股 市盈率小于20的银行股` | "筛选市盈率小于20的银行股"、"有没有股息率高的蓝筹股" |
| 查股 | `/查股 AAPL` | "宁德时代是什么股票"、"AAPL代码是多少" |
| 帮助 | `/帮助` | "你能做什么" |

### 支持的股票格式

- **A 股**: `000001`、`600519`、`平安银行`、`茅台`
- **港股**: `0700.HK`、`腾讯控股`、`美团`
- **美股**: `AAPL`、`TSLA`、`NVDA`

### 选股示例

```
/选股 市盈率小于20的银行股
/选股 MACD金叉且成交量放大的科技股
筛选 净利润增长大于30%的医药股
有没有 股息率高的蓝筹股
```

## 🏗️ 技术架构

### v2.0 架构（当前）

```
用户输入（斜杠命令 或 自然语言）
    │
    ├── /命令 → 直接路由
    └── 自然语言 → LLM 意图识别 → 自动路由
    │
    └──→ 主智能体（TradingAgents-AstrBot）
            │
            ├── 数据收集（国信 API 工具）
            │     ├── tool_query_historical_kline  → 国信行情 API
            │     ├── tool_query_single_quote     → 国信行情 API
            │     ├── tool_query_fund_flow        → 国信行情 API
            │     ├── tool_query_financials        → 国信财报 API
            │     └── tool_query_macro_data       → 国信宏观 API
            │
            ├── 并行调度（AstrBot SubAgent）
            │     ├── transfer_to_market_analyst       → 📊 技术面分析
            │     ├── transfer_to_fundamentals_analyst → 📈 基本面分析
            │     └── transfer_to_news_analyst         → 📰 宏观/情绪分析
            │
            ├── 多空辩论（并行）
            │     ├── transfer_to_bull_researcher → 🐂 多方研究
            │     └── transfer_to_bear_researcher → 🐻 空方研究
            │
            ├── transfer_to_research_manager → ⚖️ 辩论综合
            │
            ├── transfer_to_risk_judge → 🛡️ 风险评估
            │
            └── 汇总 → 📄 最终分析报告（PDF/TXT/Markdown）
```

### 数据源架构

```
data_sources/              # 国信 API 数据源包
├── http_client.py         # 共享 HTTP 层（urllib + curl 降级，宽松 SSL）
├── market_data.py         # 行情 API（6 端点）
├── financial_data.py      # 财报 API（6 端点）
├── macro_data.py          # 宏观 API（1 端点，自然语言查询）
└── stock_picking.py       # 选股 API（1 端点，自然语言筛选）

所有模块纯 Python stdlib，零第三方依赖。
API Base: https://dgzt.guosen.com.cn/skills
认证: GS_API_KEY 环境变量 + apiKey 查询参数
```

## 📦 依赖

| 依赖 | 用途 | 备注 |
|------|------|------|
| `markdown` | Markdown→HTML 转换 | PDF 导出依赖 |
| `weasyprint` | HTML→PDF 渲染 | 需系统依赖 |

国信 API 调用层使用纯 Python stdlib（`urllib` + `subprocess`），无任何第三方依赖。

## 🙏 致谢

- **[TradingAgents-AstrBot](https://github.com/YYY7C/TradingAgents-AstrBot)**（作者 [YYY7C](https://github.com/YYY7C)）— 本项目 Fork 来源，提供了 v1.x 的完整插件框架
- **[AstrBot](https://github.com/AstrBotDevs/AstrBot)** — 优秀的 Agent 框架，SubAgent 功能让多智能体协作成为可能
- **[国信证券](https://www.guosen.com.cn/gs/xxskills/index.html)** — 提供官方金融数据 API 服务
- **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** — 多智能体辩论的原始架构与核心思路
- **[TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)** — 中文本地化改进与 A 股适配方案

## ⚠️ 免责声明

本插件生成的分析报告仅供学习与参考，**不构成任何投资建议**。投资有风险，入市需谨慎。使用者应基于自身判断做出投资决策，本插件开发者不对任何因使用本插件而产生的投资损失承担责任。

## 📄 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE) 许可证。

```
Copyright (C) 2024-2026 Coe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```
