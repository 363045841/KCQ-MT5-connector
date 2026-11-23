# K 线与实时帧的数据模型：aggregator/hub/routes 共用，禁止各处重复定义。
# K 线帧的身份一律是 instrumentId（数据源范围内稳定 ID），连接参数（周期/聚合）不再逐帧重复。

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Bar:
    """单根 K 线；time_ms 语义由调用方约定（网关返回=服务器伪 UTC，对齐输出=真 UTC）。"""

    time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    turnover: float = 0.0


@dataclass(frozen=True, slots=True)
class SnapshotFrame:
    """订阅建立时的尾部快照（含最后一根收线与当前 forming）。"""

    instrument_id: str
    bars: tuple[Bar, ...]


@dataclass(frozen=True, slots=True)
class FormingFrame:
    """forming bar 内容更新（时间戳不变、OHLCV 变化）。"""

    instrument_id: str
    bar: Bar


@dataclass(frozen=True, slots=True)
class ClosedFrame:
    """一根 bar 收线（openTime 前移后旧根终值，含终端缓存滞后的修订）。"""

    instrument_id: str
    bar: Bar


@dataclass(frozen=True, slots=True)
class StatusFrame:
    """流级状态变化（行情开闭/连接异常），不携带 bar。"""

    instrument_id: str
    status: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Tick:
    """单笔逐笔 tick；time_ms 语义由调用方约定（网关返回=服务器伪 UTC，推送=真 UTC）。"""

    time_ms: int
    bid: float
    ask: float
    last: float
    volume: float


@dataclass(frozen=True, slots=True)
class TicksFrame:
    """一批逐笔 tick 推送（同一采样窗口内按时间升序合并，不丢中间 tick）。"""

    symbol: str
    ticks: tuple[Tick, ...]


# 帧联合类型别名
Frame = SnapshotFrame | FormingFrame | ClosedFrame | StatusFrame | TicksFrame


def frame_payload(frame: Frame, seq: int) -> dict[str, object]:
    """把帧序列化为 V1.1 载荷：统一信封 seq/ts，增量帧带 state，身份一律 instrumentId。"""
    ts = int(time.time() * 1000)
    match frame:
        case SnapshotFrame(instrument_id, bars):
            return {
                "type": "snapshot",
                "seq": seq,
                "ts": ts,
                "instrumentId": instrument_id,
                "bars": [bar_to_dict(bar) for bar in bars],
            }
        case FormingFrame(instrument_id, bar):
            return {
                "type": "bar",
                "seq": seq,
                "ts": ts,
                "instrumentId": instrument_id,
                "state": "forming",
                "bar": bar_to_dict(bar),
            }
        case ClosedFrame(instrument_id, bar):
            return {
                "type": "bar",
                "seq": seq,
                "ts": ts,
                "instrumentId": instrument_id,
                "state": "closed",
                "bar": bar_to_dict(bar),
            }
        case StatusFrame(instrument_id, status, detail):
            return {
                "type": "status",
                "seq": seq,
                "ts": ts,
                "instrumentId": instrument_id,
                "status": status,
                "detail": detail,
            }
        case TicksFrame(symbol, ticks):
            return {
                "type": "ticks",
                "seq": seq,
                "ts": ts,
                "symbol": symbol,
                "ticks": [tick_to_dict(tick) for tick in ticks],
            }
    raise TypeError(f"unknown frame: {frame!r}")


def hello_payload(instruments: tuple[str, ...], snapshot_size: int) -> dict[str, object]:
    """连接级 hello：回显订阅身份与快照条数，客户端据此确认服务端理解一致。"""
    return {
        "type": "hello",
        "seq": -1,
        "ts": int(time.time() * 1000),
        "instruments": list(instruments),
        "snapshotSize": snapshot_size,
    }


def ping_payload(seq: int) -> dict[str, object]:
    """连接级心跳：数据帧而非注释，浏览器 JS 才能观察存活。"""
    return {"type": "ping", "seq": seq, "ts": int(time.time() * 1000)}


def quote_payload(
    instrument_id: str, last: float, prev_close: float, timestamp: int, seq: int
) -> dict[str, object]:
    """报价载荷：只给最新价与昨收，涨跌幅由消费端派生；结构与其他品种帧一致。"""
    return {
        "type": "quote",
        "seq": seq,
        "ts": int(time.time() * 1000),
        "instrumentId": instrument_id,
        "quote": {"last": last, "prevClose": prev_close, "timestamp": timestamp},
    }


def bar_to_dict(bar: Bar) -> dict[str, float | int]:
    """Bar 转 V1 KLineItem 字典（时间戳为 UTC 毫秒）。"""
    return {
        "timestamp": bar.time_ms,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "turnover": bar.turnover,
    }


def tick_to_dict(tick: Tick) -> dict[str, float | int]:
    """Tick 转逐笔字典（timestamp 为真 UTC 毫秒）。"""
    return {
        "timestamp": tick.time_ms,
        "bid": tick.bid,
        "ask": tick.ask,
        "last": tick.last,
        "volume": tick.volume,
    }
