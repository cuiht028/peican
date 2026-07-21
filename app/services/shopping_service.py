"""买菜清单服务。

根据配餐结果与今日用餐计划，把各菜主材按「每人份克重 × 用餐人数 ×
年龄段系数」线性汇总，并按食材分类输出「克 / 斤」双单位清单。

重量换算：1 斤 = 500 克；年龄段系数见 config.AGE_PORTION。
"""

from __future__ import annotations

from typing import Optional

from app import config
from app.database import DB


def _load_category_map() -> dict:
    """食材名 -> 分类编码。"""
    rows = DB.query("SELECT name, category FROM ingredient")
    return {r["name"]: int(r["category"]) for r in rows}


def convert_weight(grams: float, headcount: int = 1, factor: float = 1.0) -> dict:
    """重量换算辅助：返回克与斤。

    Args:
        grams: 单人基准克重。
        headcount: 用餐人数。
        factor: 年龄段系数合计（已含人数与减量系数）。

    Returns:
        {'grams': 总克数, 'jin': 总斤数}（斤保留 1 位小数）。
    """
    total = grams * factor
    return {
        "grams": round(total, 0),
        "jin": round(total / config.GRAMS_PER_JIN, 1),
    }


def build_shopping_list(meals: dict, plan: dict) -> dict:
    """聚合买菜清单。

    Args:
        meals: 配餐结果中的 meals 字段（早 / 午 / 晚菜品列表）。
        plan: build_today_plan() 输出的计划（含各餐用餐成员）。

    Returns:
        按分类聚合的清单：{'蔬菜':[{name,grams,jin}], '肉类':[...], ...}。
        始终返回字典（可能为空）。
    """
    cat_map = _load_category_map()
    accum: dict = {}  # name -> 总克数

    for meal_key in config.MEAL_KEYS:
        diners = plan.get(meal_key, []) or []
        factor = sum(
            config.AGE_PORTION.get(m.get("age_type", 4), 1.0) for m in diners
        )
        if factor <= 0:
            continue
        for dish in meals.get(meal_key, []) or []:
            for ing in dish.get("main_ingredients", []) or []:
                name = ing.get("name", "")
                grams = ing.get("grams", 0)
                if not name:
                    continue
                accum[name] = accum.get(name, 0) + grams * factor

    result: dict = {}
    for name, grams in accum.items():
        cat = cat_map.get(name, 5)
        cat_name = config.INGREDIENT_CATS.get(cat, "其他")
        entry = {
            "name": name,
            "grams": round(grams, 0),
            "jin": round(grams / config.GRAMS_PER_JIN, 1),
        }
        result.setdefault(cat_name, []).append(entry)

    for items in result.values():
        items.sort(key=lambda x: x["name"])

    return result
