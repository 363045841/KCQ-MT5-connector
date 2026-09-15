# 对齐重采样语义测试：冬夏令时 4h/日线边界、DST 切换、周日短棒并入周一、周月锚、偏移校正。
# 用例语义移植自 WaveTrader 对齐验收（行为基准，非代码复制）。

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.align import GMT2, ATHENS, anchor_tz, resample, server_to_utc_ms
from app.frames import Bar

UTC = timezone.utc


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _h1(start: datetime, hours: int) -> list[Bar]:
    """从 start 起的连续 H1 服务器时间 Bar（offset=0 时服务器时间即 UTC）。"""
    return [
        Bar(_ms(start + timedelta(hours=i)), 1.0 + i, 2.0 + i, 0.5, 1.5 + i, 100, 0.0)
        for i in range(hours)
    ]


def test_daily_winter_merges_sunday_stub():
    # 2026-01-11 周日，冬令时（EET=UTC+2）：周日 22:00 UTC = 周一 EET 00:00
    start = datetime(2026, 1, 11, 22, 0, tzinfo=UTC)
    daily = resample(_h1(start, 72), "daily", GMT2, 0)

    assert daily[0].time_ms == _ms(start)
    assert daily[0].volume == 24 * 100
    assert len(daily) == 3
    assert daily[1].time_ms == _ms(start + timedelta(days=1))
    assert daily[2].time_ms == _ms(start + timedelta(days=2))


def test_4h_winter_boundaries():
    start = datetime(2026, 1, 11, 22, 0, tzinfo=UTC)
    bars = resample(_h1(start, 48), "4h", GMT2, 0)

    expected = [start + timedelta(hours=h) for h in range(0, 48, 4)]
    assert [b.time_ms for b in bars] == [_ms(t) for t in expected]
    assert bars[0].volume == 4 * 100


def test_daily_summer_athens_gmt3():
    # 2026-08-16 周日，夏令时（EEST=UTC+3）：周一 00:00 = 周日 21:00 UTC
    start = datetime(2026, 8, 16, 21, 0, tzinfo=UTC)
    daily = resample(_h1(start, 72), "daily", ATHENS, 0)

    assert daily[0].time_ms == _ms(start)
    assert daily[0].volume == 24 * 100
    assert daily[1].time_ms == _ms(start + timedelta(days=1))
    assert daily[2].time_ms == _ms(start + timedelta(days=2))


def test_4h_summer_boundaries():
    start = datetime(2026, 8, 16, 21, 0, tzinfo=UTC)
    bars = resample(_h1(start, 48), "4h", ATHENS, 0)

    expected = [start + timedelta(hours=h) for h in range(0, 48, 4)]
    assert [b.time_ms for b in bars] == [_ms(t) for t in expected]


def test_dst_spring_transition_day_has_23h_sunday():
    # 2026 欧洲夏令时开始：3/29（周日）02:00→03:00 本地，周日 EET 只有 23 根 H1
    start = datetime(2026, 3, 28, 22, 0, tzinfo=UTC)  # 周日 EET 00:00
    daily = resample(_h1(start, 48), "daily", ATHENS, 0)

    assert daily[0].time_ms == _ms(datetime(2026, 3, 28, 22, 0, tzinfo=UTC))
    assert daily[0].volume == 23 * 100
    assert daily[1].time_ms == _ms(datetime(2026, 3, 29, 21, 0, tzinfo=UTC))
    assert daily[2].time_ms == _ms(datetime(2026, 3, 30, 21, 0, tzinfo=UTC))


def test_weekly_monday_anchor_winter():
    # 冬令时周一 00:00 EET = 周日 22:00 UTC；2026-01-05 为周一
    first_monday = datetime(2026, 1, 4, 22, 0, tzinfo=UTC)
    daily_bars = [
        Bar(_ms(first_monday + timedelta(days=d)), 1.0, 2.0, 0.5, 1.5, 100, 0.0)
        for d in range(21)
    ]
    weekly = resample(daily_bars, "weekly", GMT2, 0)

    assert weekly[0].time_ms == _ms(first_monday)
    assert len(weekly) == 3  # 3 个 ISO 周
    assert weekly[1].time_ms == _ms(first_monday + timedelta(weeks=1))


def test_monthly_calendar_anchor_winter():
    # 1/31 00:00 EET = 1/30 22:00 UTC；2/1 EET = 1/31 22:00 UTC
    jan = datetime(2026, 1, 30, 22, 0, tzinfo=UTC)
    feb = datetime(2026, 1, 31, 22, 0, tzinfo=UTC)
    daily_bars = [
        Bar(_ms(jan), 1, 2, 0.5, 1.5, 10, 0),
        Bar(_ms(feb), 1, 2, 0.5, 1.5, 20, 0),
    ]
    monthly = resample(daily_bars, "monthly", GMT2, 0)

    assert len(monthly) == 2
    assert monthly[0].time_ms == _ms(datetime(2025, 12, 31, 22, 0, tzinfo=UTC))  # 1/1 EET
    assert monthly[1].time_ms == _ms(feb)  # 2/1 EET
    assert monthly[0].volume == 10
    assert monthly[1].volume == 20


def test_crypto_anchor_utc_natural_boundaries():
    # 加密品种 4h 锚 UTC：边界 {00,04,08...}，与 EET/EEST 无关
    start = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    bars = resample(_h1(start, 12), "4h", anchor_tz("crypto", "auto"), 0)

    assert [b.time_ms for b in bars] == [
        _ms(datetime(2026, 8, 16, h, 0, tzinfo=UTC)) for h in (0, 4, 8)
    ]


def test_server_offset_shifts_output_to_utc():
    # 服务器领先 UTC 120 分钟：服务器 00:00 → UTC 前一日 22:00，落入前一日 UTC 桶
    server_midnight = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)
    bars = [Bar(_ms(server_midnight), 1, 2, 0.5, 1.5, 100, 0)]
    daily = resample(bars, "daily", anchor_tz("crypto", "auto"), 120)

    # 日线桶起点 = UTC 前一日 00:00（偏移校正后归属 8/16 的 UTC 自然日）
    assert daily[0].time_ms == _ms(datetime(2026, 8, 16, 0, 0, tzinfo=UTC))


def test_anchor_tz_fixed_modes():
    assert anchor_tz("forex", "gmt2") == GMT2
    assert anchor_tz("forex", "gmt3").utcoffset(None) == timedelta(hours=3)
    assert anchor_tz("crypto", "gmt2") is timezone.utc  # 加密始终 UTC
    assert anchor_tz("forex", "auto") == ATHENS


def test_server_to_utc_ms_negative_offset():
    assert server_to_utc_ms(1_000, 0) == 1_000
    assert server_to_utc_ms(1_000, 120) == 1_000 - 120 * 60_000
    assert server_to_utc_ms(1_000, -60) == 1_000 + 60 * 60_000
