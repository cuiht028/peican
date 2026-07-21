"""地域识别与节气计算服务。

  * ``get_solar_term(date)``：基于「寿星公式」纯 Python 计算当前节气
    （21 世纪近似，无需联网）。
  * ``detect()``：综合 app_setting 中的手动覆盖，返回地域 / 节气 / 养生提示。

说明：寿星公式为天文近似值，个别年份与权威发布可能相差 ±1 天，对家庭
养生提示场景足够。如需更高精度可后续替换为天文算法。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app import config
from app.database import DB

# 21 世纪（2000-2099）各节气公式参数：(节气名, 月份, C 常数)
# day = int(y * 0.2422 + C) - int(y / 4)，y = 年份后两位
_SOLAR_TERMS = [
    ("小寒", 1, 5.4055),
    ("大寒", 1, 20.12),
    ("立春", 2, 3.87),
    ("雨水", 2, 18.73),
    ("惊蛰", 3, 5.63),
    ("春分", 3, 20.646),
    ("清明", 4, 4.81),
    ("谷雨", 4, 20.1),
    ("立夏", 5, 5.52),
    ("小满", 5, 21.04),
    ("芒种", 6, 5.678),
    ("夏至", 6, 21.37),
    ("小暑", 7, 7.108),
    ("大暑", 7, 22.83),
    ("立秋", 8, 7.5),
    ("处暑", 8, 23.13),
    ("白露", 9, 7.646),
    ("秋分", 9, 23.042),
    ("寒露", 10, 8.318),
    ("霜降", 10, 23.438),
    ("立冬", 11, 7.438),
    ("小雪", 11, 22.36),
    ("大雪", 12, 7.18),
    ("冬至", 12, 21.94),
]


def _term_date(year: int, month: int, c: float) -> date:
    """计算某年某节气的大致日期。"""
    y = year % 100
    day = int(y * 0.2422 + c) - int(y / 4)
    # 防御非法日期（个别边界）
    if day < 1:
        day = 1
    if day > 28:
        day = 28
    return date(year, month, day)


def get_solar_term(d: date) -> str:
    """返回给定日期所处的节气名。

    Args:
        d: 目标日期。

    Returns:
        24 节气名称之一。
    """
    terms = []
    for candidate_year in (d.year - 1, d.year):
        for name, month, c in _SOLAR_TERMS:
            try:
                terms.append((_term_date(candidate_year, month, c), name))
            except ValueError:
                continue
    terms.sort(key=lambda x: x[0])

    current = terms[0][1]
    for t_date, name in terms:
        if t_date <= d:
            current = name
        else:
            break
    return current


def get_region() -> int:
    """从配置读取当前地域类型，默认成渝(1)。"""
    raw = DB.get_setting("region_type")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            return 1
    return 1


def get_city() -> str:
    """从配置读取当前城市名，默认成都。"""
    return DB.get_setting("city") or "成都"


def detect(d: Optional[date] = None) -> dict:
    """综合识别地域与节气，返回完整上下文。

    Returns:
        字典：city / region_type / solar_term / date / health_tip /
        climate / health_core / recommend_food / forbid_food。
    """
    if d is None:
        d = date.today()

    city = get_city()
    region_type = get_region()

    # 手动节气覆盖优先
    override = DB.get_setting("solar_override") or ""
    if override:
        solar_term = override
    else:
        solar_term = get_solar_term(d)

    rule_rows = DB.query(
        "SELECT * FROM solar_health_rule WHERE solar_term = ? AND region_type = ?",
        [solar_term, region_type],
    )
    if not rule_rows:
        rule_rows = DB.query(
            "SELECT * FROM solar_health_rule WHERE solar_term = ?", [solar_term]
        )

    climate = ""
    health_core = ""
    recommend_food: list = []
    forbid_food: list = []
    if rule_rows:
        row = rule_rows[0]
        climate = row.get("climate", "")
        health_core = row.get("health_core", "")
        recommend_food = config.json_decode(row.get("recommend_food"))
        forbid_food = config.json_decode(row.get("forbid_food"))

    # 组装养生提示文案
    tips = [health_core] if health_core else []
    if recommend_food:
        tips.append("宜食：" + "、".join(recommend_food))
    if forbid_food:
        tips.append("忌食：" + "、".join(forbid_food))
    health_tip = "；".join(tips) if tips else "顺应时节，均衡饮食。"

    return {
        "city": city,
        "region_type": region_type,
        "region_name": config.REGION_TYPES.get(region_type, "其他"),
        "solar_term": solar_term,
        "date": d.isoformat(),
        "climate": climate,
        "health_core": health_core,
        "recommend_food": recommend_food,
        "forbid_food": forbid_food,
        "health_tip": health_tip,
    }
