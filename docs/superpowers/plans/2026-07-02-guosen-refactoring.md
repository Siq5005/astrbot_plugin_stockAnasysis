# TradingAgents-AstrBot 重构计划：国信 API + AstrBot SubAgent 架构

> **面向执行代理：** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐一实现。步骤使用 `- [ ]` 复选框跟踪进度。

**目标：** 将当前项目从"akshare/yfinance 爬取 + LangGraph 状态图"架构重构为"纯国信证券 API 数据源 + AstrBot SubAgent 子智能体编排"架构。集成 4 个国信 API skill（行情、财报、宏观、选股），用 AstrBot 原生 SubAgent 框架替代 LangGraph 多智能体管线。

**架构变更：**

| 维度 | 旧 | 新 |
|------|-----|-----|
| 数据源 | akshare + yfinance + 腾讯财经（爬取） | 国信证券 API（4 个 skill，纯 stdlib）|
| 编排引擎 | LangGraph StateGraph（顺序节点） | AstrBot SubAgent（主智能体 + 子智能体并行） |
| 依赖 | langgraph, akshare, yfinance, curl-cffi, pandas （~8 个） | 仅 Python stdlib（零新依赖） |
| 子智能体 | LangGraph 节点（单 LLM 实例） | AstrBot transfer_to_* 独立子智能体 |

**技术栈：** Python 3.9+, 国信证券 API ×4（全部纯 stdlib：urllib + curl 降级）, AstrBot v4.14.0+ SubAgent

---

## 前置阅读：国信 API 四件套

所有 4 个 skill 共享同一套模式：
- **Base URL**: `https://dgzt.guosen.com.cn/skills`
- **认证**: `apiKey` 查询参数 + `GS_API_KEY` 环境变量
- **传输**: `urllib.request.urlopen`（宽松 SSL）→ `curl -s -k` 降级
- **依赖**: 零第三方库，纯 Python stdlib

| Skill | 目录 | 端点 | 提供数据 |
|-------|------|------|----------|
| `gs-stock-market-query` | `.../gs-stock-market-query/` | 6 个 | 实时行情、历史K线、资金流向、涨跌排名、关联板块 |
| `gs-stock-financial-query` | `.../gs-stock-financial-query/` | 6 个 | A股/H股资产负债表、利润表、现金流量表 |
| `gs-economy-query` | `.../gs-economy-query/` | 1 个 | 宏观经济指标（自然语言查询） |
| `gs-smart-stock-picking` | `.../gs-smart-stock-picking/` | 1 个 | 智能选股（自然语言条件筛选） |

---

## AstrBot SubAgent 架构说明

AstrBot SubAgent 是 v4.14.0 引入的实验性功能。架构模型：

```
用户发送命令 (/股票分析 000001)
  → 主智能体（TradingAssistantPlugin 注册的工具）
    → 调用 transfer_to_data_fetcher("获取000001的行情和财报数据")
    → 并行调用 transfer_to_market_analyst, transfer_to_fundamentals_analyst, transfer_to_news_analyst
    → 并行调用 transfer_to_bull_researcher, transfer_to_bear_researcher
    → 主智能体综合子智能体结果，调用 transfer_to_risk_judge
    → 主智能体生成最终报告
```

**配置方式：** AstrBot WebUI → SubAgent 编排页面，创建子智能体：
1. **Agent Name**: 英文名（如 `market_analyst`），自动生成 `transfer_to_market_analyst` 工具
2. **Persona**: 选择/自定义人格（包含 system prompt）
3. **Description for main LLM**: 告诉主智能体何时委托给此子智能体
4. **Assign tools**: 赋予该子智能体能调用的工具
5. **Provider override (可选)**: 不同模型提供商

**插件角色变化：** 插件不再通过 LangGraph 代码编排智能体流程，而是：
1. 注册数据获取工具（让 AstrBot 的工具系统感知国信 API）
2. 提供子智能体的 Persona 定义（prompt 模板）
3. 处理最终报告的格式化输出（PDF/Markdown）

---

## 文件结构总览

```
TradingAgents-AstrBot/
├── data_sources/                        # (NEW) 国信 API 数据工具
│   ├── __init__.py                      #   重导出所有 API 函数
│   ├── http_client.py                   #   共享 HTTP 传输层（urllib + curl 降级 + SSL）
│   ├── market_data.py                   #   行情 API（6 端点）—— 来自 gs-stock-market-query
│   ├── financial_data.py                #   财报 API（6 端点）—— 来自 gs-stock-financial-query
│   ├── macro_data.py                    #   宏观经济 API（1 端点）—— 来自 gs-economy-query
│   └── stock_picking.py                 #   智能选股 API（1 端点）—— 来自 gs-smart-stock-picking
│
├── astrbot_tools.py                     # (NEW) AstrBot 工具注册 —— 将 data_sources 包装为工具
│
├── subagent_personas/                   # (NEW) 子智能体 Persona 定义
│   ├── __init__.py
│   ├── market_analyst.md                #   市场分析师 system prompt
│   ├── fundamentals_analyst.md          #   基本面分析师 system prompt
│   ├── news_analyst.md                  #   新闻/情绪分析师 system prompt
│   ├── bull_researcher.md               #   多方研究员 system prompt
│   ├── bear_researcher.md               #   空方研究员 system prompt
│   ├── research_manager.md              #   辩论综合主管 system prompt
│   └── risk_judge.md                    #   风险评估法官 system prompt
│
├── main.py                              # (REWRITE) 插件入口 —— 注册工具 + 命令处理
├── report_generator.py                  # (NEW) 报告生成器（独立于智能体流程）
│
├── utils/                               # (保留，微调)
│   ├── __init__.py
│   ├── stock_utils.py                   #   股票代码标准化（保留现有逻辑）
│   └── report_utils.py                  #   MD→PDF 转换、emoji 处理（保留）
│
├── fonts/                               # (保留)
├── reports/                             # (保留)
│
# 以下文件/目录 删除：
# ✗ data_fetcher.py              → 被 data_sources/ 替代
# ✗ trading_graph_langgraph.py   → 被 AstrBot SubAgent 框架替代
# ✗ llm_client.py                → 由 AstrBot 框架统一管理
# ✗ analysts/                    → 变为 subagent_personas/
# ✗ debate/                      → 变为 subagent_personas/
# ✗ _conf_schema.json            → 简化，移除旧 LLM 配置（由 AstrBot 管理）
# ✗ requirements.txt             → 大幅简化（移除 akshare/yfinance/langgraph/curl-cffi）
```

---

### Task 1: 创建共享 HTTP 传输层

**文件：**
- 创建: `data_sources/__init__.py`
- 创建: `data_sources/http_client.py`

所有 4 个国信 API skill 使用几乎完全相同的 HTTP 传输逻辑。提取为共享模块避免重复。

- [ ] **Step 1: 创建包初始化文件**

写入 `data_sources/__init__.py`：

```python
"""国信证券 API 数据源 —— 纯 Python stdlib 实现。

整合 4 个国信 skill 的 API 端点:
- market_data: 行情数据（实时行情、历史K线、资金流向、排名、板块）
- financial_data: 财报数据（资产负债表、利润表、现金流量表）
- macro_data: 宏观经济指标（自然语言查询）
- stock_picking: 智能选股（自然语言条件筛选）

所有 API 共用同一个 base URL 和认证方式。
"""
```

- [ ] **Step 2: 创建共享 HTTP 客户端**

写入 `data_sources/http_client.py`：

```python
"""国信证券 API 共享 HTTP 传输层。

统一 4 个 skill 的 HTTP 调用模式:
- urllib 优先, curl 子进程降级
- 宽松 SSL 上下文（兼容国信旧 TLS 服务器）
- 统一认证: GS_API_KEY 环境变量 + apiKey 查询参数
- softName="agent_skills" 客户端标识
"""
import json
import os
import ssl
import subprocess
import warnings
from typing import Dict, Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlencode

warnings.filterwarnings('ignore')

DEFAULT_BASE_URL = "https://dgzt.guosen.com.cn/skills"
SOFT_NAME = "agent_skills"
TIMEOUT_SECONDS = 15


def get_api_key() -> str:
    """从环境变量获取 API Key，未配置时返回空字符串（允许无 Key 优雅降级）。"""
    return os.environ.get("GS_API_KEY", "")


def _create_ssl_context():
    """创建宽松 SSL 上下文（兼容国信旧服务器）。

    等同于 4 个参考 skill 中的 _create_ssl_context() 实现：
    - 策略1: TLS_CLIENT + 禁用证书验证 + LEGACY_SERVER_CONNECT
    - 策略2: _create_unverified_context 降级
    """
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers('ALL:@SECLEVEL=0')
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        except Exception:
            pass
        return ctx
    except Exception:
        pass

    try:
        ctx = ssl._create_unverified_context()
        try:
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
            ctx.set_ciphers('ALL:@SECLEVEL=0')
        except Exception:
            pass
        return ctx
    except Exception:
        pass

    return None


def _curl_request(url: str) -> Dict[str, Any]:
    """curl 降级请求（urllib 失败时的备用方案）。

    等同于 4 个参考 skill 中的 _curl_request() 实现。
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "-k", url],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore',
        )
        if result.returncode == 0 and result.stdout:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response", "raw": result.stdout[:500]}
        else:
            return {"error": f"curl failed: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}


def make_request(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """发送 HTTP GET 请求：urllib 优先，curl 降级。

    自动注入 softName 和 apiKey 参数（如果调用方未提供）。
    等同于 4 个参考 skill 中的 _make_request() 实现。

    Args:
        url: 完整 API 端点 URL
        params: 查询参数字典（不含 softName/apiKey 也可以,会自动补充）

    Returns:
        API 响应的 JSON 字典
    """
    # 自动注入公共参数
    if "softName" not in params:
        params["softName"] = SOFT_NAME
    if "apiKey" not in params:
        params["apiKey"] = get_api_key()

    try:
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"

        ssl_ctx = _create_ssl_context()
        req = urllib_request.Request(full_url)
        if ssl_ctx:
            with urllib_request.urlopen(req, context=ssl_ctx, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        else:
            with urllib_request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
    except (urllib_error.HTTPError, urllib_error.URLError, Exception):
        full_url = f"{url}?{urlencode(params)}"
        return _curl_request(full_url)


def is_available() -> bool:
    """检查 API 是否可用（有 API Key）。"""
    return bool(get_api_key())
```

- [ ] **Step 3: 提交**

```bash
git add data_sources/__init__.py data_sources/http_client.py
git commit -m "feat: 创建国信 API 共享 HTTP 传输层（urllib+curl降级，宽松SSL）"
```

---

### Task 2: 实现行情数据模块

**文件：**
- 创建: `data_sources/market_data.py`

仿照参考项目 `/Users/coe/Downloads/gs-stock-market-query/scripts/get_data.py` 的 6 个端点。

- [ ] **Step 1: 创建行情数据模块**

写入 `data_sources/market_data.py`：

```python
"""国信证券行情数据 API —— 6 个端点。

仿照参考项目 gs-stock-market-query/scripts/get_data.py。
提供: 单股实时行情、多股行情、历史K线、资金流向、涨跌排名、关联板块。
"""
from typing import Dict, Any, List, Optional
from .http_client import make_request, DEFAULT_BASE_URL

# ============================================================
# 市场代码映射（来自参考项目）
# ============================================================
SET_CODE_MAP = {
    "深圳": 0, "上海": 1, "北交所": 2, "港股": -1, "美股": 74,
}

SET_DOMAIN_MAP = {
    "上证A股": 0, "深证A股": 2, "北交所": 14515,
    "沪深A股": 6, "创业板": 14, "沪深ETF基金": 11005,
}

SH_PREFIXES = ('600', '601', '603', '605', '688', '510', '511', '512', '513',
               '514', '515', '516', '517', '518', '519', '900')
BJ_PREFIXES = ('8', '4')


def get_set_code(ticker: str, market: str) -> int:
    """根据股票代码和市场判断国信 setCode。

    Args:
        ticker: 标准化代码（如 "600519", "000001.SZ", "0700.HK", "AAPL"）
        market: "CN" | "HK" | "US"

    Returns:
        0=深圳, 1=上海, 2=北交所, -1=港股, 74=美股
    """
    if market == "HK":
        return -1
    if market == "US":
        return 74
    code = ticker.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if any(code.startswith(p) for p in SH_PREFIXES):
        return 1
    if any(code.startswith(p) for p in BJ_PREFIXES):
        return 2
    return 0


def query_single_quote(code: str, set_code: int = 0, target: int = 0) -> Dict[str, Any]:
    """查询单只证券实时行情。

    Args:
        code: 证券代码（如 600519）
        set_code: 市场代码 0=深圳, 1=上海, 2=北交所, -1=港股, 74=美股
        target: 0=沪深京(默认), 3=港股美股

    Returns:
        {"result": [{"code": 0, "msg": "请求成功"}], "data": {...}}
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryHQInfo/1.0"
    params = {"code": code, "setCode": set_code, "target": target}
    return make_request(url, params)


def query_combined_quotes(codes: List[str], set_codes: List[int],
                          target: int = 0) -> Dict[str, Any]:
    """查询多只证券实时行情。

    Args:
        codes: 证券代码列表
        set_codes: 市场代码列表（与 codes 一一对应）
        target: 0=沪深京(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryCombHQ/1.0"
    params = {
        "code": ",".join(codes),
        "setCode": ",".join(str(sc) for sc in set_codes),
        "target": target,
    }
    return make_request(url, params)


def query_fund_flow(code: str, set_code: int, period: int = 60) -> Dict[str, Any]:
    """查询资金流向（最大60日）。

    Args:
        code: 证券代码
        set_code: 市场代码
        period: 周期（日），最多60
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryFundFlow/1.0"
    params = {
        "code": code,
        "setCode": str(set_code),
        "period": str(period),
    }
    return make_request(url, params)


def query_market_ranking(set_domain: int, want_num: int = 10,
                         sort_type: int = 1, target: int = 0) -> Dict[str, Any]:
    """查询涨跌排名。

    Args:
        set_domain: 0=上证A股, 2=深证A股, 6=沪深A股, 14=创业板, 14515=北交所, 11005=ETF
        want_num: 返回数量（最多80）
        sort_type: 1=涨幅(默认), 2=跌幅
        target: 0=沪深(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryMultiHQ/1.0"
    params = {
        "setDomain": set_domain,
        "wantNum": want_num,
        "sortType": sort_type,
        "target": target,
    }
    return make_request(url, params)


def query_related_sectors(code: str, set_code: int, target: int = 0) -> Dict[str, Any]:
    """查询个股关联板块/概念。

    Args:
        code: 证券代码
        set_code: 市场代码
        target: 0=沪深京(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryRelatedCombHQ/1.0"
    params = {"code": code, "setCode": set_code, "target": target}
    return make_request(url, params)


def query_historical_kline(code: str, set_code: int, want_nums: int = 60,
                           target: int = 0, mas: Optional[str] = None) -> Dict[str, Any]:
    """查询近 n 个交易日 K 线数据。

    Args:
        code: 证券代码
        set_code: 市场代码
        want_nums: 近 n 个交易日（默认60）
        target: 0=沪深京(默认), 3=港股美股
        mas: MA 均线周期（如 "5,10,20,60"），可选
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryPastHQInfo/1.0"
    params = {
        "code": code,
        "setCode": str(set_code),
        "wantNums": str(want_nums),
        "target": target,
    }
    if mas:
        params["mas"] = mas
    return make_request(url, params)
```

