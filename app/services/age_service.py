"""年龄判定服务。

将「出生年月 (YYYY-MM)」转换为年龄层级（1 婴幼儿 / 2 儿童 / 3 少年 /
4 中青年 / 5 老年），供配餐算法做年龄适配。
"""

from __future__ import annotations

from datetime import date

from app import config


def calc_age_type(birth_ym: str, today: date | None = None) -> int:
    """根据出生年月计算年龄层级。

    Args:
        birth_ym: 出生年月，格式 ``YYYY-MM``。
        today: 参考日期，默认取当天。

    Returns:
        年龄层级整数 1-5；输入非法时回退为 4（中青年）。
    """
    if today is None:
        today = date.today()
    if not birth_ym or len(birth_ym) < 7:
        return 4
    try:
        y, m = birth_ym.split("-")[:2]
        by = int(y)
        bm = int(m)
    except (ValueError, AttributeError):
        return 4
    if by < 1900 or bm < 1 or bm > 12:
        return 4

    # 周岁计算（未到生日月份则减一岁）
    age = today.year - by
    if (today.month, today.day) < (bm, 1):
        age -= 1
    if age < 0:
        age = 0

    if age < 3:
        return 1   # 婴幼儿
    if age < 7:
        return 2   # 儿童
    if age < 18:
        return 3   # 少年
    if age < 60:
        return 4   # 中青年
    return 5       # 老年


def age_label(age_type: int) -> str:
    """返回年龄层级中文名。"""
    return config.AGE_TYPES.get(age_type, "未知")
