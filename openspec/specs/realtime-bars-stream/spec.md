# Realtime Bars Stream Specification

## Purpose

SSE 实时行情流：一条连接承载一组品种订阅，服务端按品种路由快照与增量帧。
连接状态、退避与重连节奏归客户端；服务端只负责快照、增量与存活信号。

## Requirements

### Requirement: 多品种订阅与连接参数

系统 SHALL 提供 `GET /api/v1/market-data/sources/mt5/stream?instruments=&period=`，
`instruments` 为逗号分隔的品种列表，`period` 必填，`barAggregation` 可选。
报价通道 SHALL 提供 `GET /api/v1/market-data/sources/mt5/quotes?instruments=`。
不支持的周期或口径 SHALL 返回 400 `UNSUPPORTED_CAPABILITY`；品种为空 SHALL 返回 400 `INVALID_REQUEST`。
响应 SHALL 携带 `X-Accel-Buffering: no` 与 no-cache 头。

#### Scenario: 多品种共享一条连接

- **WHEN** 客户端以 `instruments=mt5:XAUUSD,mt5:EURUSD` 建流
- **THEN** 服务端只建立一条 SSE 连接，帧按 `instrumentId` 区分品种

#### Scenario: 品种身份原样透传

- **WHEN** 请求携带大小写混写的品种
- **THEN** 系统按原样查询 MT5，帧内 `instrumentId` 与订阅一致

### Requirement: 帧信封与序号

每帧 SHALL 为 JSON，统一信封 `{type, seq, ts}`：`seq` 是连接级单调递增序号
（`hello` 为 -1，之后从 0 递增），`ts` 是服务端毫秒时间。
`hello` SHALL 是连接首帧，携带 `instruments` 与 `snapshotSize`；报价通道的 `snapshotSize` 为 0。

#### Scenario: 首帧回显订阅身份

- **WHEN** 客户端建立连接
- **THEN** 第一帧是 `hello`，其 `instruments` 与服务端实际接受的一致

### Requirement: 快照与增量帧

`snapshot` SHALL 携带 `instrumentId` 与 `bars`（尾部快照）。
`bar` SHALL 携带 `instrumentId`、`state`（`forming` | `closed`）与 `bar`。

#### Scenario: 收线终值

- **WHEN** 采样发现末根 openTime 前移
- **THEN** 先发 `bar`（`state: closed`，终值取新采样中该时间戳的值），再发 `bar`（`state: forming`）；该终值不再以 forming 重复发出

#### Scenario: 无变化不推帧

- **WHEN** 采样结果与上次完全一致
- **THEN** 不下发任何行情帧

### Requirement: 报价、状态与心跳帧

`quote` SHALL 携带 `instrumentId` 与 `quote: {last, prevClose, timestamp}`。
`status` SHALL 携带 `instrumentId`、`status`（`live` | `market-closed` | `upstream-error`）与可选 `detail`。
`ping` SHALL 每 15 秒下发一次，且必须是数据帧而不是 SSE 注释，客户端据此判断存活。

#### Scenario: 上游异常上浮

- **WHEN** 轮询上游抛错
- **THEN** 下发 `status`（`upstream-error`，`detail` 携带原因），连接保持可重试

### Requirement: 报价派生

报价帧 SHALL 由增量帧的尾部窗口派生：`last` 取最新根收盘、`prevClose` 取上一根收盘，
涨跌幅由消费端计算；尾部不足两根时 SHALL NOT 下发报价帧。

#### Scenario: 有待比基准才推报价

- **WHEN** 订阅品种的尾部窗口至少有两根 K 线
- **THEN** 下发一帧 `quote`；同一基准重复出现时不重复推送

### Requirement: Last-Event-ID 回放与存活

断线重连时客户端可携带 `Last-Event-ID`，服务端 SHALL 从环形缓冲回放 seq 大于该值的帧，
再无缝衔接实时帧；回放与实时队列的重叠帧按 seq 去重。
新订阅的基准 seq SHALL 在触发快照发布之前捕获，回放逻辑不得补进快照之前的帧。

#### Scenario: 从环缓冲续接

- **WHEN** 客户端带 `Last-Event-ID: N` 重连
- **THEN** 依次收到缓冲中 seq > N 的帧，随后是无缝衔接的实时帧

#### Scenario: 观测者关闭

- **WHEN** 连接断开
- **THEN** 该连接的观察者被移除，最后一个观察者离开后轮询任务在后台自行退出
