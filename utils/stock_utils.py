"""
股票工具类 - 用于股票代码识别、市场信息获取。

提供股票代码标准化、市场识别（A股/港股/美股）、股票名称查询等功能。
"""
import re
import time
from typing import Dict, Optional, Tuple

class StockUtils:
    """股票工具类，处理股票代码识别和市场信息"""

    # A股股票代码特征（用于文档说明，实际判断使用下方前缀）
    CHINA_STOCK_PATTERNS = [
        r'^\d{6}$',
        r'^(SH|SZ|XSHG|XSHE)\d{6}$',
        r'^\d{6}\.(SH|SZ|XSHG|XSHE)$',
    ]

    # 港股代码特征
    HK_STOCK_PATTERNS = [
        r'^\d{4}\.HK$',
        r'^HK\d{4}$',
    ]

    # 美股代码特征
    US_STOCK_PATTERNS = [
        r'^[A-Z]{1,5}$',
        r'^[A-Z]{1,5}\.[A-Z]{2}$',
    ]

    # 上海交易所代码前缀（6开头 + ETF 51/56/58开头）
    SH_PREFIXES = ('SH', 'XSHG', '600', '601', '603', '605', '688')
    # 深圳交易所代码前缀（0/3开头 + ETF 15/16开头）
    SZ_PREFIXES = ('SZ', 'XSHE', '000', '001', '002', '003', '300')

    # 上海 ETF 代码前缀（51/56/58开头，6位数字）
    SH_ETF_PREFIXES = ('510', '511', '512', '513', '514', '515', '516', '517', '518',
                       '560', '561', '562', '563', '565',
                       '580', '581', '582', '585', '588')
    # 深圳 ETF 代码前缀（15/16开头，6位数字）
    SZ_ETF_PREFIXES = ('159', '150', '151', '152', '153', '154', '155', '156',
                       '160', '161', '162', '163', '164', '165', '166', '167', '168')

    # A股名称缓存: {股票名称: 股票代码}
    _a_stock_name_cache: Optional[Dict[str, str]] = None
    _a_stock_cache_ts: float = 0.0
    _A_STOCK_CACHE_TTL: float = 4 * 3600  # 4小时过期

    # 中文字符正则
    _CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')

    @classmethod
    def _contains_chinese(cls, text: str) -> bool:
        """判断字符串是否包含中文字符"""
        return bool(cls._CHINESE_RE.search(text))

    @classmethod
    def _ensure_a_stock_cache(cls):
        """
        确保A股名称→代码缓存已加载（带TTL）。
        优先使用 akshare 的 stock_zh_a_spot_em()，失败时降级到腾讯接口。
        """
        now = time.time()
        if cls._a_stock_name_cache is not None and (now - cls._a_stock_cache_ts) < cls._A_STOCK_CACHE_TTL:
            return

        cache: Dict[str, str] = {}

        # 1. 尝试 akshare (东方财富)
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            for _, row in df.iterrows():
                name = str(row.get('名称', '')).strip()
                code = str(row.get('代码', '')).strip()
                if name and code:
                    cache[name] = code
            cls._a_stock_name_cache = cache
            cls._a_stock_cache_ts = now
            return
        except Exception:
            pass  # 继续尝试降级方案

        # 2. 降级: 腾讯批量行情接口
        try:
            import requests
            for market in ('sh', 'sz'):
                url = f'https://qt.gtimg.cn/q={market}a'
                resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                if resp.status_code != 200:
                    continue
                for line in resp.text.split(';'):
                    line = line.strip()
                    if not line or '~' not in line:
                        continue
                    parts = line.split('~')
                    if len(parts) >= 3:
                        name = parts[1].strip()
                        code = parts[2].strip()
                        if name and code and len(code) == 6 and code.isdigit():
                            cache[name] = code
            if cache:
                cls._a_stock_name_cache = cache
                cls._a_stock_cache_ts = now
                return
        except Exception:
            pass

        # 全部失败
        if cls._a_stock_name_cache is None:
            cls._a_stock_name_cache = {}

    @classmethod
    def resolve_stock_name(cls, ticker: str) -> Optional[str]:
        """
        尝试将中文股票名称解析为股票代码。

        通过 akshare 的 A 股实时列表进行名称匹配。
        支持精确匹配和模糊匹配（名称包含输入关键词）。

        Args:
            ticker: 可能是中文股票名称的字符串

        Returns:
            解析出的股票代码（如 "000905"），无法解析时返回 None
        """
        if not cls._contains_chinese(ticker):
            return None

        cls._ensure_a_stock_cache()

        if not cls._a_stock_name_cache:
            return None

        # 1. 精确匹配
        code = cls._a_stock_name_cache.get(ticker.strip())
        if code:
            return code

        # 2. 模糊匹配：输入关键词是股票名称的子串
        stripped = ticker.strip()
        matches = [(name, code) for name, code in cls._a_stock_name_cache.items()
                    if stripped in name]
        if len(matches) == 1:
            return matches[0][1]

        # 3. 模糊匹配：股票名称是输入关键词的子串
        matches2 = [(name, code) for name, code in cls._a_stock_name_cache.items()
                     if name in stripped]
        if len(matches2) == 1:
            return matches2[0][1]

        return None

    @classmethod
    def is_valid_stock_code(cls, ticker: str) -> bool:
        """
        判断输入是否为有效的股票代码格式（而非股票名称）。

        有效格式包括：
        - A股纯6位数字: 000001, 600000
        - A股带前缀: SH600000, SZ000001
        - 港股: 0700.HK, HK0700
        - 美股纯字母: AAPL, TSLA

        Args:
            ticker: 用户输入

        Returns:
            True 表示是有效代码格式，False 表示可能是名称
        """
        t = ticker.strip().upper().replace(' ', '')

        # 包含中文 → 不是代码
        if cls._CHINESE_RE.search(t):
            return False

        # A股: 纯6位数字
        if re.match(r'^\d{6}$', t):
            return True

        # A股: SH/SZ/XSHG/XSHE + 6位数字
        if re.match(r'^(SH|SZ|XSHG|XSHE)\d{6}$', t):
            return True

        # 港股: 数字.HK 或 HK+数字
        if re.match(r'^\d{4,5}\.HK$', t):
            return True
        if re.match(r'^HK\d{4,5}$', t):
            return True

        # 美股: 1-5个大写字母（可能带交易所后缀）
        if re.match(r'^[A-Z]{1,5}(\.[A-Z]{2})?$', t):
            return True

        return False

    @classmethod
    def normalize_ticker(cls, ticker: str) -> str:
        """
        标准化股票代码。

        将各种格式的股票代码统一为标准格式：
        - A股: SH600000 / SZ000001
        - 港股: 0700.HK
        - 美股: AAPL

        支持中文股票名称输入（如"厦门港务"→"SZ000905"）。

        Args:
            ticker: 原始股票代码或中文名称

        Returns:
            标准化后的股票代码
        """
        ticker = ticker.strip()
        if not ticker:
            return ticker

        # 中文股票名称 → 解析为代码
        if cls._contains_chinese(ticker):
            resolved = cls.resolve_stock_name(ticker)
            if resolved:
                ticker = resolved
            else:
                # 含中文但无法解析为代码，原样返回（后续 market_info 会标记 resolution_failed）
                return ticker.strip()

        ticker = ticker.upper()

        # 港股 .HK 格式保留
        if ticker.endswith('.HK'):
            return ticker

        # 移除可能残留的空格
        ticker = ticker.replace(' ', '')

        # 处理 SH/SZ 前缀 → 保留前缀
        if ticker.startswith('SH'):
            return ticker
        elif ticker.startswith('SZ'):
            return ticker
        # HK 前缀 → 转为 .HK 格式
        elif ticker.startswith('HK'):
            return ticker[2:] + '.HK'
        # 纯6位数字 → 根据前缀判断沪深
        elif re.match(r'^\d{6}$', ticker):
            if ticker.startswith(('600', '601', '603', '605', '688')):
                return 'SH' + ticker
            # 上海 ETF（51/56/58开头）
            if cls._is_sh_etf_code(ticker):
                return 'SH' + ticker
            # 深圳 ETF（15/16开头）
            if cls._is_sz_etf_code(ticker):
                return 'SZ' + ticker
            return 'SZ' + ticker

        return ticker
    
    @classmethod
    def get_market_info(cls, ticker: str) -> Dict[str, any]:
        """
        获取股票市场信息。

        Args:
            ticker: 股票代码

        Returns:
            市场信息字典，包含 is_china/is_hk/is_us、market_name、exchange、currency 等
        """
        normalized = cls.normalize_ticker(ticker)

        # 检测市场类型
        is_china = cls.is_china_stock(normalized)
        is_hk = cls.is_hk_stock(normalized)
        is_us = cls.is_us_stock(normalized)

        market_name_map = {
            'ch': '中国A股',
            'hk': '港股',
            'us': '美股'
        }

        currency_map = {
            'ch': ('人民币', 'CNY', '¥'),
            'hk': ('港币', 'HKD', 'HK$'),
            'us': ('美元', 'USD', '$')
        }

        if is_china:
            market_key = 'ch'
            if normalized.startswith('SH') or normalized.startswith('XSHG'):
                exchange = 'XSHG'
            else:
                exchange = 'XSHE'
        elif is_hk:
            market_key = 'hk'
            exchange = 'HKG'
        else:
            market_key = 'us'
            exchange = 'US'

        market_name = market_name_map[market_key]
        currency_name, currency_code, currency_symbol = currency_map[market_key]

        # 防御：包含中文但被归为美股，说明名称解析失败
        resolved_ticker = normalized
        if market_key == 'us' and cls._contains_chinese(ticker):
            # 用解析前的原始 ticker 判断
            if not cls.is_us_stock(normalized):
                # 无法识别市场，标记为未知市场而非误判为美股
                return {
                    'is_china': False,
                    'is_hk': False,
                    'is_us': False,
                    'market_name': '未知市场',
                    'exchange': 'UNKNOWN',
                    'currency_name': '未知',
                    'currency_code': 'UNKNOWN',
                    'currency_symbol': '',
                    'normalized_ticker': ticker.strip(),
                    'resolution_failed': True,
                    'resolution_message': f'无法识别股票"{ticker.strip()}"的所属市场，请使用股票代码查询（如：000905、SH600000、0700.HK、AAPL）'
                }

        # ETF检测（仅A股范围内判断）
        is_etf = is_china and cls.is_etf(normalized)
        if is_etf:
            market_name = '中国A股(ETF)'

        return {
            'is_china': is_china,
            'is_hk': is_hk,
            'is_us': is_us,
            'is_etf': is_etf,
            'market_name': market_name,
            'exchange': exchange,
            'currency_name': currency_name,
            'currency_code': currency_code,
            'currency_symbol': currency_symbol,
            'normalized_ticker': normalized
        }

    @classmethod
    def strip_market_prefix(cls, ticker: str) -> str:
        """
        剥离 A 股代码的 SH/SZ 市场前缀，返回纯 6 位数字。

        对于非 A 股代码，原样返回。

        Args:
            ticker: 标准化后的股票代码

        Returns:
            去除市场前缀后的代码
        """
        if ticker.startswith('SH') or ticker.startswith('SZ'):
            return ticker[2:]
        return ticker
    
    @classmethod
    def _is_sh_etf_code(cls, code: str) -> bool:
        """判断纯6位数字代码是否为上海ETF（51/56/58开头）"""
        if not code or len(code) < 3:
            return False
        return code[:3] in cls.SH_ETF_PREFIXES

    @classmethod
    def _is_sz_etf_code(cls, code: str) -> bool:
        """判断纯6位数字代码是否为深圳ETF（15/16开头）"""
        if not code or len(code) < 3:
            return False
        return code[:3] in cls.SZ_ETF_PREFIXES

    @classmethod
    def is_etf(cls, ticker: str) -> bool:
        """判断股票代码是否为ETF(交易所交易基金)。

        上海ETF前缀: 510xxx, 511xxx, 512xxx, 513xxx, 514xxx, 515xxx, 56xxxx, 58xxxx
        深圳ETF前缀: 159xxx, 150xxx, 160xxx, 16xxxx

        Args:
            ticker: 股票代码(已标准化或原始格式均可)

        Returns:
            True 表示是ETF代码
        """
        normalized = cls.normalize_ticker(ticker)

        if cls._contains_chinese(normalized):
            return False

        code = cls.strip_market_prefix(normalized)

        if not re.match(r'^\d{6}$', code):
            return False

        return cls._is_sh_etf_code(code) or cls._is_sz_etf_code(code)

    @classmethod
    def is_china_stock(cls, ticker: str) -> bool:
        """判断是否为A股"""
        normalized = cls.normalize_ticker(ticker)
        
        # 含中文的不可能是代码格式
        if cls._contains_chinese(normalized):
            return False
        
        # 纯数字6位判断
        if re.match(r'^\d{6}$', normalized):
            return True
        
        # 带SH/SZ前缀
        if normalized.startswith(('SH', 'SZ', 'XSHG', 'XSHE')):
            return True
            
        return False
    
    @classmethod
    def is_hk_stock(cls, ticker: str) -> bool:
        """判断是否为港股"""
        normalized = cls.normalize_ticker(ticker)
        
        # 含中文的不可能是港股代码
        if cls._contains_chinese(normalized):
            return False
        
        if normalized.endswith('.HK'):
            return True
        if normalized.startswith('HK') and len(normalized) == 6:
            return True
            
        return False
    
    @classmethod
    def is_us_stock(cls, ticker: str) -> bool:
        """判断是否为美股"""
        normalized = cls.normalize_ticker(ticker)
        
        # 含中文的不可能是美股代码
        if cls._contains_chinese(normalized):
            return False
        
        # 美股是纯字母
        if re.match(r'^[A-Z]{1,5}$', normalized):
            # 排除已经是SH/SZ的情况
            if not normalized.startswith(('SH', 'SZ')):
                return True
                
        return False
    
    @classmethod
    def get_stock_name(cls, ticker: str) -> str:
        """
        获取股票名称（通过akshare）
        
        Args:
            ticker: 股票代码
            
        Returns:
            股票名称
        """
        market_info = cls.get_market_info(ticker)
        normalized = market_info['normalized_ticker']
        
        try:
            if market_info['is_china']:
                return cls._get_china_stock_name(normalized)
            elif market_info['is_hk']:
                return cls._get_hk_stock_name(normalized)
            else:
                return cls._get_us_stock_name(normalized)
        except Exception as e:
            return f"股票{normalized}"
    
    @classmethod
    def _get_china_stock_name(cls, ticker: str) -> str:
        """获取A股/ETF名称"""
        try:
            import akshare as ak

            code = cls.strip_market_prefix(ticker)

            # ETF → 使用 fund_etf_spot_em 查询名称
            if cls.is_etf(ticker):
                try:
                    df = ak.fund_etf_spot_em()
                    result = df[df['代码'] == code]
                    if not result.empty:
                        return result.iloc[0]['名称']
                except Exception:
                    pass
                return f"ETF{code}"

            # 上海交易所
            if code.startswith(('600', '601', '603', '605', '688')):
                try:
                    for symbol in ('主板A股', '科创板'):
                        df = ak.stock_info_sh_name_code(symbol=symbol)
                        result = df[df['证券代码'] == code]
                        if not result.empty:
                            return result.iloc[0]['证券简称']
                except Exception:
                    pass

            # 深圳交易所
            try:
                df = ak.stock_info_sz_name_code(symbol="A股列表")
                result = df[df['A股代码'] == code]
                if not result.empty:
                    return result.iloc[0]['A股简称']
            except Exception:
                pass

            # 东方财富实时列表兜底
            try:
                df = ak.stock_zh_a_spot_em()
                result = df[df['代码'] == code]
                if not result.empty:
                    return result.iloc[0]['名称']
            except Exception:
                pass

            # 腾讯接口兜底
            try:
                import requests
                prefix = 'sh' if code.startswith(('6', '9', '5')) else 'sz'
                url = f'https://qt.gtimg.cn/q={prefix}{code}'
                resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                parts = resp.text.split('~')
                if len(parts) >= 2 and parts[1].strip():
                    return parts[1].strip()
            except Exception:
                pass

            return f"A股{code}"
        except Exception:
            return f"A股{ticker}"
    
    @classmethod
    def _get_hk_stock_name(cls, ticker: str) -> str:
        """获取港股股票名称"""
        try:
            import akshare as ak

            code = ticker.replace('.HK', '')

            try:
                df = ak.stock_hk_spot_em()
                result = df[df['代码'] == code]
                if not result.empty:
                    return result.iloc[0]['名称']
            except Exception:
                pass

            return f"港股{code}"
        except Exception:
            return f"港股{ticker}"
    
    @classmethod
    def _get_us_stock_name(cls, ticker: str) -> str:
        """获取美股股票名称"""
        # 常用美股名称映射
        US_NAMES = {
            'AAPL': '苹果公司',
            'TSLA': '特斯拉',
            'NVDA': '英伟达',
            'MSFT': '微软',
            'GOOGL': '谷歌',
            'AMZN': '亚马逊',
            'META': 'Meta Platforms',
            'NFLX': '奈飞',
            'AMD': '超微半导体',
            'INTC': '英特尔',
            'BABA': '阿里巴巴',
            'JD': '京东',
            'PDD': '拼多多',
            'NIO': '蔚来',
            'XPEV': '小鹏汽车',
            'LI': '理想汽车',
        }
        
        return US_NAMES.get(ticker.upper(), f"美股{ticker}")
    
    @classmethod
    def format_ticker_for_api(cls, ticker: str, market_info: Dict[str, any] = None) -> str:
        """
        格式化股票代码用于API调用。

        - A股: 返回纯6位数字
        - 港股: 保留 .HK 格式
        - 美股: 大写字母

        Args:
            ticker: 股票代码
            market_info: 市场信息（可选）

        Returns:
            格式化后的代码
        """
        if market_info is None:
            market_info = cls.get_market_info(ticker)

        normalized = market_info['normalized_ticker']

        if market_info['is_china']:
            return cls.strip_market_prefix(normalized)
        elif market_info['is_hk']:
            return normalized
        else:
            return normalized.upper()
