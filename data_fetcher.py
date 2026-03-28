"""统一数据获取模块。"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger("data_fetcher")


class DataFetcher:
    """统一数据获取器"""
    
    def __init__(self):
        self._akshare_available = None
        self._yfinance_available = None
        self._initialized = False
        # 初始化curl_cffi补丁（仅执行一次）
        self._initialize_akshare()

    async def _run_blocking(self, func, *args, timeout: int = 30, **kwargs):
        """在线程池中执行阻塞调用并添加超时控制。"""
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs),
            timeout=timeout,
        )
    
    def _initialize_akshare(self):
        """
        初始化AKShare连接 - 使用curl_cffi绕过反爬虫
        复刻 TradingAgents-CN-fixed 的实现
        """
        if self._initialized:
            return
            
        try:
            import requests
            import time

            # 尝试导入 curl_cffi，如果可用则使用它来绕过反爬虫
            try:
                from curl_cffi import requests as curl_requests
                use_curl_cffi = True
                logger.info("🔧 检测到 curl_cffi，将使用它来模拟真实浏览器 TLS 指纹")
            except ImportError:
                use_curl_cffi = False
                logger.warning("⚠️ curl_cffi 未安装，将使用标准 requests（可能被反爬虫拦截）")
                logger.warning("   建议安装: pip install curl-cffi")

            # 修复AKShare的bug：设置requests的默认headers，并添加请求延迟
            if not hasattr(requests, '_akshare_headers_patched'):
                original_get = requests.get
                last_request_time = {'time': 0}

                def patched_get(url, **kwargs):
                    """
                    包装requests.get方法，自动添加必要的headers和请求延迟
                    如果可用，使用 curl_cffi 模拟真实浏览器 TLS 指纹
                    """
                    # 添加请求延迟，避免被反爬虫封禁
                    if 'eastmoney.com' in url:
                        current_time = time.time()
                        time_since_last_request = current_time - last_request_time['time']
                        if time_since_last_request < 0.5:
                            time.sleep(0.5 - time_since_last_request)
                        last_request_time['time'] = time.time()

                    # 如果是东方财富网的请求，且 curl_cffi 可用，使用它来绕过反爬虫
                    if use_curl_cffi and 'eastmoney.com' in url:
                        try:
                            curl_kwargs = {
                                'timeout': kwargs.get('timeout', 10),
                                'impersonate': "chrome120"
                            }
                            if 'params' in kwargs:
                                curl_kwargs['params'] = kwargs['params']
                            if 'data' in kwargs:
                                curl_kwargs['data'] = kwargs['data']
                            if 'json' in kwargs:
                                curl_kwargs['json'] = kwargs['json']

                            response = curl_requests.get(url, **curl_kwargs)
                            return response
                        except Exception as e:
                            error_msg = str(e)
                            if 'invalid library' not in error_msg and '400' not in error_msg:
                                logger.warning(f"⚠️ curl_cffi 请求失败，回退到标准 requests: {e}")

                    # 标准 requests 请求
                    if 'headers' not in kwargs or kwargs['headers'] is None:
                        kwargs['headers'] = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Referer': 'https://www.eastmoney.com/',
                            'Connection': 'keep-alive',
                        }
                    elif isinstance(kwargs['headers'], dict):
                        if 'User-Agent' not in kwargs['headers']:
                            kwargs['headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        if 'Referer' not in kwargs['headers']:
                            kwargs['headers']['Referer'] = 'https://www.eastmoney.com/'
                        if 'Accept' not in kwargs['headers']:
                            kwargs['headers']['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                        if 'Accept-Language' not in kwargs['headers']:
                            kwargs['headers']['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'

                    return original_get(url, **kwargs)

                requests.get = patched_get
                requests._akshare_headers_patched = True

                if use_curl_cffi:
                    logger.info("🔧 已修复AKShare的headers问题，使用 curl_cffi 模拟真实浏览器（Chrome 120）")
                else:
                    logger.info("🔧 已修复AKShare的headers问题，并添加请求延迟（0.5秒）")

            self._initialized = True
            logger.info("✅ AKShare 初始化完成")

        except Exception as e:
            logger.error(f"❌ AKShare初始化失败: {e}")
            self._initialized = True  # 标记已尝试初始化，避免重复
    
    @property
    def akshare_available(self) -> bool:
        """检查akshare是否可用"""
        if self._akshare_available is None:
            try:
                import akshare
                self._akshare_available = True
                logger.info("akshare 已可用")
            except ImportError:
                self._akshare_available = False
                logger.warning("akshare 未安装")
        return self._akshare_available
    
    @property
    def yfinance_available(self) -> bool:
        """检查yfinance是否可用"""
        if self._yfinance_available is None:
            try:
                import yfinance
                self._yfinance_available = True
                logger.info("yfinance 已可用")
            except ImportError:
                self._yfinance_available = False
                logger.warning("yfinance 未安装")
        return self._yfinance_available
    
    async def get_market_data(self, ticker: str, trade_date: str) -> str:
        """
        获取市场数据 - 复刻 get_stock_market_data_unified
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期 YYYY-MM-DD
            
        Returns:
            格式化的市场数据文本
        """
        from .utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        try:
            if market_info['is_china']:
                return await self._get_china_market_data(ticker, trade_date, market_info)
            elif market_info['is_hk']:
                return await self._get_hk_market_data(ticker, trade_date, market_info)
            else:
                return await self._get_us_market_data(ticker, trade_date, market_info)
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return f"获取市场数据失败: {str(e)}"
    
    async def _get_china_market_data(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取A股市场数据（带重试机制）"""
        if not self.akshare_available:
            return "akshare未安装，无法获取A股数据"
        
        from .utils.stock_utils import StockUtils
        import asyncio
        
        try:
            import akshare as ak
            import pandas as pd
            
            code = StockUtils.strip_market_prefix(ticker)
            
            end_date = datetime.strptime(trade_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=30)
            
            # 重试机制 - 最多尝试3次
            df = None
            last_error = None
            
            for attempt in range(3):
                try:
                    logger.info(f"尝试获取A股数据 (尝试 {attempt + 1}/3): {code}")
                    # 使用 to_thread 在线程池中执行同步代码，避免阻塞事件循环
                    df = await self._run_blocking(
                        ak.stock_zh_a_hist,
                        symbol=code,
                        period="daily",
                        start_date=start_date.strftime('%Y%m%d'),
                        end_date=end_date.strftime('%Y%m%d'),
                        adjust="qfq",
                        timeout=30,
                    )
                    if df is not None and not df.empty:
                        logger.info(f"成功获取A股数据: {code}")
                        break
                except asyncio.TimeoutError:
                    last_error = "获取数据超时"
                    logger.warning(f"尝试 {attempt + 1} 超时")
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"尝试 {attempt + 1} 失败: {e}")
                
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            
            if df is None or df.empty:
                return f"""## A股市场数据

**股票代码**: {code}
**交易日期**: {trade_date}
**市场**: {market_info['market_name']}
**状态**: 数据获取失败

### 提示
无法从数据源获取{code}的行情数据。
原因: {last_error or '未知错误'}

**建议**: 
1. 检查网络连接
2. 稍后重试
3. 股票代码可能不存在或已停牌

---
*数据来源: akshare*"""
            
            # 获取最新数据
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # 计算涨跌
            price_change = latest['收盘'] - prev['收盘']
            pct_change = (price_change / prev['收盘'] * 100) if prev['收盘'] != 0 else 0
            
            result = f"""## A股市场数据

**股票代码**: {code}
**交易日期**: {trade_date}
**市场**: {market_info['market_name']}
**交易所**: {market_info['exchange']}
**货币**: {market_info['currency_name']}（{market_info['currency_symbol']}）

### 近期行情
| 日期 | 开盘 | 收盘 | 最高 | 最低 | 成交量 | 成交额 | 涨跌幅 |
|------|------|------|------|------|--------|--------|--------|
| {latest['日期']} | {latest['开盘']} | {latest['收盘']} | {latest['最高']} | {latest['最低']} | {latest['成交量']} | {latest['成交额']} | {pct_change:.2f}% |

### 最近5个交易日
"""
            
            for idx, row in df.tail(5).iterrows():
                result += f"- **{row['日期']}**: 收{row['收盘']} ({row['涨跌幅']:+.2f}%)\n"
            
            # 获取实时行情（带重试）
            try:
                spot_df = await self._run_blocking(ak.stock_zh_a_spot_em, timeout=15)
                spot_result = spot_df[spot_df['代码'] == code]
                if not spot_result.empty:
                    s = spot_result.iloc[0]
                    result += f"""
### 实时行情
| 指标 | 数值 |
|------|------|
| 最新价 | {s.get('最新价', 'N/A')} |
| 涨跌额 | {s.get('涨跌额', 'N/A')} |
| 涨跌幅 | {s.get('涨跌幅', 'N/A')}% |
| 成交量 | {s.get('成交量', 'N/A')} |
| 成交额 | {s.get('成交额', 'N/A')} |
| 最高 | {s.get('最高', 'N/A')} |
| 最低 | {s.get('最低', 'N/A')} |
| 今开 | {s.get('今开', 'N/A')} |
| 昨收 | {s.get('昨收', 'N/A')} |
| 市盈率(动态) | {s.get('市盈率-动态', 'N/A')} |
| 市净率 | {s.get('市净率', 'N/A')} |
| 总市值 | {s.get('总市值', 'N/A')} |
| 流通市值 | {s.get('流通市值', 'N/A')} |
"""
            except Exception as e:
                logger.warning(f"获取实时行情失败: {e}")
            
            return result
            
        except ImportError:
            return "akshare未安装，请运行: pip install akshare"
        except Exception as e:
            return f"获取A股数据失败: {str(e)}"
    
    def _pad_hk_code(self, code: str) -> str:
        """将港股代码补零到5位（akshare stock_hk_hist 需要）。
        例如: '0700' -> '00700', '9988' -> '09988', '00700' -> '00700'
        """
        code = code.lstrip('0') if code.startswith('0') and len(code) > 4 else code
        return code.zfill(5)
    
    async def _get_hk_market_data(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取港股市场数据（akshare实时行情 + 历史K线）"""
        if not self.akshare_available:
            return "akshare未安装，无法获取港股数据"
        
        try:
            import akshare as ak
            import pandas as pd
            
            # 提取纯数字代码（0700.HK → 0700）
            code = ticker.replace('.HK', '').replace('HK', '').replace('.', '')
            # akshare stock_hk_spot_em 使用原始代码（如 0700）
            # akshare stock_hk_hist 需要5位补零代码（如 00700）
            padded_code = self._pad_hk_code(code)
            
            # === 1. 获取实时行情 ===
            realtime_text = ""
            try:
                spot_df = await self._run_blocking(ak.stock_hk_spot_em, timeout=30)
                spot_result = spot_df[spot_df['代码'] == code]
                
                if spot_result is None or spot_result.empty:
                    # 尝试用补零代码匹配
                    spot_result = spot_df[spot_df['代码'] == padded_code]
                
                if spot_result is not None and not spot_result.empty:
                    row = spot_result.iloc[0]
                    realtime_text = f"""### 实时行情
| 指标 | 数值 |
|------|------|
| 股票名称 | {row.get('名称', 'N/A')} |
| 最新价 | {row.get('最新价', row.get('现价', 'N/A'))} |
| 涨跌额 | {row.get('涨跌额', 'N/A')} |
| 涨跌幅 | {row.get('涨跌幅', 'N/A')}% |
| 今开 | {row.get('今开', 'N/A')} |
| 最高 | {row.get('最高', 'N/A')} |
| 最低 | {row.get('最低', 'N/A')} |
| 昨收 | {row.get('昨收', 'N/A')} |
| 成交量 | {row.get('成交量', 'N/A')} |
| 成交额 | {row.get('成交额', 'N/A')} |
| 市盈率 | {row.get('市盈率', 'N/A')} |
| 总市值 | {row.get('总市值', 'N/A')} |
"""
                else:
                    realtime_text = "### 实时行情\n暂无实时行情数据\n"
            except Exception as e:
                logger.warning(f"获取港股实时行情失败: {e}")
                realtime_text = f"### 实时行情\n获取失败: {str(e)}\n"
            
            # === 2. 获取历史K线数据 ===
            hist_text = ""
            try:
                end_date = datetime.strptime(trade_date, '%Y-%m-%d')
                start_date = end_date - timedelta(days=60)  # 多取一些确保有足够交易日
                
                hist_df = await self._run_blocking(
                    ak.stock_hk_hist,
                    symbol=padded_code,
                    period="daily",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    adjust="qfq",
                    timeout=30,
                )
                
                if hist_df is not None and not hist_df.empty:
                    # 最近5个交易日摘要
                    hist_text = "### 最近5个交易日\n"
                    for idx, row in hist_df.tail(5).iterrows():
                        date_str = row.get('日期', 'N/A')
                        close = row.get('收盘', 'N/A')
                        pct = row.get('涨跌幅', 'N/A')
                        hist_text += f"- **{date_str}**: 收{close} ({pct:+.2f}%)\n"
                    
                    # 近期行情表（最新一天）
                    latest = hist_df.iloc[-1]
                    hist_text += f"""
### 近期行情
| 日期 | 开盘 | 收盘 | 最高 | 最低 | 成交量 | 成交额 | 涨跌幅 |
|------|------|------|------|------|--------|--------|--------|
| {latest.get('日期', 'N/A')} | {latest.get('开盘', 'N/A')} | {latest.get('收盘', 'N/A')} | {latest.get('最高', 'N/A')} | {latest.get('最低', 'N/A')} | {latest.get('成交量', 'N/A')} | {latest.get('成交额', 'N/A')} | {latest.get('涨跌幅', 'N/A')}% |
"""
                else:
                    hist_text = "### 历史K线\n暂无历史K线数据\n"
            except Exception as e:
                logger.warning(f"获取港股历史K线失败: {e}")
                hist_text = f"### 历史K线\n获取失败: {str(e)}\n"
            
            if not realtime_text and not hist_text:
                return f"暂无港股{code}的行情数据"
            
            return f"""## 港股市场数据

**股票代码**: {code}.HK
**交易日期**: {trade_date}
**市场**: {market_info['market_name']}
**货币**: {market_info['currency_name']}（{market_info['currency_symbol']}）

{realtime_text}
{hist_text}
---
*数据来源: akshare（东方财富）*
"""
                
        except ImportError:
            return "akshare未安装"
        except Exception as e:
            return f"获取港股数据失败: {str(e)}"
    

    async def _get_us_market_data(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取美股市场数据（akshare主数据源 + yfinance备选）"""
        
        # === 1. 尝试 akshare 作为主数据源 ===
        if self.akshare_available:
            try:
                import akshare as ak
                import pandas as pd
                
                # 获取实时行情
                spot_df = await self._run_blocking(ak.stock_us_spot_em, timeout=30)
                
                if spot_df is not None and not spot_df.empty:
                    # 匹配美股代码（akshare格式: "105.AAPL"）
                    matched = spot_df[spot_df['代码'].str.endswith(f'.{ticker}', na=False)]
                    
                    if not matched.empty:
                        row = matched.iloc[0]
                        ak_code = row['代码']  # 完整的 akshare 代码
                        
                        realtime_text = f"""### 实时行情（akshare）
| 指标 | 数值 |
|------|------|
| 股票名称 | {row.get('名称', 'N/A')} |
| 最新价 | ${row.get('最新价', row.get('现价', 'N/A'))} |
| 涨跌额 | {row.get('涨跌额', 'N/A')} |
| 涨跌幅 | {row.get('涨跌幅', 'N/A')}% |
| 今开 | {row.get('今开', 'N/A')} |
| 最高 | {row.get('最高', 'N/A')} |
| 最低 | {row.get('最低', 'N/A')} |
| 昨收 | {row.get('昨收', 'N/A')} |
| 成交量 | {row.get('成交量', 'N/A')} |
| 成交额 | {row.get('成交额', 'N/A')} |
| 总市值 | {row.get('总市值', 'N/A')} |
"""
                        
                        # 获取历史K线
                        hist_text = ""
                        try:
                            end_date = datetime.strptime(trade_date, '%Y-%m-%d')
                            start_date = end_date - timedelta(days=60)
                            
                            hist_df = await self._run_blocking(
                                ak.stock_us_hist,
                                symbol=ak_code,
                                period="daily",
                                start_date=start_date.strftime('%Y%m%d'),
                                end_date=end_date.strftime('%Y%m%d'),
                                adjust="qfq",
                                timeout=30,
                            )
                            
                            if hist_df is not None and not hist_df.empty:
                                hist_text = "\n### 最近5个交易日\n"
                                for idx, hrow in hist_df.tail(5).iterrows():
                                    date_str = hrow.get('日期', 'N/A')
                                    close = hrow.get('收盘', 'N/A')
                                    pct = hrow.get('涨跌幅', 'N/A')
                                    hist_text += f"- **{date_str}**: 收${close} ({pct:+.2f}%)\n"
                        except Exception as e:
                            logger.warning(f"获取美股历史K线失败(akshare): {e}")
                            hist_text = "\n### 历史K线\n获取失败\n"
                        
                        return f"""## 美股市场数据

**股票代码**: {ticker}
**交易日期**: {trade_date}
**市场**: {market_info['market_name']}
**货币**: {market_info['currency_name']}（{market_info['currency_symbol']}）

{realtime_text}
{hist_text}
---
*数据来源: akshare（东方财富）*
"""
            except Exception as e:
                logger.warning(f"akshare获取美股数据失败，回退到yfinance: {e}")
        
        # === 2. 回退到 yfinance ===
        if not self.yfinance_available:
            return "akshare和yfinance均不可用，无法获取美股数据"
        
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = await self._run_blocking(lambda: stock.info, timeout=30)
            
            # 获取历史数据
            end_date = datetime.strptime(trade_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=30)
            hist = await self._run_blocking(stock.history, start=start_date, end=end_date, timeout=30)
            
            hist_text = ""
            if hist is not None and not hist.empty:
                hist_text = "### 最近5个交易日\n"
                for idx, row in hist.tail(5).iterrows():
                    date_str = idx.strftime('%Y-%m-%d')
                    close = row['Close']
                    pct = row['Close'].pct_change() * 100 if idx != hist.index[0] else 0
                    hist_text += f"- **{date_str}**: 收${close:.2f} ({pct:+.2f}%)\n"
            
            return f"""## 美股市场数据

**股票代码**: {ticker}
**交易日期**: {trade_date}
**市场**: {market_info['market_name']}
**货币**: {market_info['currency_name']}（{market_info['currency_symbol']}）

### 公司信息（yfinance）
| 指标 | 数值 |
|------|------|
| 公司名称 | {info.get('shortName', info.get('longName', 'N/A'))} |
| 当前价格 | ${info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))} |
| 今日开盘 | ${info.get('regularMarketOpen', 'N/A')} |
| 今日最高 | ${info.get('dayHigh', info.get('regularMarketDayHigh', 'N/A'))} |
| 今日最低 | ${info.get('dayLow', info.get('regularMarketDayLow', 'N/A'))} |
| 52周最高 | ${info.get('fiftyTwoWeekHigh', 'N/A')} |
| 52周最低 | ${info.get('fiftyTwoWeekLow', 'N/A')} |
| 成交量 | {info.get('volume', info.get('regularMarketVolume', 'N/A')):,} |
| 总市值 | ${info.get('marketCap', 'N/A'):,.0f if info.get('marketCap') else 'N/A'} |
| 市盈率(TTM) | {info.get('trailingPE', 'N/A')} |
| 市净率 | {info.get('priceToBook', 'N/A')} |
| 股息收益率 | {info.get('dividendYield', 'N/A') or 'N/A'} |
| EPS | ${info.get('trailingEps', 'N/A')} |

{hist_text}
---
*数据来源: yfinance（akshare不可用时的备选）*
"""
        except ImportError:
            return "yfinance未安装，请运行: pip install yfinance"
        except Exception as e:
            return f"获取美股数据失败: {str(e)}"
    
    async def get_fundamentals(self, ticker: str, trade_date: str) -> str:
        """
        获取基本面数据 - 复刻 get_stock_fundamentals_unified
        """
        from .utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        try:
            if market_info['is_china']:
                return await self._get_china_fundamentals(ticker, trade_date, market_info)
            elif market_info['is_hk']:
                return await self._get_hk_fundamentals(ticker, trade_date, market_info)
            else:
                return await self._get_us_fundamentals(ticker, trade_date, market_info)
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return f"获取基本面数据失败: {str(e)}"
    
    async def _get_china_fundamentals(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取A股基本面数据"""
        if not self.akshare_available:
            return "akshare未安装，无法获取A股基本面数据"
        
        from .utils.stock_utils import StockUtils
        
        try:
            import akshare as ak
            import pandas as pd
            
            code = StockUtils.strip_market_prefix(ticker)
            
            try:
                # 使用 asyncio.to_thread 在线程池中执行同步API
                # 获取主要财务指标 - stock_financial_abstract 包含所有关键指标
                main_indicators = await self._run_blocking(
                    ak.stock_financial_abstract,
                    symbol=code,
                    timeout=30,
                )
                
                # 构建结果
                result = f"""## A股基本面数据

**股票代码**: {code}
**分析日期**: {trade_date}

"""
                
                if main_indicators is not None and not main_indicators.empty:
                    # 找到最新一期数据的列
                    cols = main_indicators.columns.tolist()
                    # 跳过 '选项' 和 '指标' 列，最新数据在第3列
                    latest_col = None
                    for col in cols[2:4]:  # 使用最近两期中的一期
                        if '20' in str(col):
                            latest_col = col
                            break
                    
                    if latest_col:
                        result += f"### 财务指标（报告期: {latest_col}）\n\n"
                        result += "| 指标 | 数值 |\n|------|------|\n"
                        
                        # 关键指标列表
                        key_indicators = [
                            ('每股收益', '每股收益'),
                            ('净资产收益率(ROE)', '净资产收益率(ROE)'),
                            ('销售毛利率', '销售毛利率'),
                            ('销售净利率', '销售净利率'),
                            ('资产负债率', '资产负债率'),
                            ('流动比率', '流动比率'),
                            ('速动比率', '速动比率'),
                            ('营业总收入', '营业总收入'),
                            ('净利润', '净利润'),
                            ('扣非净利润', '扣非净利润'),
                            ('经营现金流净额', '经营现金流净额'),
                            ('加权平均ROE', '加权平均净资产收益率'),
                        ]
                        
                        for display_name, data_name in key_indicators:
                            row = main_indicators[main_indicators['指标'] == data_name]
                            if not row.empty:
                                val = row[latest_col].values[0]
                                if pd.notna(val):
                                    if isinstance(val, (int, float)):
                                        if abs(val) > 1e8:  # 亿
                                            result += f"| {display_name} | {val/1e8:.2f}亿 |\n"
                                        elif abs(val) > 1e4:  # 万
                                            result += f"| {display_name} | {val/1e4:.2f}万 |\n"
                                        else:
                                            result += f"| {display_name} | {val:.4f} |\n"
                                    else:
                                        result += f"| {display_name} | {val} |\n"
                                else:
                                    result += f"| {display_name} | N/A |\n"
                            else:
                                result += f"| {display_name} | N/A |\n"
                
                return result
                
            except Exception as e:
                logger.error(f"获取A股基本面数据失败: {e}")
                return f"获取A股基本面数据失败: {str(e)}"
                
        except ImportError:
            return "akshare未安装"
        except Exception as e:
            return f"获取A股基本面失败: {str(e)}"
    
    async def _get_hk_fundamentals(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取港股基本面数据（akshare公司信息 + yfinance估值/财务）"""
        code = ticker.replace('.HK', '').replace('HK', '').replace('.', '')
        padded_code = self._pad_hk_code(code)
        
        result_parts = []
        result_parts.append(f"""## 港股基本面数据

**股票代码**: {code}.HK
**分析日期**: {trade_date}
""")
        
        # === 1. akshare: 雪球公司基本信息 ===
        if self.akshare_available:
            try:
                import akshare as ak
                
                info_df = await self._run_blocking(
                    ak.stock_individual_basic_info_hk_xq,
                    symbol=padded_code,
                    timeout=30,
                )
                
                if info_df is not None and not info_df.empty:
                    # 雪球返回的是 item-value 两列格式
                    info_dict = dict(zip(info_df.iloc[:, 0], info_df.iloc[:, 1]))
                    
                    company_text = "### 公司基本信息（雪球）\n| 指标 | 数值 |\n|------|------|\n"
                    
                    key_fields = {
                        '公司名称': '公司名称',
                        '所属行业': '所属行业',
                        '上市日期': '上市日期',
                        '总股本': '总股本',
                        '流通股本': '流通股本',
                        '市值': '市值',
                    }
                    for display, key in key_fields.items():
                        val = info_dict.get(key, 'N/A')
                        if val and str(val) != 'nan':
                            company_text += f"| {display} | {val} |\n"
                    
                    # 添加所有其他字段
                    for item, value in info_dict.items():
                        if item not in key_fields.values() and value and str(value) != 'nan':
                            company_text += f"| {item} | {value} |\n"
                    
                    result_parts.append(company_text)
                else:
                    result_parts.append("### 公司基本信息\n暂无公司基本信息数据\n")
            except Exception as e:
                logger.warning(f"获取港股雪球公司信息失败: {e}")
                result_parts.append(f"### 公司基本信息\n获取失败: {str(e)}\n")
        
        # === 2. yfinance: 估值指标 + 财务报表 ===
        if self.yfinance_available:
            try:
                import yfinance as yf
                
                yf_ticker = f"{code}.HK"
                stock = yf.Ticker(yf_ticker)
                info = await self._run_blocking(lambda: stock.info, timeout=30)
                
                if info:
                    # 估值指标
                    valuation_text = """### 估值指标（yfinance）
| 指标 | 数值 |
|------|------|
"""
                    val_fields = [
                        ('市盈率(TTM)', 'trailingPE'),
                        ('市盈率(前瞻)', 'forwardPE'),
                        ('市净率', 'priceToBook'),
                        ('市销率', 'priceToSalesTrailing12Months'),
                        ('总市值', 'marketCap'),
                        ('企业价值', 'enterpriseValue'),
                        ('股息率', 'dividendYield'),
                    ]
                    for display, key in val_fields:
                        val = info.get(key, 'N/A')
                        if val and val != 'N/A':
                            if key in ('marketCap', 'enterpriseValue') and isinstance(val, (int, float)):
                                val = f"${val:,.0f}"
                            elif key == 'dividendYield' and isinstance(val, (int, float)):
                                val = f"{val*100:.2f}%"
                            elif isinstance(val, float):
                                val = f"{val:.2f}"
                        valuation_text += f"| {display} | {val} |\n"
                    
                    result_parts.append(valuation_text)
                    
                    # 盈利能力
                    profit_fields = [
                        ('EPS(TTM)', 'trailingEps'),
                        ('毛利率', 'grossProfitMargin'),
                        ('营业利润率', 'operatingProfitMargin'),
                        ('净利率', 'profitMargins'),
                        ('ROE', 'returnOnEquity'),
                    ]
                    profit_text = """### 盈利能力（yfinance）
| 指标 | 数值 |
|------|------|
"""
                    for display, key in profit_fields:
                        val = info.get(key, 'N/A')
                        if val and val != 'N/A':
                            if key in ('grossProfitMargin', 'operatingProfitMargin', 'profitMargins', 'returnOnEquity') and isinstance(val, (int, float)):
                                val = f"{val*100:.2f}%"
                        profit_text += f"| {display} | {val} |\n"
                    
                    result_parts.append(profit_text)
                    
                    # 财务报表摘要
                    try:
                        income = await self._run_blocking(lambda: stock.income_stmt, timeout=30)
                        if income is not None and not income.empty:
                            fin_text = "\n### 损益表摘要（最近）\n"
                            for idx in income.head(8).index:
                                val = income.loc[idx].iloc[0] if len(income.loc[idx]) > 0 else 'N/A'
                                if isinstance(val, (int, float)) and val != 0:
                                    fin_text += f"- {idx}: ${val:,.0f}\n"
                            result_parts.append(fin_text)
                    except Exception as e:
                        logger.warning(f"获取港股财务报表失败: {e}")
                    
                    result_parts.append("\n*数据来源: akshare（雪球）+ yfinance*\n")
                else:
                    result_parts.append("\n*数据来源: akshare（雪球）*\n")
            except Exception as e:
                logger.warning(f"yfinance获取港股基本面失败: {e}")
                result_parts.append(f"\n### yfinance补充数据\n获取失败: {str(e)}\n")
                result_parts.append("\n*数据来源: akshare（雪球）*\n")
        else:
            result_parts.append("\n⚠️ yfinance未安装，无法获取估值和财务数据。建议安装: pip install yfinance\n")
            result_parts.append("\n*数据来源: akshare（雪球）*\n")
        
        return "\n".join(result_parts)
    
    async def _get_us_fundamentals(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取美股基本面数据（yfinance主 + akshare公司信息补充）"""
        result_parts = []
        result_parts.append(f"""## 美股基本面数据

**股票代码**: {ticker}
**分析日期**: {trade_date}
""")
        
        # === 1. akshare: 雪球公司信息补充 ===
        if self.akshare_available:
            try:
                import akshare as ak
                info_df = await self._run_blocking(
                    ak.stock_individual_basic_info_us_xq,
                    symbol=ticker,
                    timeout=30,
                )
                if info_df is not None and not info_df.empty:
                    info_dict = dict(zip(info_df.iloc[:, 0], info_df.iloc[:, 1]))
                    company_text = "### 公司基本信息（雪球）\n| 指标 | 数值 |\n|------|------|\n"
                    for item, value in info_dict.items():
                        if value and str(value) != 'nan':
                            company_text += f"| {item} | {value} |\n"
                    result_parts.append(company_text)
            except Exception as e:
                logger.warning(f"akshare获取美股公司信息失败: {e}")
        
        # === 2. yfinance: 估值 + 财务报表 ===
        if self.yfinance_available:
            try:
                import yfinance as yf
                
                stock = yf.Ticker(ticker)
                info = await self._run_blocking(lambda: stock.info, timeout=30)
                
                # 获取财务报表
                financial_text = ""
                try:
                    income = await self._run_blocking(lambda: stock.income_stmt, timeout=30)
                    balance = await self._run_blocking(lambda: stock.balance_sheet, timeout=30)
                    
                    if income is not None and not income.empty:
                        financial_text += "### 损益表（最近一年）\n"
                        for idx, row in income.head(5).iterrows():
                            name = idx
                            value = row.iloc[0] if len(row) > 0 else 'N/A'
                            if isinstance(value, (int, float)) and value > 0:
                                financial_text += f"- {name}: ${value:,.0f}\n"
                    
                    if balance is not None and not balance.empty:
                        financial_text += "\n### 资产负债表（最近一年）\n"
                        for idx, row in balance.head(5).iterrows():
                            name = idx
                            value = row.iloc[0] if len(row) > 0 else 'N/A'
                            if isinstance(value, (int, float)) and value > 0:
                                financial_text += f"- {name}: ${value:,.0f}\n"
                except Exception as e:
                    logger.warning(f"获取美股财务报表失败: {e}")
                
                result_parts.append(f"""### 估值指标（yfinance）
| 指标 | 数值 |
|------|------|
| 市盈率(TTM) | {info.get('trailingPE', 'N/A')} |
| 市盈率(前瞻) | {info.get('forwardPE', 'N/A')} |
| 市净率 | {info.get('priceToBook', 'N/A')} |
| 市销率 | {info.get('priceToSalesTrailing12Months', 'N/A')} |
| EV/EBITDA | {info.get('enterpriseToEbitda', 'N/A')} |
| 市值 | ${info.get('marketCap', 'N/A'):,.0f if info.get('marketCap') else 'N/A'} |
| 企业价值 | ${info.get('enterpriseValue', 'N/A'):,.0f if info.get('enterpriseValue') else 'N/A'} |

### 盈利能力（yfinance）
| 指标 | 数值 |
|------|------|
| EPS(TTM) | ${info.get('trailingEps', 'N/A')} |
| EPS(前瞻) | ${info.get('forwardEps', 'N/A')} |
| 净利润 | ${info.get('netIncomeToCommon', 'N/A'):,.0f if info.get('netIncomeToCommon') else 'N/A'} |
| 收入 | ${info.get('totalRevenue', 'N/A'):,.0f if info.get('totalRevenue') else 'N/A'} |
| 毛利率 | {info.get('grossProfitMargin', 'N/A')*100 if info.get('grossProfitMargin') else 'N/A'}% |
| 营业利润率 | {info.get('operatingProfitMargin', 'N/A')*100 if info.get('operatingProfitMargin') else 'N/A'}% |
| 净利率 | {info.get('profitMargins', 'N/A')*100 if info.get('profitMargins') else 'N/A'}% |

### 财务数据
{financial_text if financial_text else '暂无详细财务数据'}
""")
                result_parts.append("\n*数据来源: yfinance + akshare（雪球）*\n")
                
            except ImportError:
                return "yfinance未安装"
            except Exception as e:
                logger.warning(f"yfinance获取美股基本面失败: {e}")
                result_parts.append(f"\n### yfinance数据\n获取失败: {str(e)}\n")
        else:
            result_parts.append("\n⚠️ yfinance未安装，无法获取估值和财务数据\n")
        
        return "\n".join(result_parts)
    
    async def get_news(self, ticker: str, trade_date: str) -> str:
        """
        获取新闻数据 - 复刻 get_stock_news_unified
        """
        from .utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        try:
            if market_info['is_china']:
                return await self._get_china_news(ticker, trade_date, market_info)
            elif market_info['is_hk']:
                return await self._get_hk_news(ticker, trade_date, market_info)
            else:
                return await self._get_us_news(ticker, trade_date, market_info)
        except Exception as e:
            logger.error(f"获取新闻数据失败: {e}")
            return f"获取新闻数据失败: {str(e)}"
    
    async def _get_china_news(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取A股新闻"""
        if not self.akshare_available:
            return "akshare未安装，无法获取A股新闻"
        
        from .utils.stock_utils import StockUtils
        
        try:
            import akshare as ak
            
            code = StockUtils.strip_market_prefix(ticker)
            
            try:
                news_df = await self._run_blocking(ak.stock_news_em, symbol=code, timeout=30)
                
                if news_df is not None and not news_df.empty:
                    news_text = f"## A股新闻数据\n\n**股票代码**: {code}\n**日期**: {trade_date}\n\n### 近期新闻\n"
                    
                    for idx, row in news_df.head(10).iterrows():
                        news_time = row.get('发布时间', 'N/A')
                        news_title = row.get('新闻标题', 'N/A')
                        news_url = row.get('链接', '')
                        news_text += f"- **{news_time}**: {news_title}\n"
                    
                    return news_text
                else:
                    return f"暂无{code}的新闻数据"
                    
            except Exception as e:
                return f"获取A股新闻失败: {str(e)}"
                
        except ImportError:
            return "akshare未安装"
        except Exception as e:
            return f"获取A股新闻失败: {str(e)}"
    
    async def _get_hk_news(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取港股新闻（yfinance）"""
        code = ticker.replace('.HK', '').replace('HK', '').replace('.', '')
        
        if not self.yfinance_available:
            return "暂无港股新闻数据（需要付费数据源）"
        
        try:
            import yfinance as yf
            
            yf_ticker = f"{code}.HK"
            stock = yf.Ticker(yf_ticker)
            news = await self._run_blocking(lambda: stock.news, timeout=30)
            
            if news and len(news) > 0:
                news_text = f"""## 港股新闻数据

**股票代码**: {code}.HK
**日期**: {trade_date}

### 近期新闻
"""
                for item in news[:10]:
                    title = item.get('title', 'N/A')
                    publisher = item.get('publisher', 'N/A')
                    # yfinance 新闻时间戳处理
                    pub_ts = item.get('providerPublishTime', item.get('pubDate', ''))
                    if isinstance(pub_ts, (int, float)) and pub_ts:
                        try:
                            from datetime import timezone
                            pub_date = datetime.fromtimestamp(int(pub_ts), tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                        except Exception:
                            pub_date = str(pub_ts)
                    else:
                        pub_date = str(pub_ts)
                    news_text += f"- **{publisher}** ({pub_date}): {title}\n"
                
                news_text += "\n---\n*数据来源: yfinance*\n"
                return news_text
            else:
                return f"暂无港股{code}.HK的新闻数据"
                
        except Exception as e:
            logger.warning(f"获取港股新闻失败: {e}")
            return f"暂无港股新闻数据（获取失败: {str(e)}）"
    
    async def _get_us_news(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取美股新闻"""
        if not self.yfinance_available:
            return "yfinance未安装，无法获取美股新闻"
        
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            news = await self._run_blocking(lambda: stock.news, timeout=30)
            
            if news and len(news) > 0:
                news_text = f"## 美股新闻数据\n\n**股票代码**: {ticker}\n**日期**: {trade_date}\n\n### 近期新闻\n"
                
                for item in news[:10]:
                    pub_date = item.get('pubDate', 'N/A')
                    title = item.get('title', 'N/A')
                    publisher = item.get('publisher', 'N/A')
                    news_text += f"- **{publisher}** ({pub_date}): {title}\n"
                
                return news_text
            else:
                return f"暂无{ticker}的新闻数据"
                
        except ImportError:
            return "yfinance未安装"
        except Exception as e:
            return f"获取美股新闻失败: {str(e)}"
    
    async def get_sentiment(self, ticker: str, trade_date: str) -> str:
        """
        获取情绪数据 - 复刻 get_stock_sentiment_unified
        """
        from .utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        try:
            if market_info['is_china']:
                return await self._get_china_sentiment(ticker, trade_date, market_info)
            elif market_info['is_hk']:
                return await self._get_hk_sentiment(ticker, trade_date, market_info)
            else:
                return await self._get_us_sentiment(ticker, trade_date, market_info)
        except Exception as e:
            logger.error(f"获取情绪数据失败: {e}")
            return f"获取情绪数据失败: {str(e)}"
    
    async def _get_china_sentiment(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取A股情绪数据"""
        # A股情绪数据（东方财富等）
        if not self.akshare_available:
            return "akshare未安装，无法获取A股情绪数据"
        
        from .utils.stock_utils import StockUtils
        
        try:
            import akshare as ak
            
            code = StockUtils.strip_market_prefix(ticker)
            
            try:
                # 资金流向数据可作为情绪参考
                df = await self._run_blocking(
                    ak.stock_individual_fund_flow,
                    stock=code,
                    market="sh" if code.startswith(('600', '601', '603', '688')) else "sz",
                    timeout=30,
                )
                
                if df is not None and not df.empty:
                    sentiment_text = f"## A股情绪数据\n\n**股票代码**: {code}\n**日期**: {trade_date}\n\n### 资金流向\n"
                    
                    for idx, row in df.tail(5).iterrows():
                        date = row.get('日期', 'N/A')
                        net = row.get('今日主力净流入-净额', 'N/A')
                        net_pct = row.get('今日主力净流入-净占比', 'N/A')
                        sentiment_text += f"- **{date}**: 主力净流入 {net} ({net_pct}%)\n"
                    
                    sentiment_text += """
### 情绪分析
资金流向可反映市场情绪：
- 主力净流入 > 0：表示机构看多
- 主力净流入 < 0：表示机构看空
- 关注连续净流入/净流出天数
"""
                    return sentiment_text
                else:
                    return f"暂无{code}的情绪数据"
                    
            except Exception as e:
                return f"获取A股情绪数据失败: {str(e)}"
                
        except ImportError:
            return "akshare未安装"
        except Exception as e:
            return f"获取A股情绪失败: {str(e)}"
    
    async def _get_hk_sentiment(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取港股情绪数据（yfinance 分析师评级 + 推荐）"""
        code = ticker.replace('.HK', '').replace('HK', '').replace('.', '')
        
        if not self.yfinance_available:
            return "暂无港股情绪数据（需要付费数据源）"
        
        try:
            import yfinance as yf
            
            yf_ticker = f"{code}.HK"
            stock = yf.Ticker(yf_ticker)
            info = await self._run_blocking(lambda: stock.info, timeout=30)
            
            sentiment_parts = [f"""## 港股情绪数据

**股票代码**: {code}.HK
**日期**: {trade_date}

### 分析师情绪
| 指标 | 数值 |
|------|------|
"""]
            
            # 分析师评级
            rec_key = info.get('recommendationKey', 'N/A')
            target_price = info.get('targetMeanPrice', 'N/A')
            num_analysts = info.get('numberOfAnalystOpinions', 'N/A')
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
            
            sentiment_parts[0] += f"| 分析师评级 | {rec_key} |\n"
            sentiment_parts[0] += f"| 目标均价 | {target_price} |\n"
            sentiment_parts[0] += f"| 分析师数量 | {num_analysts} |\n"
            sentiment_parts[0] += f"| 当前价格 | {current_price} |\n"
            
            # 如果有目标价和当前价，计算上行空间
            if isinstance(target_price, (int, float)) and isinstance(current_price, (int, float)) and current_price > 0:
                upside = (target_price - current_price) / current_price * 100
                sentiment_parts[0] += f"| 上行空间 | {upside:+.2f}% |\n"
            
            # 获取评级变动
            try:
                recommendations = await self._run_blocking(
                    lambda: getattr(stock, 'recommendations', None),
                    timeout=30,
                )
                if recommendations is not None and not recommendations.empty:
                    rec_text = "\n### 近期评级变动\n"
                    for idx, row in recommendations.tail(5).iterrows():
                        date = idx
                        grade = row.get('To Grade', row.get('ToGrade', 'N/A'))
                        firm = row.get('Firm', row.get('firm', 'N/A'))
                        rec_text += f"- **{date}**: {firm} → {grade}\n"
                    sentiment_parts.append(rec_text)
            except Exception as e:
                logger.warning(f"获取港股评级变动失败: {e}")
            
            sentiment_parts.append("\n---\n*数据来源: yfinance*\n")
            return "\n".join(sentiment_parts)
            
        except Exception as e:
            logger.warning(f"获取港股情绪数据失败: {e}")
            return f"暂无港股情绪数据（获取失败: {str(e)}）"
    
    async def _get_us_sentiment(self, ticker: str, trade_date: str, market_info: Dict) -> str:
        """获取美股情绪数据"""
        if not self.yfinance_available:
            return "yfinance未安装，无法获取美股情绪数据"
        
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = await self._run_blocking(lambda: stock.info, timeout=30)
            
            # 从分析评级获取情绪
            recommendations = await self._run_blocking(
                lambda: getattr(stock, 'recommendations', None),
                timeout=30,
            )
            
            sentiment_text = f"""## 美股情绪数据

**股票代码**: {ticker}
**日期**: {trade_date}

### 分析师情绪
| 指标 | 数值 |
|------|------|
| 分析师评级 | {info.get('recommendationKey', 'N/A')} |
| 目标价 | ${info.get('targetMeanPrice', 'N/A')} |
| 买入评级数 | {info.get('numberOfAnalystOpinions', 'N/A')} |

### 情绪评分（1-10分）
| 方向 | 评分 | 说明 |
|------|------|------|
| 买入情绪 | 5-7分 | 中性偏正面 |
| 持有情绪 | 4-6分 | 中性 |
| 卖出情绪 | 2-4分 | 中性偏负面 |

注：美股情绪数据受新闻、社交媒体影响较大，建议结合多个数据源判断。
"""
            
            if recommendations is not None and not recommendations.empty:
                sentiment_text += "\n### 近期评级变动\n"
                for idx, row in recommendations.tail(5).iterrows():
                    date = idx
                    grade = row.get('ToGrade', 'N/A')
                    sentiment_text += f"- **{date}**: {grade}\n"
            
            return sentiment_text
            
        except ImportError:
            return "yfinance未安装"
        except Exception as e:
            return f"获取美股情绪失败: {str(e)}"


    async def fetch_all_data(self, ticker: str, trade_date: str) -> Dict:
        """
        一次性并发获取所有信息源数据，并检查数据完整性。

        Returns:
            dict: {
                'success': bool,              # 是否所有必要数据都获取成功
                'market_data': str,           # 市场数据
                'fundamentals_data': str,      # 基本面数据
                'news_data': str,              # 新闻数据
                'sentiment_data': str,         # 情绪数据
                'missing_sources': list,       # 缺失的信息源列表
                'error_details': dict,         # 各信息源的缺失原因 {source: reason}
            }
        """
        import asyncio

        # 并发获取所有数据
        market_task = self.get_market_data(ticker, trade_date)
        fundamentals_task = self.get_fundamentals(ticker, trade_date)
        news_task = self.get_news(ticker, trade_date)
        sentiment_task = self.get_sentiment(ticker, trade_date)

        results = await asyncio.gather(
            market_task, fundamentals_task, news_task, sentiment_task,
            return_exceptions=True
        )

        market_data = results[0] if not isinstance(results[0], Exception) else f"获取失败: {results[0]}"
        fundamentals_data = results[1] if not isinstance(results[1], Exception) else f"获取失败: {results[1]}"
        news_data = results[2] if not isinstance(results[2], Exception) else f"获取失败: {results[2]}"
        sentiment_data = results[3] if not isinstance(results[3], Exception) else f"获取失败: {results[3]}"

        # 数据完整性校验
        missing_sources = []
        error_details = {}

        # 市场数据校验
        market_ok = self._check_data_valid(market_data, '市场数据')
        if not market_ok['valid']:
            missing_sources.append('市场数据')
            error_details['市场数据'] = market_ok['reason']

        # 基本面数据校验
        fundamentals_ok = self._check_data_valid(fundamentals_data, '基本面数据')
        if not fundamentals_ok['valid']:
            missing_sources.append('基本面数据')
            error_details['基本面数据'] = fundamentals_ok['reason']

        # 新闻数据校验
        news_ok = self._check_data_valid(news_data, '新闻数据')
        if not news_ok['valid']:
            missing_sources.append('新闻数据')
            error_details['新闻数据'] = news_ok['reason']

        # 情绪数据校验（非强制，仅警告）
        sentiment_ok = self._check_data_valid(sentiment_data, '情绪数据')
        if not sentiment_ok['valid']:
            error_details['情绪数据'] = sentiment_ok['reason']

        # 判断是否数据齐全：市场数据和基本面数据是必须的
        success = len(missing_sources) == 0

        return {
            'success': success,
            'market_data': market_data,
            'fundamentals_data': fundamentals_data,
            'news_data': news_data,
            'sentiment_data': sentiment_data,
            'missing_sources': missing_sources,
            'error_details': error_details,
        }

    def _check_data_valid(self, data: str, source_name: str) -> Dict[str, any]:
        """
        检查数据是否有效（非空、非失败信息）。

        Args:
            data: 数据文本
            source_name: 数据源名称（用于日志）

        Returns:
            {'valid': bool, 'reason': str}
        """
        if not data or not data.strip():
            return {'valid': False, 'reason': '数据为空'}

        # 检测常见的失败标志
        failure_keywords = [
            '获取失败', '未安装', '无法获取', '暂无', '不可用',
            'akshare未安装', 'yfinance未安装',
            'akshare和yfinance均不可用',
            '需要付费数据源',
        ]

        data_lower = data.strip().lower()
        data_first_line = data.strip().split('\n')[0].strip()

        # 如果整段数据非常短且包含失败关键词，则认为失败
        if len(data.strip()) < 100:
            for kw in failure_keywords:
                if kw in data_first_line or kw in data_lower:
                    return {'valid': False, 'reason': data_first_line}
        else:
            # 较长的数据，仅检查首行是否是纯错误信息
            for kw in failure_keywords:
                if data_first_line == kw or data_first_line.endswith(kw):
                    return {'valid': False, 'reason': data_first_line}

        return {'valid': True, 'reason': ''}


# 全局单例
_data_fetcher = None

def get_data_fetcher() -> DataFetcher:
    """获取全局DataFetcher实例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher
