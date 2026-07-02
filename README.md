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
> - 数据源：纯国信证券官方 API（4 个 Skill，stdlib 零依赖）
> - 编排引擎：LangGraph 并行图（三个分析师并行 + 多空并行）
> - LLM：复用 AstrBot 内置模型，无需单独配置 API Key
> - 输出：简洁买卖建议 + 仓位建议（一句话结论，追问可展开详细分析）

## ✨ 功能特性

- 🗣️ **自然语言交互** — LLM 自动调用工具，"分析一下平安银行"即可触发完整分析
- 🔍 **智能股票分析** — LangGraph 并行架构，技术面/基本面/宏观面三位分析师同时跑
- 📡 **技术信号评分** — MACD/KDJ/RSI/均线/量能五项打分，纯数学计算，零 LLM 消耗（`/信号`）
- ⚡ **快速模式** — 跳过多空辩论（`/快速分析`），也可自然语言"快速看下茅台"
- 🔎 **智能选股** — 自然语言条件筛选（`/选股 市盈率小于20的银行股`）
- 📊 **自选股监控** — 添加/删除/列表管理，建议变化时推送通知（`/监控`）
- 📈 **历史回测** — 4 策略引擎（MACD/MA/RSI/KDJ），模拟交易看收益（`/回测`）
- 💰 **仓位建议** — 分析结果包含轻仓/中等/重仓建议
- 🌍 **多市场覆盖** — A 股、港股、美股，Prompt 按市场适配

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

### 无需额外配置

插件安装后即可使用。LLM 复用 AstrBot 内置模型，数据源为国信 API（需设置 `GS_API_KEY` 环境变量）。所有命令和 LLM Tool 开箱即用。

## 📖 使用方法

支持**斜杠命令**和**自然语言**两种方式，LLM 自动识别意图并路由。

| 功能 | 斜杠命令 | 自然语言 |
|------|----------|----------|
| 股票分析 | `/股票分析 000001` | "帮我分析一下平安银行" |
| 快速分析 | `/快速分析 平安银行` | "快速看看腾讯" |
| 技术信号 | `/信号 000001` | "000001 技术面怎么看" |
| 选股 | `/选股 市盈率<20 银行股` | "筛选市盈率小于20的银行股" |
| 查股 | `/查股 AAPL` | "宁德时代是什么股票" |
| 监控 | `/监控 添加/删除/列表/检查` | — |
| 回测 | `/回测 000001 --strategy macd` | — |
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

### v2.0 架构（LangGraph 并行）

```
用户输入（斜杠命令 或 LLM Tool 自动触发）
    │
    └──→ TradingGraph.analyze()
            │
            ├── 数据收集（asyncio.gather 并发）
            │     ├── K线 + 实时行情 + 资金流向  → 国信行情 API
            │     ├── 资产负债表/利润表/现金流    → 国信财报 API
            │     └── 宏观经济指标               → 国信宏观 API
            │
            ├── 三位分析师并行（asyncio.gather）
            │     ├── 技术面 (MACD/均线/KDJ/RSI)
            │     ├── 基本面 (PE/PB/ROE/利润增速)
            │     └── 宏观面 (政策/情绪/资金)
            │
            ├── 多空辩论（完整模式，asyncio.gather 并行）
            │     ├── 多方研究员（挖掘利好）
            │     └── 空方研究员（挖掘利空）
            │
            ├── 风险评估 → 综合结论 + 仓位建议
            │
            └── 输出 → 一句话结论 + 可展开详细分析
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