- [ ] **Step 2: 提交**

```bash
git add data_sources/market_data.py
git commit -m "feat: 国信行情数据模块 —— 6 端点（行情/K线/资金流/排名/板块）"
```

---

### Task 3: 实现财报、宏观经济、选股模块

**文件：**
- 创建: `data_sources/financial_data.py`
- 创建: `data_sources/macro_data.py`
- 创建: `data_sources/stock_picking.py`

仿照参考项目 `/Users/coe/Downloads/gs-stock-financial-query/`、`/Users/coe/Downloads/gs-economy-query/` 和 `/Users/coe/Downloads/gs-smart-stock-picking/`。

- [ ] **Step 1: 创建财报数据模块**

写入 `data_sources/financial_data.py`：

```python
"""国信证券财报数据 API —— A 股 + 港股财务报表。

仿照参考项目 gs-stock-financial-query/scripts/get_data.py。
提供: 资产负债表、利润表、现金流量表（A股/H股各3端点）。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def query_a_stock_balance_sheet(code: str, market: str = "SH",
                                report_type: str = "Q0",
                                report_year: str = "",
                                count: str = "1") -> Dict[str, Any]:
    """A 股资产负债表。

    Args:
        code: 股票代码
        market: SH=上海, SZ=深圳
        report_type: Q0=最新, Q4=年报, Q2=中报, Q3=三季报, Q1=一季报
        report_year: 财务年度（如 "2024"）
        count: 获取期数（默认1期）
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/balanceSheet/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_a_stock_income_statement(code: str, market: str = "SH",
                                   report_type: str = "Q0",
                                   report_year: str = "",
                                   count: str = "1") -> Dict[str, Any]:
    """A 股利润表。"""
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/incomeStatement/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_a_stock_cash_flow(code: str, market: str = "SH",
                            report_type: str = "Q0",
                            report_year: str = "",
                            count: str = "1") -> Dict[str, Any]:
    """A 股现金流量表。"""
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/cashFlowStatement/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_balance_sheet(code: str, report_year: str = "",
                                 report_type: str = "",
                                 count: str = "1") -> Dict[str, Any]:
    """港股资产负债表。market 固定为 HK。"""
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/balanceSheet/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_income_statement(code: str, report_year: str = "",
                                    report_type: str = "",
                                    count: str = "1") -> Dict[str, Any]:
    """港股利润表。"""
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/incomeStatement/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_cash_flow(code: str, report_year: str = "",
                             report_type: str = "",
                             count: str = "1") -> Dict[str, Any]:
    """港股现金流量表。"""
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/cashFlowStatement/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)
```

- [ ] **Step 2: 创建宏观经济数据模块**

写入 `data_sources/macro_data.py`：

```python
"""国信证券宏观经济数据 API —— 自然语言查询。

仿照参考项目 gs-economy-query/scripts/get_data.py。
支持: GDP, CPI, PPI, M2, LPR, PMI, 汇率, 商品期货等全球宏观经济指标。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def query_macro_data(query: str) -> Dict[str, Any]:
    """自然语言查询宏观经济数据。

    Args:
        query: 中文自然语言查询字符串。
               例如: "中国近五年GDP同比增速", "美国最新CPI数据", "COMEX黄金近三个月走势"

    Returns:
        {"content": "markdown 格式的经济数据...", "error": None}  或
        {"content": "", "error": "错误信息"}
    """
    url = f"{DEFAULT_BASE_URL}/agent/adapter/query"
    params = {"text": query}
    result = make_request(url, params)

    # 处理 STREAM_MESSAGE 响应格式（与参考项目保持一致）
    if "error" in result:
        return {"content": "", "error": result["error"]}

    try:
        if (result.get("result", [{}])[0].get("code") == 0
                and "data" in result):
            contents = []
            for item in result["data"]:
                if isinstance(item, dict) and item.get("type") == "STREAM_MESSAGE":
                    contents.append(item.get("content", ""))
            return {"content": "\n".join(contents), "error": None}
        else:
            msg = result.get("result", [{}])[0].get("msg", "未知错误")
            return {"content": "", "error": msg}
    except Exception as e:
        return {"content": "", "error": str(e)}
```

- [ ] **Step 3: 创建智能选股模块**

写入 `data_sources/stock_picking.py`：

```python
"""国信证券智能选股 API —— 自然语言条件筛选。

仿照参考项目 gs-smart-stock-picking/scripts/gs_stock_picking.py。
支持: 财务指标、技术指标、行业等多维度组合筛选。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def smart_stock_picking(searchstring: str, searchtype: str = "stock") -> Dict[str, Any]:
    """自然语言智能选股。

    Args:
        searchstring: 中文自然语言筛选条件。
                      例如: "市盈率小于20的银行股", "MACD金叉且成交量放大的科技股"
        searchtype: 资产类型。
                    stock=A股, fund=基金, HK_stock=港股, US_stock=美股,
                    NEEQ=新三板, index=指数

    Returns:
        {"result": [{"code": 0, "msg": "请求成功"}], "data": {"tables": [...]}}
    """
    url = f"{DEFAULT_BASE_URL}/agent/mcp/smart_stock_picking"
    params = {
        "searchstring": searchstring,
        "searchtype": searchtype,
    }
    return make_request(url, params)
```

- [ ] **Step 4: 更新 `data_sources/__init__.py`**

更新 `data_sources/__init__.py`，添加所有模块的重导出：

