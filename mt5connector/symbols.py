# 品种目录工具：品种类型启发式与关键字搜索（纯函数，pytest 直接覆盖）。

from __future__ import annotations

from .gateway import SymbolMeta

# 协议 InstrumentType 枚举（market-data-v1）
INSTRUMENT_TYPES = ("stock", "index", "fund", "etf", "future", "option", "forex", "crypto", "unknown")

# 常见指数 CFD 前缀（Exness 命名惯例，尽力而为非精确）
_INDEX_PREFIXES = (
    "US500", "NAS100", "US30", "US100", "USTEC", "GER40", "UK100", "JP225", "HK50", "AUS200",
)

# 常见加密前缀
_CRYPTO_PREFIXES = ("BTC", "ETH", "LTC", "XRP", "SOL", "DOGE", "ADA", "BNB", "DOT", "AVAX")

# 贵金属现货
_METALS_PREFIXES = ("XAU", "XAG", "XPT", "XPD")

# 主要法币后缀（外汇判定）
_FIAT_SUFFIXES = ("USD", "JPY", "EUR", "GBP", "CHF", "AUD", "NZD", "CAD")


def guess_instrument_type(symbol: str) -> str:
    """按 symbol 命名启发式判定品种类型；映射到协议枚举，无法判定时 unknown。"""
    s = (symbol or "").upper()
    if s.startswith(_CRYPTO_PREFIXES):
        return "crypto"
    if s.startswith(_INDEX_PREFIXES):
        return "index"
    if s.startswith(_METALS_PREFIXES):
        return "forex"  # 现货贵金属与外汇同为 spot 报价
    if len(s) >= 6 and s.endswith(_FIAT_SUFFIXES):
        return "forex"
    return "unknown"


def search_symbols(
    catalog: list[SymbolMeta], keyword: str, limit: int, instrument_types: list[str] | None = None
) -> list[SymbolMeta]:
    """关键字过滤品种目录：代码或描述子串匹配（大小写不敏感），按代码序返回前 limit 条。"""
    needle = (keyword or "").strip().lower()
    allowed = {cls.lower() for cls in instrument_types} if instrument_types else None
    matched: list[SymbolMeta] = []
    for meta in catalog:
        if needle and needle not in meta.name.lower() and needle not in meta.description.lower():
            continue
        if allowed is not None and guess_instrument_type(meta.name) not in allowed:
            continue
        matched.append(meta)
        if len(matched) >= limit:
            break
    return matched
