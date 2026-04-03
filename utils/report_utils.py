"""报告工具：Markdown → PDF 转换 & 结论提取。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import datetime

import markdown


# ── 内嵌字体路径 ─────────────────────────────────────────────────────
_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"


def _font_path(filename: str) -> str:
    """返回字体文件的 file:// URI；文件不存在则返回空字符串（weasyprint 会忽略空 url）。"""
    p = _FONT_DIR / filename
    return p.as_uri() if p.exists() else ""


# ── 结论提取 ──────────────────────────────────────────────────────────

def extract_conclusion(report: str) -> str:
    """
    从完整分析报告中提取最终建议/结论部分。

    策略（按优先级）：
    1. 提取「风险评估」章节的全部内容（从标题到报告元数据之前）
    2. 提取「多空辩论综合」章节的全部内容
    3. 回退：取报告最后几个实质段落

    会自动排除报告元数据（生成时间、免责声明）。
    """
    if not report or report.startswith("❌"):
        return report or "报告生成失败"

    def _strip_footer(text: str) -> str:
        """去除文本末尾的元数据行。"""
        text = re.sub(
            r'\n\*{0,2}报告生成时间\*{0,2}.*$', '', text, flags=re.DOTALL,
        )
        text = re.sub(
            r'\n\*{0,2}本报告由AI自动生成.*$', '', text, flags=re.DOTALL,
        )
        text = re.sub(r'\n*---\s*$', '', text)
        return text.strip()

    def _extract_section(text: str, keyword: str) -> str | None:
        """
        提取包含 keyword 的 ## 章节的全部内容。
        章节边界 = 从 ## 标题行到「报告生成时间」之间的所有文字。
        不使用 ## 子标题作为边界，因为 LLM 会在章节内部使用 ##。
        """
        # 找所有包含 keyword 的 ## 标题行（取最后一个，因为风险评估通常是最后一节）
        matches = list(re.finditer(
            r'^## [^\n]*' + re.escape(keyword) + r'[^\n]*$',
            text, re.MULTILINE,
        ))
        if not matches:
            return None
        m = matches[-1]  # 取最后一个匹配
        heading = m.group(0).strip()
        body_start = m.end()

        # 章节结束 = 「报告生成时间」或文本末尾
        meta_match = re.search(
            r'\n\*{0,2}报告生成时间', text[body_start:],
        )
        if meta_match:
            body_end = body_start + meta_match.start()
        else:
            body_end = len(text)

        body = _strip_footer(text[body_start:body_end])
        if not body or len(body) < 30:
            return None

        clean_heading = re.sub(r'^##\s*', '', heading)
        return f"**{clean_heading}**\n\n{body}"

    # ── 策略 1：风险评估章节 ──
    result = _extract_section(report, '风险评估')
    if result:
        return result

    # ── 策略 2：多空辩论综合章节 ──
    result = _extract_section(report, '辩论综合')
    if result:
        return result

    # ── 策略 3：回退，取报告最后几个实质段落 ──
    cleaned = _strip_footer(report)
    paragraphs = [
        p.strip() for p in cleaned.split('\n\n')
        if p.strip() and p.strip() != '---'
        and not re.match(r'^#{1,3}\s', p.strip())
    ]
    if paragraphs:
        return '\n\n'.join(paragraphs[-5:])

    return report


def check_pdf_available() -> tuple[bool, str]:
    """
    检查 PDF 生成所需的依赖是否可用。

    Returns:
        (可用与否, 原因说明)
    """
    try:
        from weasyprint import HTML  # noqa: F401
        return True, ""
    except (ImportError, OSError) as e:
        return False, f"缺少 PDF 依赖: {e}"


# ── Emoji → 文字标签映射（PDF 用） ──────────────────────────────────