```python
"""国信证券 API 数据源 —— 纯 Python stdlib 实现。

整合 4 个国信 skill 的 API 端点:
- market_data: 行情数据（实时行情、历史K线、资金流向、排名、板块）
- financial_data: 财报数据（资产负债表、利润表、现金流量表）
- macro_data: 宏观经济指标（自然语言查询）
- stock_picking: 智能选股（自然语言条件筛选）

所有 API 共用同一个 base URL 和认证方式。
"""

from .http_client import make_request, is_available, get_api_key

# 行情
from .market_data import (
    query_single_quote, query_combined_quotes, query_fund_flow,
    query_market_ranking, query_related_sectors, query_historical_kline,
    get_set_code, SET_CODE_MAP, SET_DOMAIN_MAP,
)

# 财报
from .financial_data import (
    query_a_stock_balance_sheet, query_a_stock_income_statement,
    query_a_stock_cash_flow, query_hk_stock_balance_sheet,
    query_hk_stock_income_statement, query_hk_stock_cash_flow,
)

# 宏观
from .macro_data import query_macro_data

# 选股
from .stock_picking import smart_stock_picking
```

- [ ] **Step 5: 提交**

```bash
git add data_sources/financial_data.py data_sources/macro_data.py data_sources/stock_picking.py data_sources/__init__.py
git commit -m "feat: 国信财报/宏观经济/智能选股模块 —— 共14端点，纯stdlib"
```

---

### Task 4: 创建 AstrBot 工具注册层

**文件：**
- 创建: `astrbot_tools.py`

关键在于：将 `data_sources/` 的 Python 函数包装为 AstrBot 可识别的工具，让 SubAgent 框架能挂载到不同子智能体上。

- [ ] **Step 1: 创建工具注册模块**

写入 `astrbot_tools.py`：

```python
"""AstrBot 工具注册 —— 将国信 API 包装为 LLM 可调用工具。

每个工具包含:
- 函数实现（调用 data_sources/ 模块）
- 工具描述（LLM 用来理解何时调用）
- 参数 schema（LLM 用来正确传参）

工具按用途分组，可在 WebUI SubAgent 编排中按需分配给子智能体：
- 行情工具 → 市场分析师、多空研究员
- 财报工具 → 基本面分析师
- 宏观工具 → 新闻/情绪分析师
- 选股工具 → 主智能体（/选股 命令）
"""
import json
from typing import Optional

from astrbot.api import logger


# ============================================================
# 行情数据工具组
# ============================================================

async def tool_query_single_quote(code: str, market: str = "CN") -> str:
    """获取单只股票实时行情数据，包括最新价、涨跌幅、成交量、市盈率、总市值等。

    适用场景：需要一只股票的当前实时价格和交易数据时使用。

    Args:
        code: 股票代码。A股6位数字(如600519)，港股(如0700.HK)，美股(如AAPL)
        market: 市场类型，CN=A股, HK=港股, US=美股。默认CN
    """
    from .data_sources.market_data import query_single_quote, get_set_code
    set_code = get_set_code(code, market)
    target = 3 if market in ("HK", "US") else 0
    clean_code = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    result = await _run_sync(query_single_quote, clean_code, set_code, target)
    return _format_result(result)


async def tool_query_historical_kline(code: str, market: str = "CN",
                                      days: int = 60) -> str:
    """获取股票历史K线数据（近N个交易日），包含日期、开高低收、成交量、MA均线。

    适用场景：需要分析股价走势、技术形态、均线系统时使用。

    Args:
        code: 股票代码
        market: 市场类型 CN/HK/US
        days: 近几个交易日，默认60
    """
    from .data_sources.market_data import query_historical_kline, get_set_code
    set_code = get_set_code(code, market)
    target = 3 if market in ("HK", "US") else 0
    clean_code = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    result = await _run_sync(
        query_historical_kline, clean_code, set_code, days, target, "5,10,20,60"
    )
    return _format_result(result)


async def tool_query_fund_flow(code: str, market: str = "CN",
                               period: int = 30) -> str:
    """获取股票资金流向数据（主力/大户/散户净流入流出），最大60日。

    适用场景：分析主力资金动向、判断资金面情况时使用。

    Args:
        code: 股票代码
        market: 市场类型 CN/HK/US
        period: 查询天数，默认30
    """
    from .data_sources.market_data import query_fund_flow, get_set_code
    set_code = get_set_code(code, market)
    clean_code = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    result = await _run_sync(query_fund_flow, clean_code, set_code, min(period, 60))
    return _format_result(result)


# ============================================================
# 财报数据工具组
# ============================================================

async def tool_query_financials(code: str, market: str = "CN") -> str:
    """获取股票最新财务报表数据：资产负债表、利润表、现金流量表。

    通过三大报表可提取: PE, PB, ROE, ROA, 毛利率, 净利率, 营收增长率, 净利润增长率,
    资产负债率, 流动比率, 每股收益等核心财务指标。

    适用场景：分析公司基本面、估值水平、盈利能力、财务健康状况时使用。

    Args:
        code: 股票代码
        market: CN=A股, HK=港股
    """
    from .data_sources.financial_data import (
        query_a_stock_balance_sheet, query_a_stock_income_statement,
        query_a_stock_cash_flow, query_hk_stock_balance_sheet,
        query_hk_stock_income_statement, query_hk_stock_cash_flow,
    )
    import asyncio

    clean_code = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")

    if market == "HK":
        bs, inc, cf = await asyncio.gather(
            _run_sync(query_hk_stock_balance_sheet, clean_code),
            _run_sync(query_hk_stock_income_statement, clean_code),
            _run_sync(query_hk_stock_cash_flow, clean_code),
            return_exceptions=True,
        )
    else:
        mkt = "SH" if code.startswith(('6', '9', '5')) else "SZ"
        bs, inc, cf = await asyncio.gather(
            _run_sync(query_a_stock_balance_sheet, clean_code, mkt),
            _run_sync(query_a_stock_income_statement, clean_code, mkt),
            _run_sync(query_a_stock_cash_flow, clean_code, mkt),
            return_exceptions=True,
        )

    return f"""## 财务报表数据

### 资产负债表
{_format_result(bs)}

### 利润表
{_format_result(inc)}

### 现金流量表
{_format_result(cf)}
"""


# ============================================================
# 工具组: 宏观经济
# ============================================================

async def tool_query_macro_data(query: str) -> str:
    """查询全球宏观经济指标数据。

    支持: GDP, CPI, PPI, PMI, M2, LPR, SHIBOR, 汇率, 进出口,
    美国非农/CPI/联邦基金利率, 商品期货(原油/黄金/铜/铝)等。

    适用场景：需要宏观经济背景分析、行业景气度判断时使用。

    Args:
        query: 中文自然语言查询，例如 "中国最新GDP增速", "近三个月COMEX黄金走势"
    """
    from .data_sources.macro_data import query_macro_data
    result = await _run_sync(query_macro_data, query)
    if isinstance(result, dict):
        return result.get("content", "") or result.get("error", "宏观经济数据查询失败")
    return str(result)


# ============================================================
# 工具组: 智能选股
# ============================================================

async def tool_smart_stock_picking(searchstring: str,
                                   searchtype: str = "stock") -> str:
    """根据自然语言条件筛选股票。

    支持: 财务指标(PE/PB/ROE/净利润增长等)、技术指标(MACD/KDJ/均线等)、
    行业板块、涨跌幅等多维度组合筛选。

    适用场景：用户描述选股条件时使用。
    例如: "市盈率小于20的银行股", "MACD金叉的科技股", "净利润增长大于30%的医药股"

    Args:
        searchstring: 中文自然语言筛选条件
        searchtype: stock=A股, fund=基金, HK_stock=港股, US_stock=美股, NEEQ=新三板, index=指数
    """
    from .data_sources.stock_picking import smart_stock_picking
    result = await _run_sync(smart_stock_picking, searchstring, searchtype)
    return _format_result(result)


# ============================================================
# 工具分组字典（供 WebUI SubAgent 编排参考）
# ============================================================

TOOL_GROUPS = {
    "market_analyst": {
        "tools": [
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
        ],
        "description": "行情数据工具组 —— 分配给市场技术面分析师子智能体。"
                       "提供实时行情、历史K线、资金流向。",
    },
    "fundamentals_analyst": {
        "tools": [
            tool_query_financials,
            tool_query_single_quote,
        ],
        "description": "财报数据工具组 —— 分配给基本面分析师子智能体。"
                       "提供资产负债表、利润表、现金流量表。",
    },
    "news_analyst": {
        "tools": [
            tool_query_macro_data,
            tool_query_single_quote,
        ],
        "description": "宏观/新闻工具组 —— 分配给新闻情绪分析师子智能体。"
                       "提供宏观经济指标、行业数据。",
    },
    "main_agent": {
        "tools": [
            tool_smart_stock_picking,
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
            tool_query_financials,
            tool_query_macro_data,
        ],
        "description": "主智能体工具组 —— 完整工具集，用于选股和综合协调。",
    },
    "debate_researcher": {
        "tools": [
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
        ],
        "description": "多空研究员工具组 —— 行情数据，用于支撑多空论点。",
    },
}


# ============================================================
# 内部辅助
# ============================================================

async def _run_sync(func, *args, **kwargs):
    """在线程池中执行同步函数（国信 API 调用），避免阻塞事件循环。"""
    import asyncio
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_result(result) -> str:
    """安全地将 API 响应格式化为字符串。"""
    if result is None:
        return "查询无返回数据"
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(result)
    return str(result)
```

