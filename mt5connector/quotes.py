# 报价投影：把日线实时帧压成最新价与昨收。
# 报价不新增上游查询路径——它复用图表同一条日线实时流，只取尾部两根。

from __future__ import annotations

from .frames import Bar, ClosedFrame, FormingFrame, Frame, SnapshotFrame, quote_payload

# 只保留最近三根：两根用于计算，多留一根给收线后的修订。
_KEEP_BARS = 3


class QuoteProjection:
    """按品种维护日线尾部，输出最新价与昨收；值不变时不重复推送。"""

    def __init__(self) -> None:
        self._bars: dict[str, list[Bar]] = {}
        self._emitted: dict[str, tuple[float, float]] = {}

    def push(self, frame: Frame) -> dict[str, object] | None:
        """送入一帧；产生新的报价才返回载荷，其余帧返回 None。"""
        if isinstance(frame, SnapshotFrame):
            self._bars[frame.instrument_id] = list(frame.bars)[-_KEEP_BARS:]
        elif isinstance(frame, (FormingFrame, ClosedFrame)):
            self._upsert(frame.instrument_id, frame.bar)
        else:
            return None
        return self._quote(frame.instrument_id)

    def _upsert(self, instrument_id: str, bar: Bar) -> None:
        """按时间戳升序插入或覆盖，只保留尾部窗口。"""
        bars = self._bars.setdefault(instrument_id, [])
        for index, existing in enumerate(bars):
            if existing.time_ms == bar.time_ms:
                bars[index] = bar
                return
            if existing.time_ms > bar.time_ms:
                bars.insert(index, bar)
                break
        else:
            bars.append(bar)
        del bars[:-_KEEP_BARS]

    def _quote(self, instrument_id: str) -> dict[str, object] | None:
        """倒数两根即最新价与昨收；不足两根时没有可比的基准。"""
        bars = self._bars.get(instrument_id, [])
        if len(bars) < 2:
            return None
        last, previous = bars[-1], bars[-2]
        marker = (last.close, previous.close)
        if self._emitted.get(instrument_id) == marker:
            return None
        self._emitted[instrument_id] = marker
        return quote_payload(instrument_id, last.close, previous.close, last.time_ms)
