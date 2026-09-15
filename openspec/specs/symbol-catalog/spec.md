# Symbol Catalog Specification

## Purpose

把 MT5 终端的上千个原始品种映射为 V1 InstrumentDescriptor，并提供关键字搜索。
命名启发式尽力而为（非精确）；品种身份由 providerRef 原样带回，前端不得推断。

## Requirements

### Requirement: 资产类别启发式映射

系统 SHALL 按 symbol 命名判定资产类别并映射到协议枚举：加密前缀
（BTC/ETH/LTC/XRP/SOL/DOGE/ADA/BNB/DOT/AVAX）→ crypto；指数 CFD 前缀
（US500/NAS100/US30/US100/USTEC/GER40/UK100/JP225/HK50/AUS200）→ index；
贵金属现货前缀（XAU/XAG/XPT/XPD）→ forex（现货报价）；主要法币对后缀
（≥6 字符且以 USD/JPY/EUR/GBP/CHF/AUD/NZD/CAD 结尾）→ forex；其余 → unknown。

#### Scenario: 贵金属映射

- **WHEN** symbol 为 XAUUSD
- **THEN** assetClass 为 forex（现货贵金属与外汇同口径）

#### Scenario: 无法判定

- **WHEN** symbol 不匹配任何启发式
- **THEN** assetClass 为 unknown（不猜测）

### Requirement: 关键字搜索契约

搜索 SHALL 对品种代码与描述做大小写不敏感的子串匹配，按代码序返回前 limit 条；
assetClasses 过滤参数 SHALL 与启发式结果求交。结果描述符 SHALL 满足：
id=`mt5:<SYMBOL>`、sourceId=`mt5`、sessionId=`MT5`（对应前端注册的 7x24 UTC 会话）、
providerRef=`{symbol}` 原样回传、capabilities 声明全部支持周期与 `none` 复权。

#### Scenario: 描述匹配

- **WHEN** 以「gold」搜索（XAUUSD 描述为 Gold vs US Dollar）
- **THEN** 命中 XAUUSD

#### Scenario: providerRef 回传

- **WHEN** 前端 bars 请求带回 providerRef
- **THEN** 连接器按 providerRef.symbol 解析品种，不依赖 id 字符串格式