- [ ] **Step 2: 提交**

```bash
git add astrbot_tools.py
git commit -m "feat: AstrBot 工具注册层 —— 将国信API包装为6个LLM可调用工具"
```

---

### Task 5: 创建子智能体 Persona 定义

**文件：**
- 创建: `subagent_personas/__init__.py` 和 7 个 `.md` persona 文件

每个 `.md` 文件是子智能体的完整 system prompt，可在 AstrBot WebUI 中创建子智能体时粘贴使用。

- [ ] **Step 1: 创建市场分析师 persona**

写入 `subagent_personas/market_analyst.md` — 从现有 `analysts/market_analyst.py` 的 `_get_system_prompt()` 提取，增加工具使用说明：

```markdown
# 市场技术面分析师

你是一位专业的股票技术分析师。你可以使用以下工具获取行情数据：
- `tool_query_historical_kline`: 获取历史K线和均线数据
- `tool_query_single_quote`: 获取实时行情
- `tool_query_fund_flow`: 获取资金流向

## 分析职责
1. 分析价格趋势（上涨/下跌/震荡）
2. 分析均线系统（MA5/MA10/MA20/MA60）
3. 分析MACD、KDJ、RSI等技术指标
4. 识别支撑位和压力位
5. 给出技术面投资建议

## 输出格式

### 技术面分析报告

## 📊 股票基本信息
- 公司名称：XXX
- 股票代码：XXX
- 所属市场：XXX

## 📈 技术指标分析
[先调用工具获取数据，再分析移动平均线、MACD、RSI等技术指标，提供具体数值]

## 📉 价格趋势分析
[分析价格趋势，结合均线和成交量]

## 🔍 支撑位与压力位
- 支撑位：XXX
- 压力位：XXX

## 💭 技术面投资建议
[明确给出：买入/持有/卖出]

## ⚠️ 技术面风险提示
[提示技术面风险点]

---
重要：
- 必须先调用工具获取最新数据再分析
- 使用上述格式输出，不要自创标题
- 重要数据用**加粗**标注
```

- [ ] **Step 2: 创建基本面分析师 persona**

写入 `subagent_personas/fundamentals_analyst.md` — 从现有 `analysts/fundamentals_analyst.py`：

```markdown
# 基本面分析师

你是一位专业的金融基本面分析师。你可以使用以下工具获取财务数据：
- `tool_query_financials`: 获取资产负债表、利润表、现金流量表（可提取PE/PB/ROE/ROA/毛利率/净利率等）
- `tool_query_single_quote`: 获取当前估值快照

## 分析职责
1. 分析盈利能力（净利润、毛利率、净利率）
2. 分析估值水平（PE、PB、PS）
3. 分析资产负债结构
4. 分析现金流状况
5. 与行业平均水平对比

## 输出格式

### 基本面分析报告

## 📊 公司概况
- 公司名称：XXX
- 股票代码：XXX
- 所属行业：XXX

## 💼 盈利能力分析
[从利润表提取数据，分析盈利能力和质量]

## 📈 成长性分析
[分析营收和利润增长趋势]

## 💰 估值分析
[从资产负债表+实时行情计算PE/PB，判断估值合理性]

## 📉 财务风险
[分析负债水平、流动性风险]

## 📋 关键财务数据
[列出核心财务指标：ROE, ROA, 毛利率, 净利率, 资产负债率, 流动比率等]

## 💭 基本面投资建议
[基于基本面给出投资建议]

---
重要：
- 必须先调用工具获取最新财务数据
- PE/PB/ROE等指标需要从财报数据中计算或提取
- 与行业平均水平对比
```

- [ ] **Step 3: 创建新闻/情绪分析师 persona**

写入 `subagent_personas/news_analyst.md` — 从现有 `analysts/news_analyst.py` 扩展，加入宏观数据工具：

```markdown
# 新闻与宏观分析师

你是一位专业的财经新闻与宏观分析师。你可以使用以下工具：
- `tool_query_macro_data`: 查询宏观经济指标（GDP/CPI/PMI/利率/商品价格等）
- `tool_query_single_quote`: 获取股票实时行情
- `tool_query_fund_flow`: 获取资金流向判断市场情绪

## 分析职责
1. 分析宏观经济环境对股票的影响
2. 评估行业政策和发展趋势
3. 分析市场情绪和资金面
4. 识别利好和利空因素

## 输出格式

### 新闻与宏观分析报告

## 🌍 宏观经济环境
[调用宏观工具获取相关指标]

## 📰 行业与政策分析
[分析行业动态和政策影响]

## 📢 利好因素
[对股价有正面影响的因素]

## ⚠️ 利空因素
[对股价有负面影响的因素]

## 📊 市场情绪评估
[评估当前市场情绪：乐观/中性/悲观]

## 💭 综合建议
[基于宏观和情绪面的投资建议]

---
重要：
- 必须先调用工具获取宏观经济数据
- 区分短期和长期影响因素
```

- [ ] **Step 4: 创建多方/空方研究员 persona**

