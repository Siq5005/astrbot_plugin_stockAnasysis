# TradingAgents-AstrBot 📈

[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.9-green.svg)](https://python.org)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-orange.svg)](https://github.com/AstrBotDevs/AstrBot)

基于多智能体辩论架构的 AstrBot 金融分析插件，支持 A 股、港股、美股的智能分析报告生成。

> 💡 本项目灵感来源于 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 和 [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)，感谢这两个优秀框架提供的多智能体辩论思路与架构设计。

## ✨ 功能特性

### 已经实现

- 🔍 **智能股票分析** — 输入股票代码或名称，生成完整的分析报告
- ⚡ **快速分析模式** — 跳过多空辩论，更快生成分析报告（`/快速分析`）
- 📊 **ETF 支持** — 支持 A 股 ETF 基金分析，自动识别 ETF 代码并使用基金专用数据接口
- 🤖 **多智能体架构** — 基于 LangGraph 编排市场分析师、基本面分析师、新闻分析师
- ⚖️ **多空辩论机制** — 多方研究员与空方研究员进行投资辩论，碰撞观点
- 🛡️ **风险评估裁判** — 风险裁判综合评估整体投资风险等级
- 🔄 **多数据源容灾** — 东方财富数据源不可用时自动降级到腾讯财经接口
- 📱 **移动端支持** — 在移动设备上也能查看分析报告

### 待实现

- 🌐 **多市场支持** — A 股（沪深）、港股、美股全覆盖
- 📊 **多数据源** — akshare（A 股/港股/美股实时行情）+ yfinance（港股/美股基本面与新闻）
- 🧠 **多模型结合** — 结合多厂商模型分析结果

## 📋 报告示例

| 市场 | 股票 | 报告 |
|------|------|------|
| 🇨🇳 A 股 | 厦门港务 (000905) | [查看报告](reports/example_A股_厦门港务_000905.md) |
| 🇭🇰 港股 | 腾讯控股 (0700.HK) | [查看报告](reports/example_港股_腾讯控股_0700.md) |
| 🇺🇸 美股 | 苹果 (AAPL) | [查看报告](reports/example_美股_苹果_AAPL.md) |

## 🔧 安装

在 AstrBot 插件市场搜索 `tradingassistant` 安装，或手动将本仓库克隆到 `AstrBot/data/plugins/` 目录：

```bash
git clone https://github.com/YYY7C/TradingAgents-AstrBot.git
```

## ⚙️ 配置

安装后在 AstrBot WebUI 的插件配置页面填写以下信息：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | OpenAI 兼容 API Key（必填） | — |
| `api_base` | API 地址 | `https://open.bigmodel.cn/api/paas/v4` |
| `model` | 模型名称 | `glm-4-flash` |
| `reasoning` | 是否启用推理模式 | `false` |
| `timeout_seconds` | LLM 单次调用超时（秒） | `120` |
| `default_market` | 默认市场 | `AUTO` |
| `export_pdf` | 是否导出 PDF 报告，关闭后分模块发送 | `true` |

> 支持 OpenAI 兼容协议的各种模型（智谱 GLM、DeepSeek、OpenAI、MiniMax 等）。推荐使用支持 Function Calling 的模型以获得最佳效果。

## 📖 使用方法

| 命令 | 说明 | 示例 |
|------|------|------|
| `/股票分析 <代码或名称>` | 生成完整分析报告（含多空辩论） | `/股票分析 000001` |
| `/快速分析 <代码或名称>` | 快速分析（跳过多空辩论，速度更快） | `/快速分析 平安银行` |
| `/股票 <代码或名称>` | 快捷分析（同 `/股票分析`） | `/股票 平安银行` |
| `/查股 <代码>` | 查询股票基本信息 | `/查股 AAPL` |
| `/年报 <代码>` | 生成股票报告 | `/年报 600000` |
| `/帮助` | 显示帮助信息 | `/帮助` |

### 支持的股票格式

- **A 股**: `000001`、`600000`、`平安银行`
- **港股**: `0700.HK`、`腾讯`
- **美股**: `AAPL`、`TSLA`、`NVDA`

### ETF 支持

本插件支持 A 股 ETF（交易所交易基金）的智能分析，自动识别 ETF 代码并调用专用的基金数据接口。

**支持的 ETF 类型：**

| 交易所 | 代码前缀 | 示例 | 说明 |
|--------|----------|------|------|
| 上海 | `510xxx` | 510300（沪深300ETF） | 跨境/宽基 ETF |
| 上海 | `511xxx` | 511010（国泰上证5年期国债ETF） | 国债 ETF |
| 上海 | `512xxx` | 512010（医药ETF） | 行业/主题 ETF |
| 上海 | `513xxx` | 513100（纳指ETF） | 跨境 ETF |
| 上海 | `515xxx` | 515050（5GETF） | 行业/主题 ETF |
| 上海 | `56xxxx` | 560150（中证2000ETF） | 宽基 ETF |
| 上海 | `58xxxx` | 588000（科创50ETF） | 科创板 ETF |
| 深圳 | `159xxx` | 159915（创业板ETF） | 跨境/宽基 ETF |
| 深圳 | `150xxx` | 150019（银华锐进） | 分级基金 |
| 深圳 | `16xxxx` | 160105（南方积极配置） | LOF 基金 |

**使用示例：**

```
/快速分析 510300        → 沪深300ETF华泰柏瑞
/股票分析 512010        → 医药ETF
/快速分析 513100        → 纳指ETF
/股票 159915            → 创业板ETF
```

> 💡 输入 ETF 代码（6位数字）即可自动识别，插件会自动区分 ETF 与普通股票，并使用基金专用数据接口获取行情。

## 🏗️ 技术架构

```
用户输入
    │
    ├──→ 📊 市场分析师（Market Analyst）
    │         分析技术指标、价格走势、成交量
    │
    ├──→ 📈 基本面分析师（Fundamentals Analyst）
    │         分析财务数据、估值指标、盈利能力
    │
    ├──→ 📰 新闻分析师（News Analyst）
    │         分析相关新闻、舆情、市场情绪
    │
    │   ┌─── 完整模式（/股票分析）───────────────────┐
    │   │                                           │
    ├──→ ⚖️ 多空辩论                                │
    │         ├── 🐂 多方研究员（Bull Researcher）    │
    │         └── 🐻 空方研究员（Bear Researcher）    │
    │         └→ 研究主管（Research Manager）汇总     │
    │                                           │
    │   └─── 快速模式（/快速分析）跳过此阶段 ──────────┘
    │
    └──→ 🛡️ 风险裁判（Risk Judge）
              综合评估 → 生成最终报告
```

## 📦 依赖

- `aiohttp` — 异步 HTTP 客户端
- `akshare` — A 股/港股数据源
- `yfinance` — 美股数据源
- `langgraph` — 多智能体编排框架
- `langchain-core` — LangChain 核心
- `curl-cffi` — TLS 指纹模拟（反爬虫）
- `openai` — OpenAI 兼容 API 客户端

## 🙏 致谢

- **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** — 提供了多智能体辩论的原始架构与核心思路
- **[TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)** — 提供了中文本地化改进与 A 股适配方案
- **[AstrBot](https://github.com/AstrBotDevs/AstrBot)** — 优秀的Agent框架


## ⚠️ 免责声明

本插件生成的分析报告仅供学习与参考，**不构成任何投资建议**。投资有风险，入市需谨慎。使用者应基于自身判断做出投资决策，本插件开发者不对任何因使用本插件而产生的投资损失承担责任。

## 📄 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE) 许可证。

```
Copyright (C) 2024-2026 YYY7C

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```
