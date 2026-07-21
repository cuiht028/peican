"""核心配餐算法引擎（每日三餐）。

严格按 PRD 2.4 / 2.5 优先级实现「数据驱动、非随机、可复现」的配餐：
  ① 忌口兜底剔除 → ② 特殊体质优先 → ③ 年龄适配 → ④ 口味折中
  → ⑤ 地域匹配 → ⑥ 节气加分 → ⑦ 按 day_of_year 确定性轮转选菜。

设计原则：
  * 纯函数、无状态，相同 (成员 + 日期) 输入结果稳定可复现。
  * 服务层统一返回 dict，空场景返回空结构而非 None。

遵循 Google Python 风格指南。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app import config
from app.database import DB
from app.models.dish import DishMain
from app.services.env_service import detect
from app.services.member_service import build_today_plan


def _load_dishes(region: int) -> list[dict]:
    """读取匹配地域的菜品池（region 或通用 2）。"""
    rows = DB.query(
        "SELECT * FROM dish_main WHERE region_type = ? OR region_type = 2 "
        "ORDER BY id ASC",
        [region],
    )
    dishes = []
    for r in rows:
        d = DishMain.from_row(r).to_dict()
        dishes.append(d)
    return dishes


def _load_veg_map() -> dict:
    """食材名 -> 是否素食（0/1）。"""
    rows = DB.query("SELECT name, is_vegetarian FROM ingredient")
    return {r["name"]: int(r["is_vegetarian"]) for r in rows}


def _build_constraints(dining: list[dict], rule: dict) -> dict:
    """聚合一餐的约束集合。"""
    forbidden_items: set = set(rule.get("forbid_food", []) or [])
    avoid_cats: set = set()
    is_vegetarian = False
    health_needs: set = set()
    present_ages: set = set()
    taste_sum = {d: 0 for d in config.TASTE_DIMS}
    taste_cnt = 0

    for m in dining:
        avoid = m.get("avoid_food", {}) or {}
        for it in avoid.get("items", []) or []:
            forbidden_items.add(it)
        for c in avoid.get("categories", []) or []:
            avoid_cats.add(c)
        if avoid.get("vegetarian"):
            is_vegetarian = True
        for h in m.get("health_tag", []) or []:
            health_needs.add(h)
        present_ages.add(m.get("age_type", 4))
        taste = m.get("taste", {}) or {}
        for d in config.TASTE_DIMS:
            taste_sum[d] += int(taste.get(d, config.BASE_TASTE[d]))
        taste_cnt += 1

    if taste_cnt > 0:
        taste_target = {
            d: max(1, min(4, round(taste_sum[d] / taste_cnt)))
            for d in config.TASTE_DIMS
        }
    else:
        taste_target = dict(config.BASE_TASTE)

    return {
        "forbidden_items": forbidden_items,
        "avoid_cats": avoid_cats,
        "is_vegetarian": is_vegetarian,
        "health_needs": health_needs,
        "present_ages": present_ages,
        "taste_target": taste_target,
    }


def _hard_eliminate(dish: dict, ctx: dict, veg_map: dict, strict: bool) -> bool:
    """硬剔除判定。strict=True 时包含体质 / 年龄剔除。

    Returns:
        True 表示应剔除。
    """
    # ① 忌口：主材命中忌食食材
    ing_names = {ing["name"] for ing in dish.get("main_ingredients", [])}
    if ing_names & ctx["forbidden_items"]:
        return True

    # 素食冲突
    if ctx["is_vegetarian"]:
        if dish["dish_type"] == 3:  # 荤菜整类剔除
            return True
        if any(veg_map.get(n, 1) == 0 for n in ing_names):
            return True

    if strict:
        # ② 特殊体质禁忌
        if set(dish.get("forbid_health", [])) & ctx["health_needs"]:
            return True
        # ③ 年龄禁忌
        if set(dish.get("forbid_age", [])) & ctx["present_ages"]:
            return True
    return False


def _score_dish(dish: dict, ctx: dict, rule: dict, region: int, meal_key: str) -> int:
    """计算菜品综合得分（越高越优）。"""
    score = 0
    taste = dish.get("taste", {})
    suit_health = set(dish.get("suit_health", []))
    suit_age = set(dish.get("suit_age", []))
    ing_names = {ing["name"] for ing in dish.get("main_ingredients", [])}

    # ② 体质匹配加分
    matched_health = ctx["health_needs"] & suit_health
    score += min(len(matched_health) * 3, 9)

    # ③ 年龄匹配加分
    matched_age = ctx["present_ages"] & suit_age
    score += min(len(matched_age) * 2, 8)

    # ④ 口味距离加分（距离越小越好）
    dist = sum(abs(taste.get(d, 2) - ctx["taste_target"][d]) for d in config.TASTE_DIMS)
    score += max(0, 16 - dist)

    # ⑤ 地域匹配
    if dish["region_type"] == region:
        score += 5
    elif dish["region_type"] == 2:
        score += 2
    else:
        score -= 3

    # ⑥ 节气加分
    term = rule.get("solar_term", "")
    if term and term in dish.get("suit_solar", []):
        score += 5
    rec_food = set(rule.get("recommend_food", []) or [])
    rec_hit = len(ing_names & rec_food)
    score += min(rec_hit * 2, 6)

    # 忌口分类软惩罚（香辛类 / 调味类）
    if "香辛类" in ctx["avoid_cats"] and (taste.get("spicy", 2) >= 3 or taste.get("numb", 2) >= 3):
        score -= 2
    if "调味类" in ctx["avoid_cats"] and (taste.get("salt", 2) >= 3 or taste.get("sweet", 2) >= 3):
        score -= 2

    # 三餐差异化
    if meal_key == "breakfast":
        if "婴幼儿软烂" in suit_health or "老人养胃" in suit_health:
            score += 3
        if taste.get("spicy", 2) <= 2 and taste.get("numb", 2) <= 2:
            score += 2
    elif meal_key == "lunch":
        if dish["dish_type"] in (2, 3):
            score += 1
    elif meal_key == "dinner":
        if "低脂" in suit_health or "老人养胃" in suit_health:
            score += 3
        if taste.get("spicy", 2) <= 2:
            score += 1

    return score


def _select(pool: list[dict], count: int, offset: int) -> list[dict]:
    """按综合分降序 + day_of_year 轮转确定性选菜。"""
    if not pool:
        return []
    pool_sorted = sorted(pool, key=lambda x: (-x["_score"], x["id"]))
    if len(pool_sorted) <= count:
        return [p["dish"] for p in pool_sorted]
    rotated = pool_sorted[offset:] + pool_sorted[:offset]
    return [p["dish"] for p in rotated[:count]]


def generate_daily_meals(
    d: date,
    region: int,
    plan: Optional[dict] = None,
) -> dict:
    """生成每日三餐配餐结果。

    Args:
        d: 目标日期。
        region: 地域类型（1 成渝 / 2 其他）。
        plan: 今日用餐计划（见 build_today_plan）；缺省自动构建。

    Returns:
        字典：{'term', 'health_tip', 'recommend_food', 'forbid_food',
              'meals': {'breakfast':[dish_dict], 'lunch':[...], 'dinner':[...]}}。
    """
    if plan is None:
        plan = build_today_plan()

    env = detect(d)
    rule = {
        "solar_term": env["solar_term"],
        "recommend_food": env.get("recommend_food", []),
        "forbid_food": env.get("forbid_food", []),
    }

    # 无任何成员用餐时，直接返回空结构（需求：无成员返回空结构，不崩溃）。
    if all(not plan.get(meal) for meal in config.MEAL_KEYS):
        return {
            "term": env["solar_term"],
            "health_tip": env["health_tip"],
            "recommend_food": rule["recommend_food"],
            "forbid_food": rule["forbid_food"],
            "meals": {meal: [] for meal in config.MEAL_KEYS},
        }

    all_dishes = _load_dishes(region)
    veg_map = _load_veg_map()
    day_of_year = d.timetuple().tm_yday

    meals_result: dict = {meal: [] for meal in config.MEAL_KEYS}

    for meal_key in config.MEAL_KEYS:
        dining = plan.get(meal_key, []) or []
        ctx = _build_constraints(dining, rule)

        # V1.1: 按每餐实际用餐人数动态查表确定菜品数量
        headcount = plan.get("stats", {}).get(meal_key, {}).get("headcount", 0)
        if headcount == 0:
            continue  # 0人跳过该餐
        banquet = plan.get("banquet", False)
        structure = config.get_meal_structure(headcount, banquet=banquet)[meal_key]

        for dish_type in (1, 2, 3, 4):
            count = structure.get(dish_type, 0)
            if count <= 0:
                continue
            candidates = [x for x in all_dishes if x["dish_type"] == dish_type]

            # 严格筛选 + 打分
            strict_pool = []
            for dish in candidates:
                if _hard_eliminate(dish, ctx, veg_map, strict=True):
                    continue
                sc = _score_dish(dish, ctx, rule, region, meal_key)
                strict_pool.append({"dish": dish, "_score": sc, "id": dish["id"]})

            # 兜底：严格池为空时仅按忌口 / 素食放宽
            pool = strict_pool
            if not pool:
                for dish in candidates:
                    if _hard_eliminate(dish, ctx, veg_map, strict=False):
                        continue
                    sc = _score_dish(dish, ctx, rule, region, meal_key)
                    pool.append({"dish": dish, "_score": sc, "id": dish["id"]})

            offset = day_of_year % max(1, len(pool)) if pool else 0
            selected = _select(pool, count, offset)
            meals_result[meal_key].extend(selected)

    return {
        "term": env["solar_term"],
        "health_tip": env["health_tip"],
        "recommend_food": rule["recommend_food"],
        "forbid_food": rule["forbid_food"],
        "meals": meals_result,
    }


def replace_dish(
    d: date,
    region: int,
    plan: Optional[dict],
    meal_key: str,
    old_dish_id: int,
    current_dish_ids: set,
) -> Optional[dict]:
    """替换单道菜，返回同类型的新菜品dict（已过忌口筛选），无候选返回None。"""
    all_dishes = _load_dishes(region)
    veg_map = _load_veg_map()

    old_dish = next((x for x in all_dishes if x["id"] == old_dish_id), None)
    if not old_dish:
        return None

    env = detect(d)
    rule = {
        "solar_term": env["solar_term"],
        "recommend_food": env.get("recommend_food", []),
        "forbid_food": env.get("forbid_food", []),
    }
    dining = plan.get(meal_key, []) or [] if plan else []
    ctx = _build_constraints(dining, rule)

    # 严格筛选
    candidates = []
    for dish in all_dishes:
        if dish["dish_type"] != old_dish["dish_type"]:
            continue
        if dish["id"] in current_dish_ids:
            continue
        if _hard_eliminate(dish, ctx, veg_map, strict=True):
            continue
        candidates.append(dish)

    # 兜底放宽
    if not candidates:
        for dish in all_dishes:
            if dish["dish_type"] != old_dish["dish_type"]:
                continue
            if dish["id"] in current_dish_ids:
                continue
            if _hard_eliminate(dish, ctx, veg_map, strict=False):
                continue
            candidates.append(dish)

    if not candidates:
        return None

    day_of_year = d.timetuple().tm_yday
    offset = (day_of_year + old_dish_id) % len(candidates)
    return candidates[offset]