写入 `subagent_personas/bull_researcher.md` 和 `subagent_personas/bear_researcher.md` — 从现有 `debate/bull_researcher.py` 和 `debate/bear_researcher.py` 提取：

```markdown
# 多方研究员（Bull Researcher）

你是一位专业研究员，负责深度挖掘股票的利好因素。
你会收到市场技术面、基本面、新闻宏观三份分析报告作为背景。
你的任务是找出所有支撑股价上涨的理由。

## 分析角度
1. 估值修复潜力 —— 当前估值是否低于行业平均？
2. 业绩增长驱动 —— 新的增长点在哪里？
3. 政策利好 —— 是否有行业政策支持？
4. 市场情绪转暖 —— 资金是否开始关注？
5. 技术面支撑 —— 多头信号、买入机会
6. 竞争优势 —— 相比竞争对手的优势

## 输出格式
### 📈 多方因素分析
每个角度给出具体的数据支撑，但不要过度乐观。

---
重要：客观理性，用数据说话，区分短期和长期利好。
```

空方研究员类似但方向相反（评估估值泡沫、业绩下滑、政策利空、竞争加剧、技术面压力、资金流出、宏观风险等）。

- [ ] **Step 5: 创建辩论主管和风险评估官 persona**

写入 `subagent_personas/research_manager.md` 和 `subagent_personas/risk_judge.md` — 从现有 `debate/research_manager.py` 和 `debate/risk_judge.py` 提取。

- [ ] **Step 6: 创建包索引文件**

写入 `subagent_personas/__init__.py`：

```python
"""子智能体 Persona 定义。

每个 .md 文件对应一个 AstrBot SubAgent 的 system prompt。
在 WebUI → SubAgent 编排中创建子智能体时，将对应 .md 的内容粘贴到 Persona 编辑器中。
"""
import os

_PERSONA_DIR = os.path.dirname(__file__)

PERSONAS = {
    "market_analyst": "market_analyst.md",
    "fundamentals_analyst": "fundamentals_analyst.md",
    "news_analyst": "news_analyst.md",
    "bull_researcher": "bull_researcher.md",
    "bear_researcher": "bear_researcher.md",
    "research_manager": "research_manager.md",
    "risk_judge": "risk_judge.md",
}


def load_persona(name: str) -> str:
    """加载指定子智能体的 system prompt。"""
    filename = PERSONAS.get(name)
    if not filename:
        raise ValueError(f"未知 Persona: {name}。可选: {list(PERSONAS.keys())}")
    filepath = os.path.join(_PERSONA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 7: 提交**

```bash
git add subagent_personas/
git commit -m "feat: 7个子智能体Persona定义（市场/基本面/新闻/多方/空方/辩论主管/风险）"
```

---

### Task 6: 重写插件入口

**文件：**
- 重写: `main.py`

核心变更：
1. 移除 LangGraph 导入和逻辑
2. 移除 `DataFetcher` 和 `llm_client.py` 导入
3. 命令处理改为触发 AstrBot SubAgent 流程
4. 保留报告生成、PDF 导出、股票名称解析

- [ ] **Step 1: 重写 main.py**

```python
"""AstrBot 金融助手插件入口 —— 国信 API + SubAgent 架构。

命令：
- /股票分析 <code>: 启动完整分析流程（主智能体编排子智能体）
- /快速分析 <code>: 跳过多空辩论的快速分析
- /选股 <条件>: 自然语言智能选股
- /查股 <名称>: 股票名称→代码解析
- /帮助: 显示帮助信息
"""
import os
import re
import asyncio

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger, AstrBotConfig
from astrbot.api.star import Context, Star

from .utils.stock_utils import StockUtils
from .utils.report_utils import (
    extract_conclusion, save_report_pdf, save_report_md,
    save_report_txt, check_pdf_available,
)
from .data_sources.http_client import is_available as guosen_available