_EMOJI_REPLACEMENTS: list[tuple[re.Pattern, str]] = [
    # 常用符号 emoji
    (re.compile(r'⚠️|⚠'), '⚠'),
    (re.compile(r'⚔️|⚔'), '⚔'),
    (re.compile(r'📊'), '[数据]'),
    (re.compile(r'📈'), '[↑]'),
    (re.compile(r'📉'), '[↓]'),
    (re.compile(r'📋'), '[清单]'),
    (re.compile(r'📰'), '[新闻]'),
    (re.compile(r'🔍'), '[分析]'),
    (re.compile(r'🎯'), '[目标]'),
    (re.compile(r'💰'), '[资金]'),
    (re.compile(r'💭'), '[观点]'),
    (re.compile(r'🛡️|🛡'), '[防护]'),
    (re.compile(r'⚡'), '[⚡]'),
    (re.compile(r'🔥'), '[!]'),
    (re.compile(r'📊'), '[图表]'),
    # 动物（多空用）
    (re.compile(r'🐂'), '[看涨]'),
    (re.compile(r'🐻'), '[看跌]'),
    # 彩色圆点（风险等级）
    (re.compile(r'🔴'), '●'),
    (re.compile(r'🟡'), '◐'),
    (re.compile(r'🟢'), '○'),
    (re.compile(r'🔵'), '◆'),
    # 其他常见 emoji
    (re.compile(r'✅'), '✓'),
    (re.compile(r'❌'), '✗'),
    (re.compile(r'❗'), '!'),
    (re.compile(r'📌'), '[注]'),
    (re.compile(r'💡'), '[提示]'),
    (re.compile(r'🔑'), '[关键]'),
    (re.compile(r'🚀'), '[↑↑]'),
    (re.compile(r'💀'), '[×]'),
    (re.compile(r'🏆'), '[★]'),
    (re.compile(r'📢'), '[公告]'),
    (re.compile(r'🤖'), '[AI]'),
    (re.compile(r'📝'), '[报告]'),
    (re.compile(r'🧠'), '[思考]'),
    (re.compile(r'💎'), '[+]'),
    (re.compile(r'⚖️|⚖'), '[权衡]'),
    (re.compile(r'🤝'), '[合作]'),
    (re.compile(r'🌏'), '[全球]'),
    # 滑稽/交易相关
    (re.compile(r'💸'), '[亏损]'),
    (re.compile(r'🏦'), '[银行]'),
    (re.compile(r'📅'), '[日期]'),
    (re.compile(r'🗂️|🗂'), '[归档]'),
]


def _replace_emojis_for_pdf(text: str) -> str:
    """将 Markdown 文本中的 emoji 替换为文字标签，确保 PDF 可正常显示。"""
    for pattern, replacement in _EMOJI_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    # 兜底：移除剩余的其他 emoji（U+1F300-U+1FFFF 范围）
    text = re.sub(r'[\U0001F300-\U0001FFFF]', '', text)
    return text


# ── Markdown → PDF ───────────────────────────────────────────────────

