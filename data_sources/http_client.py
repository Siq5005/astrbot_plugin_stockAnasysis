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