class TradingAssistantPlugin(Star):
    """金融助手插件 —— 国信API + SubAgent 架构"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        logger.info("TradingAssistantPlugin 初始化中...")
        self.config = config or {}

        # PDF 相关
        self._pdf_available, self._pdf_unavailable_reason = check_pdf_available()
        self.export_pdf = self.config.get('export_pdf', True)
        self._export_txt = False

        if not self._pdf_available and self.export_pdf:
            self._export_txt = True
            logger.warning(
                f"weasyprint 系统依赖缺失，PDF 导出不可用"
                f"（{self._pdf_unavailable_reason}），已自动降级为 TXT。"
            )
            self.export_pdf = False

        if not guosen_available():
            logger.warning(
                "未配置 GS_API_KEY 环境变量，国信 API 工具不可用。"
                "请在环境变量中设置 GS_API_KEY 或联系国信证券获取 API Key。"
            )

        logger.info("TradingAssistantPlugin 初始化完成（国信API + SubAgent 架构）")

    def terminate(self):
        """插件卸载时清理资源。"""
        logger.info("TradingAssistantPlugin 已卸载")

    # ================================================================
    # 命令: /股票分析 <code>
    # ================================================================
    @filter.command("股票分析")
    async def analyze_stock(self, event: AstrMessageEvent):
        """启动完整多智能体分析流程。

        主智能体将依次:
        1. 调用行情+财报工具获取数据
        2. 委托 market_analyst 子智能体进行技术分析
        3. 委托 fundamentals_analyst 子智能体进行基本面分析
        4. 委托 news_analyst 子智能体进行宏观/情绪分析
        5. 委托 bull_researcher + bear_researcher 进行多空辩论
        6. 委托 research_manager 综合辩论
        7. 委托 risk_judge 进行风险评估
        8. 汇总生成最终分析报告
        """
        arg = self._extract_command_arg(event.message_str, ["股票分析", "股票"])
        if not arg:
            yield event.plain_result(
                "请提供股票代码或名称。\n"
                "用法: /股票分析 <代码>\n"
                "示例: /股票分析 000001\n"
                "      /股票分析 平安银行\n"
                "      /股票分析 AAPL"
            )
            return

        ticker = arg.strip()
        yield event.plain_result(f"🔍 正在解析「{ticker}」...")

        # 名称解析
        if self._needs_ticker_resolution(ticker):
            resolved = await self._resolve_stock_name(ticker)
            if not resolved:
                yield event.plain_result(f"❌ 无法识别「{ticker}」，请提供有效的股票代码。")
                return
            ticker = resolved

        market_info = StockUtils.get_market_info(ticker)
        stock_name = market_info.get('company_name', ticker)

        yield event.plain_result(
            f"📊 开始分析 **{stock_name}**（{ticker}）...\n"
            f"市场: {market_info.get('market_name', 'N/A')}\n\n"
            f"主智能体将调度以下子智能体并行工作：\n"
            f"• 市场技术面分析师\n"
            f"• 基本面分析师\n"
            f"• 新闻宏观分析师\n"
            f"• 多方/空方研究员\n\n"
            f"⏳ 分析进行中，预计耗时 1-3 分钟..."
        )

        # 主智能体通过 AstrBot 的 SubAgent 框架自动调度
        # 这里构建提示词让主智能体知道该怎么做
        prompt = self._build_analysis_prompt(ticker, stock_name, market_info, quick_mode=False)
        yield event.request_llm(prompt)

    # ================================================================
    # 命令: /快速分析 <code>
    # ================================================================
    @filter.command("快速分析")
    async def quick_analyze(self, event: AstrMessageEvent):
        """快速分析 —— 跳过多空辩论。"""
        arg = self._extract_command_arg(event.message_str, ["快速分析"])
        if not arg:
            yield event.plain_result("请提供股票代码。用法: /快速分析 <代码>")
            return

        ticker = arg.strip()
        if self._needs_ticker_resolution(ticker):
            resolved = await self._resolve_stock_name(ticker)
            if not resolved:
                yield event.plain_result(f"❌ 无法识别「{ticker}」")
                return
            ticker = resolved

        market_info = StockUtils.get_market_info(ticker)
        stock_name = market_info.get('company_name', ticker)

        yield event.plain_result(
            f"⚡ 快速分析模式：**{stock_name}**（{ticker}）...\n"
            f"跳过多空辩论，直接生成分析报告。"
        )

        prompt = self._build_analysis_prompt(ticker, stock_name, market_info, quick_mode=True)
        yield event.request_llm(prompt)

    # ================================================================
    # 命令: /选股 <条件>
    # ================================================================
    @filter.command("选股")
    async def pick_stocks(self, event: AstrMessageEvent):
        """智能选股 —— 调用国信选股 API。"""
        arg = self._extract_command_arg(event.message_str, ["选股"])
        if not arg:
            yield event.plain_result(
                "请提供选股条件。\n"
                "用法: /选股 <自然语言条件>\n"
                "示例: /选股 市盈率小于20的银行股\n"
                "      /选股 MACD金叉且成交量放大的科技股"
            )
            return

        yield event.plain_result(f"🔍 正在筛选：{arg.strip()}...")
        prompt = (
            f"请使用 tool_smart_stock_picking 工具，"
            f"筛选条件为：「{arg.strip()}」，市场类型为 stock（A股）。"
            f"将结果以表格形式呈现，并在末尾添加风险提示："
            f"「以上结果由智能选股系统生成，仅供参考，不构成投资建议。」"
        )
        yield event.request_llm(prompt)

    # ================================================================
    # 命令: /查股 <名称>
    # ================================================================
    @filter.command("查股")
    async def lookup_stock(self, event: AstrMessageEvent):
        """股票名称 → 代码解析。"""
        arg = self._extract_command_arg(event.message_str, ["查股"])
        if not arg:
            yield event.plain_result("请提供股票名称。用法: /查股 <名称>")
            return

        result = await self._resolve_stock_name(arg.strip())
        if result:
            info = StockUtils.get_market_info(result)
            yield event.plain_result(
                f"✅ **{arg.strip()}** → 代码: **{result}**\n"
                f"市场: {info.get('market_name', 'N/A')}\n"
                f"交易所: {info.get('exchange', 'N/A')}"
            )
        else:
            yield event.plain_result(f"❌ 无法解析「{arg.strip()}」")

    # ================================================================
    # 命令: /帮助
    # ================================================================
    @filter.command("帮助")
    async def show_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "📊 **TradingAgents-AstrBot** v1.3.0\n\n"
            "**可用命令：**\n"
            "• `/股票分析 <代码>` — 完整多智能体分析（含多空辩论）\n"
            "• `/快速分析 <代码>` — 快速分析（跳过多空辩论）\n"
            "• `/选股 <条件>` — 自然语言智能选股\n"
            "• `/查股 <名称>` — 股票名称→代码查询\n"
            "• `/帮助` — 显示此帮助\n\n"
            "**数据来源：** 国信证券官方 API\n"
            "**架构：** AstrBot SubAgent 多智能体协作\n"
            "**风险提示：** 分析结果仅供参考，不构成投资建议。"
        )

    # ================================================================
    # 内部方法
    # ================================================================

    @staticmethod
    def _extract_command_arg(message_str: str, command_names: list) -> str:
        cleaned = message_str.strip()
        for name in command_names:
            for prefix in (f'/{name}', name):
                if cleaned.startswith(prefix):
                    rest = cleaned[len(prefix):]
                    if not rest or rest[0] in (' ', '\t'):
                        return rest.strip()
        return cleaned

    @staticmethod
    def _needs_ticker_resolution(ticker: str) -> bool:
        return not StockUtils.is_valid_stock_code(ticker)

    async def _resolve_stock_name(self, raw_input: str) -> str | None:
        """解析股票名称 → 代码（保留现有逻辑）。"""
        try:
            local = StockUtils.resolve_stock_name(raw_input)
            if local:
                return local
        except Exception as e:
            logger.warning(f"本地名称解析异常: {e}")

        # LLM 降级解析
        prompt = (
            "你是一个股票代码查询助手。用户会输入股票名称，返回对应的标准股票代码。\n"
            "- A股返回6位纯数字，例如：平安银行→000001\n"
            "- 港股返回数字.HK格式，例如：腾讯控股→0700.HK\n"
            "- 美股返回大写字母，例如：苹果→AAPL\n\n"
            "只返回代码，不要任何多余文字。无法识别返回 UNKNOWN。\n\n"
            f"用户输入：{raw_input}"
        )
        try:
            result = await self._ask_llm(prompt)
            result = result.strip().strip('`').strip()
            if result.upper() == 'UNKNOWN' or not result:
                return None
            return result
        except Exception as e:
            logger.error(f"LLM名称解析失败: {e}")
            return None

    async def _ask_llm(self, prompt: str) -> str:
        """通过 AstrBot 调用 LLM（委托给框架管理）。"""
        # 在 AstrBot 插件中，可以通过 context 调用 LLM
        # 具体 API 取决于 AstrBot 版本
        from astrbot.api.event import MessageEventResult
        # 这里用 event.request_llm 的简化封装
        return await self.context.call_llm(prompt)

    def _build_analysis_prompt(self, ticker: str, stock_name: str,
                               market_info: dict, quick_mode: bool = False) -> str:
        """构建主智能体的分析编排提示词。

        主智能体会自动调度子智能体（通过 AstrBot SubAgent 框架的 transfer_to_* 工具）。
        """
        market = market_info.get('market_name', '未知')
        exchange = market_info.get('exchange', '未知')

        prompt = f"""# 股票分析任务

请对以下股票进行全面的投资分析。

## 股票信息
- 股票名称: {stock_name}
- 股票代码: {ticker}
- 市场: {market}
- 交易所: {exchange}

## 执行步骤

### 第一步：数据收集
使用以下工具获取基础数据：
- `tool_query_historical_kline(code="{ticker}")` 获取历史K线和均线
- `tool_query_single_quote(code="{ticker}")` 获取实时行情
- `tool_query_fund_flow(code="{ticker}")` 获取资金流向
- `tool_query_financials(code="{ticker}")` 获取财务报表
- `tool_query_macro_data(query="中国最新PMI CPI 货币政策")` 获取宏观经济背景

