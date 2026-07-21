"""主食材买菜清单聚合服务。"""

from __future__ import annotations

from typing import Any

from app import config
from app.database import DB

# 家庭通常已有的基础主食与调料不进入采购清单。
_EXCLUDED_INGREDIENTS: frozenset[str] = frozenset({
    "大米", "糯米", "面粉", "面条", "饺子皮", "馄饨皮", "面饼皮", "糯米粉",
    "葱", "大葱", "大蒜", "蒜", "生姜", "姜", "盐", "白糖", "冰糖",
    "醋", "酱油", "花椒", "干辣椒", "红辣椒", "辣椒油", "郫县豆瓣",
    "泡椒", "榨菜", "食用油", "料酒", "蚝油", "鸡精", "味精", "胡椒粉",
    "十三香", "五香粉", "孜然", "香油", "芝麻油", "蚝皇酱", "番茄酱",
})


def _load_category_map() -> dict[str, int]:
    """加载食材名称到分类编码的映射。"""
    rows: list[dict[str, Any]] = DB.query("SELECT name, category FROM ingredient")
    return {str(row["name"]): int(row["category"]) for row in rows}


def is_shopping_ingredient(name: str) -> bool:
    """判断食材是否为需要购买的主食材。"""
    normalized_name: str = str(name).strip()
    return bool(normalized_name) and normalized_name not in _EXCLUDED_INGREDIENTS


def convert_weight(grams: float, headcount: int = 1, factor: float = 1.0) -> dict[str, float]:
    """把食材重量换算为克和斤。"""
    del headcount
    total: float = max(0.0, float(grams)) * max(0.0, float(factor))
    return {"grams": round(total, 0), "jin": round(total / config.GRAMS_PER_JIN, 1)}


def build_shopping_list(meals: dict[str, list[dict[str, Any]]], plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """按分类聚合主菜、蔬菜、肉蛋等主食材，排除调料与基础主食。"""
    category_map: dict[str, int] = _load_category_map()
    accumulated: dict[str, float] = {}

    for meal_key in config.MEAL_KEYS:
        diners: list[dict[str, Any]] = plan.get(meal_key, []) or []
        factor: float = sum(
            config.AGE_PORTION.get(int(member.get("age_type", 4)), 1.0)
            for member in diners
        )
        if factor <= 0:
            continue
        for dish in meals.get(meal_key, []) or []:
            for ingredient in dish.get("main_ingredients", []) or []:
                name: str = str(ingredient.get("name", "")).strip()
                if not is_shopping_ingredient(name):
                    continue
                try:
                    grams: float = max(0.0, float(ingredient.get("grams", 0)))
                except (TypeError, ValueError):
                    grams = 0.0
                accumulated[name] = accumulated.get(name, 0.0) + grams * factor

    result: dict[str, list[dict[str, Any]]] = {}
    for name, grams in accumulated.items():
        category: int = category_map.get(name, 5)
        category_name: str = config.INGREDIENT_CATS.get(category, "其他")
        result.setdefault(category_name, []).append({
            "name": name,
            "grams": round(grams, 0),
            "jin": round(grams / config.GRAMS_PER_JIN, 1),
        })
    for items in result.values():
        items.sort(key=lambda item: str(item["name"]))
    return result
