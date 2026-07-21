"""种子数据加载器（首次启动幂等写入 SQLite）。

职责：
  * 若相应表为空，则批量写入 24 节气、约 80 道菜、约 80 条食材。
  * 已存在数据则跳过，保证可重复执行（幂等）。
  * 写入默认地域配置（成渝）。

遵循 Google Python 风格指南。
"""

from __future__ import annotations

from app import config
from app.database import DB
from app.data.seed_solar import SOLAR_SEED
from app.data.seed_dishes import DISH_SEED
from app.data.seed_ingredients import INGREDIENT_SEED


def _seed_table(table: str, rows: list[dict], unique_key: str) -> int:
    """向指定表写入种子行（按唯一键去重，已存在跳过）。

    Args:
        table: 表名。
        rows: 待写入的行字典列表。
        unique_key: 用于判重的字段名。

    Returns:
        本次新写入的行数。
    """
    existing = {r[unique_key] for r in DB.query(f"SELECT {unique_key} FROM {table}")}
    inserted = 0
    for row in rows:
        if row[unique_key] in existing:
            continue
        DB.upsert(table, row)
        inserted += 1
    return inserted


def run() -> dict:
    """执行全部种子加载，返回各表写入统计。

    Returns:
        形如 {'solar': n, 'dish': n, 'ingredient': n} 的统计字典。
    """
    solar_n = _seed_table(
        "solar_health_rule",
        [
            {
                "solar_term": s["solar_term"],
                "climate": s["climate"],
                "health_core": s["health_core"],
                "recommend_food": config.json_encode(s["recommend_food"]),
                "forbid_food": config.json_encode(s["forbid_food"]),
                "region_type": s["region_type"],
            }
            for s in SOLAR_SEED
        ],
        "solar_term",
    )

    dish_n = _seed_table(
        "dish_main",
        [
            {
                "dish_name": d["dish_name"],
                "dish_type": d["dish_type"],
                "region_type": d["region_type"],
                "spicy_level": d["taste"]["spicy"],
                "numb_level": d["taste"]["numb"],
                "acid_level": d["taste"]["acid"],
                "salt_level": d["taste"]["salt"],
                "sweet_level": d["taste"]["sweet"],
                "suit_age": config.json_encode(d["suit_age"]),
                "forbid_age": config.json_encode(d["forbid_age"]),
                "suit_health": config.json_encode(d["suit_health"]),
                "forbid_health": config.json_encode(d["forbid_health"]),
                "main_ingredients": config.json_encode(d["main_ingredients"]),
                "recipe_steps": config.json_encode(d["recipe_steps"]),
                "efficacy": d["efficacy"],
                "suitable_crowd": d["suitable_crowd"],
                "taboo_crowd": d["taboo_crowd"],
                "note": d["note"],
                "suit_solar": config.json_encode(d["suit_solar"]),
            }
            for d in DISH_SEED
        ],
        "dish_name",
    )

    ingredient_n = _seed_table(
        "ingredient",
        [
            {
                "name": i["name"],
                "category": i["category"],
                "unit": i["unit"],
                "alias": i["alias"],
                "is_vegetarian": i["is_vegetarian"],
            }
            for i in INGREDIENT_SEED
        ],
        "name",
    )

    # 默认地域配置（仅当缺失时写入）
    if DB.get_setting("city") is None:
        DB.set_setting("city", "成都")
        DB.set_setting("region_type", "1")
        DB.set_setting("solar_override", "")

    return {"solar": solar_n, "dish": dish_n, "ingredient": ingredient_n}