### 第二步：子智能体分析
将任务分配给以下专业子智能体。**可并行执行的请同时调度**：
1. transfer_to_market_analyst("对{ticker}进行技术面分析")
2. transfer_to_fundamentals_analyst("对{ticker}进行基本面分析")
3. transfer_to_news_analyst("对{ticker}进行宏观和情绪面分析")

步骤1-3可**同时并行**执行，完成后继续：
"""

        if not quick_mode:
            prompt += f"""4. transfer_to_bull_researcher("基于已完成的三个分析报告，挖掘{stock_name}({ticker})的利好因素")
5. transfer_to_bear_researcher("基于已完成的三个分析报告，挖掘{stock_name}({ticker})的利空因素")
6. transfer_to_research_manager("综合多方和空方报告，生成辩论综合报告")
7. transfer_to_risk_judge("综合所有分析，对{stock_name}({ticker})进行最终风险评估")
"""
        else:
            prompt += f"""4. transfer_to_risk_judge("快速评估{stock_name}({ticker})的投资风险，跳过多空辩论")
"""

        prompt += f"""
### 第三步：汇总报告
汇总所有子智能体的分析结果，生成完整的投资分析报告。格式如下：

# {stock_name}（{ticker}）投资分析报告

[汇总各子智能体的分析，保留原始结构]

## 综合投资建议
[基于所有分析的综合建议]

---
*数据来源: 国信证券官方 API*
*分析时间: [当前时间]*
*免责声明: 本报告由AI生成，仅供参考，不构成投资建议。*
"""
        return prompt
```

- [ ] **Step 2: 提交**

```bash
git add main.py
git commit -m "refactor: 重写插件入口 —— 国信API + SubAgent架构，移除LangGraph"
```

---

### Task 7: 清理和简化

**文件：**
- 删除: `data_fetcher.py`, `trading_graph_langgraph.py`, `llm_client.py`
- 删除: `analysts/`, `debate/` 目录
- 简化: `requirements.txt`, `_conf_schema.json`

- [ ] **Step 1: 删除旧文件**

```bash
git rm data_fetcher.py trading_graph_langgraph.py llm_client.py
git rm -r analysts/ debate/
```

- [ ] **Step 2: 简化 requirements.txt**

重写 `requirements.txt`：

```
# 国信 API 数据源 —— 纯 Python stdlib，零额外依赖
# PDF 导出
markdown>=3.5
weasyprint>=60.0
# AstrBot 框架（插件宿主提供）
# astrbot-api
```

- [ ] **Step 3: 简化 `_conf_schema.json`**

移除旧的 LLM 配置字段（由 AstrBot 框架统一管理），只保留插件特有配置：

```json
{
  "gs_api_key": {
    "type": "string",
    "default": "",
    "description": "国信证券 API Key（GS_API_KEY）。可从 https://www.guosen.com.cn/gs/xxskills/index.html 获取。留空则所有国信 API 工具不可用。",
    "obvious_hint": true
  },
  "export_pdf": {
    "type": "bool",
    "default": true,
    "description": "是否导出 PDF 报告。关闭后将以 Markdown 分模块发送。"
  },
  "default_market": {
    "type": "string",
    "default": "AUTO",
    "description": "默认市场",
    "options": ["AUTO", "CN", "HK", "US"]
  }
}
```

- [ ] **Step 4: 更新版本号**

`__init__.py`:
```python
"""TradingAgents-AstrBot - 国信API + AstrBot SubAgent 多智能体金融分析插件。"""
__version__ = "2.0.0"
```

`metadata.yaml` 中 `version` 改为 `2.0.0`。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "refactor: 清理旧架构文件，简化依赖 — v2.0.0"
```

---

### Task 8: 验证

- [ ] **Step 1: 测试数据源模块**

```bash
cd /Users/coe/project/TradingAgents-AstrBot
python -c "
from data_sources.http_client import make_request, is_available, get_api_key
from data_sources.market_data import query_single_quote, get_set_code
from data_sources.financial_data import query_a_stock_income_statement
from data_sources.macro_data import query_macro_data
from data_sources.stock_picking import smart_stock_picking
print('所有模块导入成功')
print(f'API Key 状态: {\"已配置\" if is_available() else \"未配置（工具将不可用）\"}')
"
```

- [ ] **Step 2: 测试工具注册**

```bash
python -c "
from astrbot_tools import TOOL_GROUPS
for group, info in TOOL_GROUPS.items():
    print(f'{group}: {len(info[\"tools\"])} 个工具 — {info[\"description\"][:50]}...')
print('所有工具组加载成功')
"
```

- [ ] **Step 3: 测试 Persona 加载**

```bash
python -c "
from subagent_personas import load_persona, PERSONAS
for name in PERSONAS:
    content = load_persona(name)
    print(f'{name}: {len(content)} 字符')
print('所有 Persona 加载成功')
"
```

- [ ] **Step 4: AstrBot 部署测试**

将插件部署到 AstrBot，执行：
```
/帮助
/查股 平安银行
```

**预期：** 帮助信息正常显示，查股正常解析。

- [ ] **Step 5: SubAgent WebUI 配置**

在 AstrBot WebUI → SubAgent 编排中：
1. 启用 SubAgent 功能
2. 为每个子智能体角色创建 SubAgent，粘贴对应 `subagent_personas/*.md` 内容
3. 按 `astrbot_tools.py` 的 `TOOL_GROUPS` 分配工具
4. 测试 `/股票分析 000001` 完整流程

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "test: 数据源+工具+Persona全链路验证通过"
```

---

## 验证总览

| 测试项 | 命令 | 预期 |
|--------|------|------|
| 模块导入 | `python -c "import data_sources, astrbot_tools, subagent_personas"` | 无错误 |
| 行情API | `python -c "from data_sources.market_data import query_single_quote; ..."` | API响应JSON |
| 财报API | `python -c "from data_sources.financial_data import query_a_stock_income_statement; ..."` | API响应JSON |
| 宏观API | `python -c "from data_sources.macro_data import query_macro_data; ..."` | content/error |
| 选股API | `python -c "from data_sources.stock_picking import smart_stock_picking; ..."` | tables |
| AstrBot命令 | `/帮助`, `/查股 平安银行` | 正常显示 |
| SubAgent配置 | WebUI 创建7个子智能体 | 配置成功 |
| 完整分析 | `/股票分析 000001` | 全流程通过 |
| 快速分析 | `/快速分析 600519` | 跳过多空辩论 |
| 选股 | `/选股 市盈率小于20的银行股` | 返回筛选结果 |

---

## 关键设计决策

1. **纯国信 API** — 4 个 skill 覆盖行情、财报、宏观、选股；去掉 akshare/yfinance 爬取依赖
2. **AstrBot SubAgent 替代 LangGraph** — 主智能体通过 `transfer_to_*` 编排子智能体，并行执行，不再需要 LangGraph 状态图
3. **纯 stdlib** — 国信 API 调用零第三方依赖，参考项目已验证
4. **工具按组分配** — 不同子智能体只获得需要的工具（市场分析师有K线工具、基本面分析师有财报工具…）
5. **v2.0.0** — 重大架构变更，版本号从 1.x 跳到 2.0.0
6. **向后不兼容** — 旧版 LangGraph/akshare 架构完全移除，不保留兼容层