_REPORT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: "Noto Sans SC";
    src: url("{regular_font_uri}") format("truetype");
    font-weight: normal;
    font-style: normal;
  }}
  @font-face {{
    font-family: "Noto Sans SC";
    src: url("{bold_font_uri}") format("truetype");
    font-weight: bold;
    font-style: normal;
  }}
  @page {{
    size: A4;
    margin: 2cm 2.5cm;
  }}
  body {{
    font-family: "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC",
                 "Microsoft YaHei", "WenQuanYi Micro Hei", sans-serif;
    font-size: 13px;
    line-height: 1.7;
    color: #333;
  }}
  h1 {{
    font-size: 22px;
    border-bottom: 2px solid #1a73e8;
    padding-bottom: 8px;
    color: #1a73e8;
  }}
  h2 {{
    font-size: 17px;
    margin-top: 24px;
    color: #333;
    border-left: 4px solid #1a73e8;
    padding-left: 10px;
  }}
  h3 {{
    font-size: 15px;
    color: #555;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
  }}
  th, td {{
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: left;
    font-size: 12px;
  }}
  th {{
    background-color: #f5f7fa;
  }}
  blockquote {{
    border-left: 4px solid #ddd;
    margin: 10px 0;
    padding: 8px 16px;
    color: #666;
  }}
  strong {{
    color: #222;
  }}
  em {{
    color: #555;
  }}
  hr {{
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 20px 0;
  }}
  code {{
    background: #f5f5f5;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 12px;
  }}
  .footer {{
    text-align: center;
    color: #999;
    font-size: 11px;
    margin-top: 30px;
    border-top: 1px solid #e0e0e0;
    padding-top: 10px;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""


def markdown_to_pdf_bytes(md_text: str) -> bytes:
    """
    将 Markdown 文本转换为 PDF 字节。

    使用 markdown 库转为 HTML，再通过 weasyprint 渲染为 PDF。

    Args:
        md_text: Markdown 格式的报告文本

    Returns:
        PDF 文件的二进制内容

    Raises:
        ImportError: 如果缺少依赖库
        RuntimeError: 如果 PDF 生成失败
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "生成 PDF 需要安装 weasyprint，请运行: pip install weasyprint"
        )

    # 预处理：将 emoji 替换为文字标签，确保 PDF 中可显示
    md_for_pdf = _replace_emojis_for_pdf(md_text)

    # Markdown → HTML
    body_html = markdown.markdown(
        md_for_pdf,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    full_html = _REPORT_HTML_TEMPLATE.format(
        body_html=body_html,
        regular_font_uri=_font_path("NotoSansSC-Regular.ttf"),
        bold_font_uri=_font_path("NotoSansSC-Bold.ttf"),
    )

    # 渲染为 PDF
    pdf_bytes = HTML(string=full_html).write_pdf()
    return pdf_bytes


def save_report_pdf(md_text: str, ticker: str, output_dir: str | None = None) -> str:
    """
    将 Markdown 报告保存为 PDF 文件。

    Args:
        md_text: Markdown 格式的报告
        ticker: 股票代码（用于文件名）
        output_dir: 输出目录，默认为 data/plugin_data/astrbot_plugin_tradingagents/reports

    Returns:
        保存的 PDF 文件绝对路径
    """
    if output_dir is None:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path
            base = get_astrbot_data_path()
            # get_astrbot_data_path() 可能返回 str 或 Path，统一用 os.path.join
            output_dir = os.path.join(
                str(base), "plugin_data", "astrbot_plugin_tradingagents", "reports"
            )
        except ImportError:
            output_dir = os.path.join(
                os.path.expanduser("~"), ".astrbot_plugin_tradingagents", "reports"
            )

    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名： ticker_日期_时间.pdf
    now = datetime.now()
    filename = f"{ticker}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf_bytes = markdown_to_pdf_bytes(md_text)

    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    return filepath


def save_report_md(md_text: str, ticker: str, output_dir: str | None = None) -> str:
    """
    将 Markdown 报告保存为 .md 文件（PDF 不可用时的降级方案）。

    Args:
        md_text: Markdown 格式的报告
        ticker: 股票代码（用于文件名）
        output_dir: 输出目录

    Returns:
        保存的 .md 文件绝对路径
    """
    if output_dir is None:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path
            base = get_astrbot_data_path()
            output_dir = os.path.join(
                str(base), "plugin_data", "astrbot_plugin_tradingagents", "reports"
            )
        except ImportError:
            output_dir = os.path.join(
                os.path.expanduser("~"), ".astrbot_plugin_tradingagents", "reports"
            )

    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    filename = f"{ticker}_{now.strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_text)

    return filepath


def save_report_txt(md_text: str, ticker: str, output_dir: str | None = None) -> str:
    """
    将报告保存为纯文本 .txt 文件（PDF 不可用时的降级方案）。

    Args:
        md_text: Markdown 格式的报告
        ticker: 股票代码（用于文件名）
        output_dir: 输出目录

    Returns:
        保存的 .txt 文件绝对路径
    """
    if output_dir is None:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path
            base = get_astrbot_data_path()
            output_dir = os.path.join(
                str(base), "plugin_data", "astrbot_plugin_tradingagents", "reports"
            )
        except ImportError:
            output_dir = os.path.join(
                os.path.expanduser("~"), ".astrbot_plugin_tradingagents", "reports"
            )

    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    filename = f"{ticker}_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(output_dir, filename)

    # 预处理：将 emoji 替换为文字标签，确保纯文本中可正常显示
    txt_text = _replace_emojis_for_pdf(md_text)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(txt_text)

    return filepath
