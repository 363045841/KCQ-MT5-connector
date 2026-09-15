# Exness Alignment Specification

## Purpose

把 MT5 的「服务器墙钟按 UTC epoch 解释」伪 UTC 时间轴换算为真 UTC，并按锚时区
重采样高周期 K 线，使图表显示、指标计算与存储三层数据同源一致。行为基准：
传统品种（外汇/金属/指数）锚 Europe/Athens（EET/EEST 自动 DST，冬 +2 / 夏 +3），
加密品种锚 UTC（币安标准边界 4h={00,04,08...}）；周日短棒不剔除——日内原生保留，
高周期在重采样中自然并入周一首根。

## Requirements

### Requirement: 服务器偏移实测与覆盖

系统 SHALL 以活跃品种最后 tick 时间与本机时钟差实测服务器领先 UTC 的整小时偏移，
取整后模 24h 归一到 [-12h, +12h)（消除周末停市累积天数）；探测品种优先 7x24 的
加密（BTCUSD/ETHUSD），外汇/金属兜底。`EXNESS_SERVER_UTC_OFFSET` env SHALL 覆盖实测；
实测失败回落 0。偏移 SHALL 周期复测（默认 300s）并在 probe 响应上报
`serverOffsetMinutes` 与 `offsetMeasured`。

#### Scenario: 周末停市不偏移

- **WHEN** 最后 tick 距今超过 24h（周末停市）
- **THEN** 实测偏移经模 24h 归一后仍等于服务器真实偏移（如 +180 分钟）

#### Scenario: env 覆盖

- **WHEN** `EXNESS_SERVER_UTC_OFFSET=2`
- **THEN** 偏移取 +120 分钟，跳过实测

### Requirement: 对齐开关语义

`ALIGN_TZ` env SHALL 控制对齐：`off` 关闭（取 MT5 原生周期数据，仅偏移校正）；
`gmt2`/`gmt3` 强制开启且传统品种锚固定偏移；`auto`（默认）仅在检测到 Exness
平台（company/server 含 exness）时开启。加密品种 SHALL 始终锚 UTC，不受 gmt2/gmt3 影响。
对齐状态 SHALL 在 probe 响应的 `alignment.anchor` 上报。

#### Scenario: auto 模式非 Exness 平台

- **WHEN** 终端 company/server 不含 exness 且 ALIGN_TZ=auto
- **THEN** 对齐关闭，4h/daily/weekly/monthly 走原生周期端点

### Requirement: 高周期锚时区重采样

对齐开启时，4h/daily SHALL 从 H1、weekly/monthly SHALL 从 D1 按锚时区重采样：
锚时区归日（normalize），4h 再按 hour//4*4 分桶，weekly 取 ISO 周锚（周 00:00），
monthly 取自然月首日。输出时间戳 SHALL 为锚时区边界对应的 UTC 毫秒；
OHLCV 按桶聚合（open=first, high=max, low=min, close=last, volume/turnover=sum）。

#### Scenario: 冬令时周日短棒并入周一

- **WHEN** 输入 H1 序列始于周日 22:00 UTC（= 周一 EET 00:00）且跨 72 小时
- **THEN** daily 重采样输出 3 根，首根开于周日 22:00 UTC、量为 24×H1 量

#### Scenario: 夏令时边界随 EEST 平移

- **WHEN** 8 月（EEST）输入 H1 序列始于周日 21:00 UTC
- **THEN** daily 首根开于周日 21:00 UTC；4h 边界为 {21,01,05,09,13,17} UTC

#### Scenario: DST 切换日

- **WHEN** 3 月最后一个周日（02:00→03:00 本地）跨越重采样
- **THEN** 该周日（EET）日线只含 23 根 H1，次日（EEST）起开于 21:00 UTC

#### Scenario: 加密品种 UTC 锚

- **WHEN** 品种为 BTCUSD（crypto）且对齐开启
- **THEN** 4h 边界为 {00,04,08,12,16,20} UTC，与 DST 无关
