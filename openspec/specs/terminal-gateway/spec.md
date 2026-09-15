# Terminal Gateway Specification

## Purpose

MetaTrader5 Python 包的唯一持有者：连接生命周期管理与全部数据查询的串行执行点。
MetaTrader5 无异步接口且不可多线程并发调用；裸 `initialize()` 会拉起 Windows
默认终端（可能连错经纪商），必须防御。

## Requirements

### Requirement: 单工作线程串行执行

全部 MetaTrader5 调用 SHALL 经单工作线程（ThreadPoolExecutor max_workers=1）
串行执行并以 async 接口暴露；其余模块 SHALL NOT 直接 import MetaTrader5。

#### Scenario: 并发请求不并发进入 IPC

- **WHEN** 多个协程同时发起查询
- **THEN** 底层 MetaTrader5 调用按队列顺序逐个执行

### Requirement: 显式路径初始化与平台校验

initialize SHALL 传入终端全路径：显式 `MT5_TERMINAL_PATH` 优先，否则按已知
Exness 安装路径探测；绝无路径时才允许默认行为。`EXNESS_ONLY=1`（默认）时
SHALL 校验 terminal company/server 含 `exness`，且账户必须已登录
（account_info().login 非空）；校验失败 SHALL shutdown 并抛错（启动失败不阻断
HTTP 服务——probe 如实上报 offline）。

#### Scenario: 未登录账户

- **WHEN** 终端已启动但无已登录账户
- **THEN** initialize 抛「终端未登录」错误

#### Scenario: 非 Exness 平台

- **WHEN** 终端为其他经纪商且 EXNESS_ONLY=1
- **THEN** initialize 抛平台校验失败错误，提示设置 MT5_TERMINAL_PATH 或 EXNESS_ONLY=0

### Requirement: 限流心跳重连

心跳循环（默认 5s）SHALL 探测 terminal_info().connected；断连时重连尝试
SHALL 限流（相邻 initialize 间隔 ≥ 10s），禁止 re-initialize 风暴；失败原因
记录到 init_error 供 probe 展示。

#### Scenario: 断连后限流重连

- **WHEN** 终端断连且两次重连间隔不足 10s
- **THEN** 跳过本轮，下个心跳窗口再试

### Requirement: 品种目录缓存

`symbols_get()` 全量较重，SHALL 以 60s TTL 缓存品种元数据
（name/description/currency_profit/point/volume_min），并提供缓存失效入口。

#### Scenario: 缓存命中

- **WHEN** 60s 内再次请求品种目录
- **THEN** 不发起 symbols_get 调用，直接返回缓存副本
