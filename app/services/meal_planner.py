"""核心配餐算法引擎（每日三餐）。

本模块基于成员忌口、健康需求、地域、节气和近期生成记录提供可复现的
三餐推荐。它不修改数据库 schema；近期多样性记录仅保存在进程内，因此不
会将临时推荐结果写入用户数据。
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import random
from typing import Any, Optional

from app import config
from app.database import DB
from app.models.dish import DishMain
from app.services.env_service import detect
from app.services.member_service import build_today_plan

# 最近生成的每日方案。key 为日期，value 为完整 meals dict。仅用于同一进程内
# 的连续推荐去重，既不改变数据库，也不会影响相同日期的稳定结果。
_RECENT_MEAL_HISTORY: dict[date, dict[str, list[dict[str, Any]]]] = {}
_HISTORY_WINDOW_DAYS: int = 14
_HISTORY_MAX_DATES: int = 45

# 早餐不适合出现的重油、重辣或大份主菜关键词。关键词只用作安全兜底；口味
# 等级仍是主要判定依据，避免依赖不可靠的自由文本标签。
_BREAKFAST_HEAVY_TOKENS: tuple[str, ...] = (
    "毛血旺", "冒菜", "肥肠鱼", "肥肠", "水煮", "辣子", "麻辣", "香辣",
    "回锅", "红烧肉", "粉蒸", "烧白", "烤鸭", "卤拼", "油焖", "郡肝",
)
# 用户明确点名不宜出现在早餐的菜品（即便属素菜/小菜类型也不上早餐）。
_BREAKFAST_EXCLUDE_NAMES: tuple[str, ...] = (
    "豆花饭", "皮蛋拌豆腐", "凉拌猪耳朵",
)

# 早餐粥/羹/豆花优先（仅 type=5 早餐主品生效）
_BREAKFAST_PORRIDGE_TOKENS: tuple[str, ...] = ("粥", "羹", "豆花")

# 早餐饼类优先（type=5 优先）
_BREAKFAST_PANCAKE_TOKENS: tuple[str, ...] = (
    "饼", "锅贴", "卷饼", "锅盔", "煎饼", "煎包", "小笼", "包子", "馒头",
    "豆浆", "稀饭", "糍",
)

# 早餐粗粮
_BREAKFAST_GRAIN_TOKENS: tuple[str, ...] = (
    "粗粮", "小米", "玉米", "荞麦", "高粱", "红薯", "紫米", "薏米",
)

# 早餐下粥小菜（凉拌/腌制/小菜），优先级高于热炒蔬菜
_BREAKFAST_SMALL_DISH_TOKENS: tuple[str, ...] = (
    "凉拌", "拌", "小菜", "萝卜干", "泡菜", "酱", "花生",
    "炝拌", "糖醋", "麻辣萝卜", "拌黄瓜", "拌豆腐", "拌海带",
    "拌莴笋", "拌土豆", "拌藕",
)

# 早餐热炒蔬菜（优先级较低，仅在无小菜时补位）
_BREAKFAST_WOK_TOKENS: tuple[str, ...] = (
    "清炒", "炒蛋", "炒", "灼", "蒜蓉", "蒜泥", "素炒",
)

# 早餐饼类加分（type=5 专用主品）
_BREAKFAST_PANCAKE_BONUS: int = 16

# 早下粥小菜加分（type=2 素菜槽位）
_BREAKFAST_SMALL_DISH_BONUS: int = 20

# 早餐热炒加分（type=2 素菜槽位，仅补位）
_BREAKFAST_WOK_BONUS: int = 5

# 早餐稀饭/羹加分（type=5）
_BREAKFAST_PORRIDGE_BONUS: int = 22

# 早餐粗粮加分（type=5）
_BREAKFAST_GRAIN_BONUS: int = 14

# 早餐鸡蛋/豆腐/豆干加分（通用）
_BREAKFAST_PROTEIN_BONUS: int = 6

# 餐次间轮换随机种子，基于日期 + rotation_seed 生成
_ROTATION_RANDOM: random.Random = random.Random()

# 温度随机化噪声幅度（0-1），影响同分候选排序的随机性
_SCORE_NOISE_FACTOR: float = 0.3

# 节气与季节对应（用于菜品 `suit_solar` 批量匹配）
_SOLAR_BY_SEASON: dict[str, list[str]] = {
    "春": ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨"],
    "夏": ["立夏", "小满", "芒种", "夏至", "小暑", "大暑"],
    "秋": ["立秋", "处暑", "白露", "秋分", "寒露", "霜降"],
    "冬": ["立冬", "小雪", "大雪", "冬至", "小寒", "大寒"],
}

# 菜品名中的季节关键词 → 对应节气
_SEASON_KEYWORDS: dict[str, list[str]] = {
    "春": ["韭菜", "荠菜", "春笋", "香椿", "豆苗", "蚕豆"],
    "夏": ["苦瓜", "冬瓜", "丝瓜", "黄瓜", "绿豆", "莲子", "西瓜", "荷叶"],
    "秋": ["梨", "银耳", "百合", "莲藕", "银耳", "南瓜", "板栗", "柿子"],
    "冬": ["羊肉", "萝卜", "白菜", "山药", "红薯", "土豆", "洋葱"],
}

_AROMATIC_INGREDIENTS: set[str] = {
    "葱", "大蒜", "蒜", "生姜", "花椒", "红辣椒", "干辣椒", "泡椒",
    "酱油", "醋", "白糖", "郫县豆瓣", "辣椒油", "盐",
}


def _load_dishes(region: int) -> list[dict[str, Any]]:
    """读取匹配地域的菜品池（指定地域或通用地域）。"""
    rows: list[dict[str, Any]] = DB.query(
        "SELECT * FROM dish_main WHERE region_type = ? OR region_type = 2 "
        "ORDER BY id ASC",
        [region],
    )
    return [DishMain.from_row(row).to_dict() for row in rows]


def _load_veg_map() -> dict[str, int]:
    """读取食材名到是否素食的映射。"""
    rows: list[dict[str, Any]] = DB.query("SELECT name, is_vegetarian FROM ingredient")
    return {str(row["name"]): int(row["is_vegetarian"]) for row in rows}


def _build_constraints(dining: list[dict[str, Any]], rule: dict[str, Any]) -> dict[str, Any]:
    """聚合一餐的忌口、年龄、健康和口味约束。"""
    forbidden_items: set[str] = set(rule.get("forbid_food", []) or [])
    avoid_categories: set[str] = set()
    is_vegetarian: bool = False
    health_needs: set[str] = set()
    present_ages: set[int] = set()
    taste_sum: dict[str, int] = {dimension: 0 for dimension in config.TASTE_DIMS}
    taste_count: int = 0

    for member in dining:
        avoid_food: dict[str, Any] = member.get("avoid_food", {}) or {}
        forbidden_items.update(avoid_food.get("items", []) or [])
        avoid_categories.update(avoid_food.get("categories", []) or [])
        is_vegetarian = is_vegetarian or bool(avoid_food.get("vegetarian", False))
        health_needs.update(member.get("health_tag", []) or [])
        present_ages.add(int(member.get("age_type", 4)))
        taste: dict[str, Any] = member.get("taste", {}) or {}
        for dimension in config.TASTE_DIMS:
            taste_sum[dimension] += int(taste.get(dimension, config.BASE_TASTE[dimension]))
        taste_count += 1

    taste_target: dict[str, int]
    if taste_count:
        taste_target = {
            dimension: max(1, min(4, round(taste_sum[dimension] / taste_count)))
            for dimension in config.TASTE_DIMS
        }
    else:
        taste_target = dict(config.BASE_TASTE)

    return {
        "forbidden_items": forbidden_items,
        "avoid_categories": avoid_categories,
        "is_vegetarian": is_vegetarian,
        "health_needs": health_needs,
        "present_ages": present_ages,
        "taste_target": taste_target,
    }


def _ingredient_names(dish: dict[str, Any]) -> set[str]:
    """返回菜品主材名称集合，容忍旧数据中的不完整食材条目。"""
    ingredients: list[dict[str, Any]] = dish.get("main_ingredients", []) or []
    return {
        str(ingredient.get("name", ""))
        for ingredient in ingredients
        if ingredient.get("name")
    }


def _primary_ingredients(dish: dict[str, Any]) -> set[str]:
    """返回用于同餐去重的主要食材，忽略调味料。"""
    return _ingredient_names(dish) - _AROMATIC_INGREDIENTS


def _hard_eliminate(
    dish: dict[str, Any],
    constraints: dict[str, Any],
    veg_map: dict[str, int],
    strict: bool,
) -> bool:
    """判断菜品是否因硬性约束被剔除。

    ``strict=False`` 只放宽年龄和健康适配，绝不放宽用户忌口与素食要求。
    """
    ingredient_names: set[str] = _ingredient_names(dish)
    if ingredient_names & constraints["forbidden_items"]:
        return True

    if constraints["is_vegetarian"]:
        if int(dish.get("dish_type", 2)) == 3:
            return True
        if any(veg_map.get(name, 1) == 0 for name in ingredient_names):
            return True

    if strict:
        if set(dish.get("forbid_health", []) or []) & constraints["health_needs"]:
            return True
        if set(dish.get("forbid_age", []) or []) & constraints["present_ages"]:
            return True
    return False


def _is_breakfast_unsuitable(dish: dict[str, Any]) -> bool:
    """返回早餐是否应排除该菜品。

    早餐禁止明确列出的重口主菜，并将重辣、重麻菜作为不可选项。轻蛋白菜
    仍可作为候选不足时的补位，保证菜库较小时能产出完整结果。
    """
    dish_name: str = str(dish.get("dish_name", ""))
    taste: dict[str, Any] = dish.get("taste", {}) or {}
    if any(token in dish_name for token in _BREAKFAST_HEAVY_TOKENS):
        return True
    if dish_name in _BREAKFAST_EXCLUDE_NAMES:
        return True
    return int(taste.get("spicy", 2)) >= 3 or int(taste.get("numb", 2)) >= 3


def _daily_tiebreaker(
    target_date: date,
    dish_id: int,
    meal_key: str,
    rotation_seed: int = 0,
) -> int:
    """为日期、餐次和菜品生成稳定的非随机排序值。"""
    raw_key: str = f"{target_date.isoformat()}:{meal_key}:{dish_id}:{rotation_seed}"
    digest: bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def _history_penalty(dish_id: int, target_date: date) -> int:
    """计算最近已生成方案的重复惩罚，越近的日期惩罚越高。"""
    penalty: int = 0
    lower_bound: date = target_date - timedelta(days=_HISTORY_WINDOW_DAYS)
    for history_date, meals in _RECENT_MEAL_HISTORY.items():
        if history_date < lower_bound or history_date >= target_date:
            continue
        elapsed_days: int = (target_date - history_date).days
        for dishes in meals.values():
            if any(int(item.get("id", 0)) == dish_id for item in dishes):
                penalty += max(2, 13 - elapsed_days)
                break
    return penalty


def _breakfast_preference_bonus(dish: dict[str, Any]) -> int:
    """为粥、饼类及下粥小菜计算早餐优先级加分。

    分层优先级：
    1. 稀饭/粥/羹/豆花（type=5 主品）：最高
    2. 饼类/包子/馒头/豆浆（type=5 主品）：次高
    3. 粗粮粥（type=5 主品）：中等
    4. 下粥小菜（type=2 素菜槽）：高
    5. 热炒蔬菜（type=2 素菜槽，补位）：低
    """
    dish_name: str = str(dish.get("dish_name", ""))
    dish_type: int = int(dish.get("dish_type", 0))
    ingredient_names: set[str] = _ingredient_names(dish)
    bonus: int = 0

    # type=5 早餐主品槽位
    if dish_type == 5:
        if any(token in dish_name for token in _BREAKFAST_PORRIDGE_TOKENS):
            bonus += _BREAKFAST_PORRIDGE_BONUS  # 粥/羹/豆花：最高
        if any(token in dish_name for token in _BREAKFAST_PANCAKE_TOKENS):
            bonus += _BREAKFAST_PANCAKE_BONUS  # 饼类/包子/馒头/豆浆
        if any(token in dish_name for token in _BREAKFAST_GRAIN_TOKENS):
            bonus += _BREAKFAST_GRAIN_BONUS  # 粗粮

    # type=2 素菜槽位：优先下粥小菜，其次热炒
    elif dish_type == 2:
        if any(token in dish_name for token in _BREAKFAST_SMALL_DISH_TOKENS):
            bonus += _BREAKFAST_SMALL_DISH_BONUS
        if any(token in dish_name for token in _BREAKFAST_WOK_TOKENS):
            bonus += _BREAKFAST_WOK_BONUS

    if {"鸡蛋", "豆腐", "豆干", "黄豆"} & ingredient_names:
        bonus += _BREAKFAST_PROTEIN_BONUS
    if dish_type == 4:
        bonus += 3
    return bonus


def _score_dish(
    dish: dict[str, Any],
    constraints: dict[str, Any],
    rule: dict[str, Any],
    region: int,
    meal_key: str,
    target_date: date,
    rotation_seed: int = 0,
    avoided_ids: Optional[set[int]] = None,
) -> int:
    """计算菜品综合分，分数越高优先级越高。

    新增特性：
    - 温度随机化：在评分后加入基于日期的随机噪声，让同分菜品有轮换空间
    - 节气匹配增强：根据菜品主材关键词自动推断季节适配
    """
    score: int = 0
    taste: dict[str, Any] = dish.get("taste", {}) or {}
    suit_health: set[str] = set(dish.get("suit_health", []) or [])
    suit_age: set[int] = set(dish.get("suit_age", []) or [])
    ingredient_names: set[str] = _ingredient_names(dish)
    dish_name: str = str(dish.get("dish_name", ""))

    # 健康适配
    score += min(len(constraints["health_needs"] & suit_health) * 3, 9)
    score += min(len(constraints["present_ages"] & suit_age) * 2, 8)

    # 口味匹配
    taste_distance: int = sum(
        abs(int(taste.get(dimension, 2)) - constraints["taste_target"][dimension])
        for dimension in config.TASTE_DIMS
    )
    score += max(0, 16 - taste_distance)

    # 地域偏好
    if int(dish.get("region_type", 2)) == region:
        score += 5
    elif int(dish.get("region_type", 2)) == 2:
        score += 2
    else:
        score -= 3

    # 节气匹配：显式 suit_solar + 关键词推断
    solar_term: str = str(rule.get("solar_term", ""))
    explicit_solar: list[str] = dish.get("suit_solar", []) or []
    is_solar_match: bool = solar_term in explicit_solar
    if not is_solar_match:
        # 根据主材关键词推断季节适配
        inferred_season: Optional[str] = None
        for season, keywords in _SEASON_KEYWORDS.items():
            if any(kw in ingredient_names for kw in keywords):
                inferred_season = season
                break
        if inferred_season and solar_term in _SOLAR_BY_SEASON.get(inferred_season, []):
            is_solar_match = True

    if is_solar_match:
        # 午晚餐节气加分更高，早餐保持粥/饼优先级
        score += 12 if meal_key in ("lunch", "dinner") else 5

    # 推荐食材加分
    recommended_food: set[str] = set(rule.get("recommend_food", []) or [])
    score += min(len(ingredient_names & recommended_food) * 3, 9)

    # 忌口降权
    if "香辛类" in constraints["avoid_categories"]:
        if int(taste.get("spicy", 2)) >= 3 or int(taste.get("numb", 2)) >= 3:
            score -= 2
    if "调味类" in constraints["avoid_categories"]:
        if int(taste.get("salt", 2)) >= 3 or int(taste.get("sweet", 2)) >= 3:
            score -= 2

    # 餐次特定加分
    if meal_key == "breakfast":
        score += _breakfast_preference_bonus(dish)
        if "婴幼儿软烂" in suit_health or "老人养胃" in suit_health:
            score += 3
    elif meal_key == "dinner":
        if "低脂" in suit_health or "老人养胃" in suit_health:
            score += 3
        if int(taste.get("spicy", 2)) <= 2:
            score += 1

    # 历史重复惩罚
    dish_id: int = int(dish.get("id", 0))
    score -= _history_penalty(dish_id, target_date)

    # 重配降权
    if avoided_ids and dish_id in avoided_ids:
        score -= 50

    return score


def _apply_rotation_noise(
    candidates: list[dict[str, Any]],
    target_date: date,
    meal_key: str,
    rotation_seed: int = 0,
) -> list[dict[str, Any]]:
    """为候选池添加温度随机化噪声，实现菜品轮换。

    使用基于日期、餐次和 rotation_seed 的确定性随机，确保：
    1. 同一日期同一餐次的结果稳定可复现
    2. 不同日期之间有明显变化
    3. 高分菜品不会永远占据首位
    """
    # 确定性随机种子
    rng = random.Random()
    rng.seed(f"{target_date.isoformat()}:{meal_key}:{rotation_seed}")

    # 找出最高分作为基准
    scores = [int(c["_score"]) for c in candidates]
    if not scores:
        return candidates
    max_score = max(scores)
    min_score = min(scores)
    spread = max(1, max_score - min_score)

    # 对非最高分的菜品施加噪声，让同分/接近同分的菜品有机会轮换
    for candidate in candidates:
        current = int(candidate["_score"])
        if current < max_score:
            # 分数差距越小，噪声影响越大（同分菜几乎完全随机排列）
            distance_from_top = (max_score - current) / spread
            noise_amplitude = spread * _SCORE_NOISE_FACTOR * (1 - distance_from_top)
            # 为每个菜品生成不同的噪声值
            noise = rng.gauss(0, noise_amplitude)
            candidate["_score"] = current + int(noise)

    return candidates


def _to_scored_candidate(
    dish: dict[str, Any],
    constraints: dict[str, Any],
    rule: dict[str, Any],
    region: int,
    meal_key: str,
    target_date: date,
    rotation_seed: int = 0,
    avoided_ids: Optional[set[int]] = None,
) -> dict[str, Any]:
    """包装菜品及其分数、稳定排序值。"""
    dish_id: int = int(dish.get("id", 0))
    return {
        "dish": dish,
        "_score": _score_dish(dish, constraints, rule, region, meal_key, target_date, rotation_seed, avoided_ids),
        "id": dish_id,
        "_rank": _daily_tiebreaker(target_date, dish_id, meal_key, rotation_seed),
    }


def _compatible_with_meal(dish: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    """避免同餐重复菜、重复主料及同类菜品堆叠。"""
    dish_id: int = int(dish.get("id", 0))
    selected_ids: set[int] = {int(item.get("id", 0)) for item in selected}
    if dish_id in selected_ids:
        return False

    candidate_main: set[str] = _primary_ingredients(dish)
    for selected_dish in selected:
        if candidate_main & _primary_ingredients(selected_dish):
            return False
    return True


def _select(
    pool: list[dict[str, Any]],
    count: int,
    offset: int = 0,
    selected: Optional[list[dict[str, Any]]] = None,
    excluded_ids: Optional[set[int]] = None,
) -> list[dict[str, Any]]:
    """从候选池确定性选菜，并在候选充足时执行同餐多样性约束。

    ``offset`` 保留为兼容旧内部调用；实际排序由日期稳定 hash 决定，不依赖随机。
    当多样性约束使候选不足时，会自动放宽该软约束，确保菜库较小时仍可配餐。
    """
    del offset
    if count <= 0 or not pool:
        return []

    base_selected: list[dict[str, Any]] = list(selected or [])
    blocked_ids: set[int] = set(excluded_ids or set())
    ordered: list[dict[str, Any]] = sorted(
        pool,
        key=lambda candidate: (-int(candidate["_score"]), int(candidate["_rank"]), int(candidate["id"])),
    )
    picked: list[dict[str, Any]] = []

    for candidate in ordered:
        dish: dict[str, Any] = candidate["dish"]
        if int(candidate["id"]) in blocked_ids:
            continue
        if _compatible_with_meal(dish, base_selected + picked):
            picked.append(dish)
        if len(picked) == count:
            return picked

    # 候选池不足时只放宽「去重」软约束，仍保持所有硬性忌口过滤。
    used_ids: set[int] = {int(item.get("id", 0)) for item in base_selected + picked}
    for candidate in ordered:
        dish: dict[str, Any] = candidate["dish"]
        dish_id: int = int(candidate["id"])
        if dish_id in blocked_ids or dish_id in used_ids:
            continue
        picked.append(dish)
        used_ids.add(dish_id)
        if len(picked) == count:
            break
    return picked


def _candidate_pool(
    candidates: list[dict[str, Any]],
    constraints: dict[str, Any],
    veg_map: dict[str, int],
    rule: dict[str, Any],
    region: int,
    meal_key: str,
    target_date: date,
    count: int,
    rotation_seed: int = 0,
    avoided_ids: Optional[set[int]] = None,
) -> list[dict[str, Any]]:
    """构建严格优先、候选不足时放宽年龄/健康约束的候选池。"""
    strict_pool: list[dict[str, Any]] = []
    relaxed_pool: list[dict[str, Any]] = []
    for dish in candidates:
        if meal_key == "breakfast" and _is_breakfast_unsuitable(dish):
            continue
        if not _hard_eliminate(dish, constraints, veg_map, strict=False):
            relaxed_pool.append(
                _to_scored_candidate(dish, constraints, rule, region, meal_key, target_date, rotation_seed, avoided_ids)
            )
        if not _hard_eliminate(dish, constraints, veg_map, strict=True):
            strict_pool.append(
                _to_scored_candidate(dish, constraints, rule, region, meal_key, target_date, rotation_seed, avoided_ids)
            )

    if len(strict_pool) >= count:
        # 候选充足：加入温度噪声实现轮换
        return _apply_rotation_noise(strict_pool, target_date, meal_key, rotation_seed)
    strict_ids: set[int] = {int(item["id"]) for item in strict_pool}
    pool = strict_pool + [item for item in relaxed_pool if int(item["id"]) not in strict_ids]
    return _apply_rotation_noise(pool, target_date, meal_key, rotation_seed)


def _is_noodle_staple(dish: dict[str, Any]) -> bool:
    """判断主食是否为适合午晚餐的一碗式面食/粉类。"""
    if int(dish.get("dish_type", 0)) != 1:
        return False
    dish_name: str = str(dish.get("dish_name", ""))
    return any(token in dish_name for token in config.NOODLE_STAPLE_TOKENS)


def _prefer_lunch_dinner_staples(
    candidates: list[dict[str, Any]],
    meal_key: str,
) -> list[dict[str, Any]]:
    """午晚餐优先候选中的饺子、面条、粉等面食，候选不足时保持可回退。"""
    if meal_key not in ("lunch", "dinner"):
        return candidates
    noodles: list[dict[str, Any]] = [
        candidate for candidate in candidates if _is_noodle_staple(candidate["dish"])
    ]
    return noodles or candidates


def _adjust_structure_for_noodle(
    structure: dict[int, int],
    staple: Optional[dict[str, Any]],
    meal_key: str,
) -> dict[int, int]:
    """面食主食自带肉菜或配料时减少配菜，仍保留均衡荤菜/素菜/汤品。"""
    adjusted: dict[int, int] = dict(structure)
    if meal_key not in ("lunch", "dinner") or not staple or not _is_noodle_staple(staple):
        return adjusted
    # 面食作为一碗主食，至多保留一道素菜；不删荤菜与汤品，避免营养失衡。
    adjusted[2] = min(int(adjusted.get(2, 0)), 1)
    return adjusted


def _remember_generated_meals(target_date: date, meals: dict[str, list[dict[str, Any]]]) -> None:
    """保存本次结果并清理过期进程内历史。"""
    _RECENT_MEAL_HISTORY[target_date] = {
        meal_key: list(meals.get(meal_key, [])) for meal_key in config.MEAL_KEYS
    }
    if len(_RECENT_MEAL_HISTORY) <= _HISTORY_MAX_DATES:
        return
    for old_date in sorted(_RECENT_MEAL_HISTORY)[:-_HISTORY_MAX_DATES]:
        del _RECENT_MEAL_HISTORY[old_date]


def generate_daily_meals(
    d: date,
    region: int,
    plan: Optional[dict[str, Any]] = None,
    rotation_seed: int = 0,
    avoid_dish_ids: Optional[set[int]] = None,
) -> dict[str, Any]:
    """生成每日三餐配餐结果。

    早餐优先粥/粗粮/小菜，并排除重口主菜；同一日的早午晚餐不会重复同一道菜。
    ``rotation_seed`` 用于同日候选轮换；``avoid_dish_ids`` 用于主动重新配餐时
    尽量避开上一次整套菜单，且不会放宽忌口、素食等硬性约束。
    """
    if plan is None:
        plan = build_today_plan()

    environment: dict[str, Any] = detect(d)
    rule: dict[str, Any] = {
        "solar_term": environment["solar_term"],
        "recommend_food": environment.get("recommend_food", []),
        "forbid_food": environment.get("forbid_food", []),
    }
    empty_meals: dict[str, list[dict[str, Any]]] = {
        meal_key: [] for meal_key in config.MEAL_KEYS
    }
    if all(not plan.get(meal_key) for meal_key in config.MEAL_KEYS):
        return {
            "term": environment["solar_term"],
            "health_tip": environment["health_tip"],
            "recommend_food": rule["recommend_food"],
            "forbid_food": rule["forbid_food"],
            "meals": empty_meals,
        }

    all_dishes: list[dict[str, Any]] = _load_dishes(region)
    vegetarian_map: dict[str, int] = _load_veg_map()
    meals_result: dict[str, list[dict[str, Any]]] = {
        meal_key: [] for meal_key in config.MEAL_KEYS
    }
    # 全日已选菜品 ID：保证早餐、午餐、晚餐不会出现同一道菜。
    selected_day_ids: set[int] = set()
    # 重配时先排除上一套菜单；若特定餐次候选确实不足，再由下方回退逻辑补位。
    avoided_ids: set[int] = {int(dish_id) for dish_id in (avoid_dish_ids or set())}

    for meal_key in config.MEAL_KEYS:
        dining: list[dict[str, Any]] = plan.get(meal_key, []) or []
        headcount: int = int(plan.get("stats", {}).get(meal_key, {}).get("headcount", 0))
        if not dining or headcount <= 0:
            continue

        constraints: dict[str, Any] = _build_constraints(dining, rule)
        banquet: bool = bool(plan.get("banquet", False))
        structure: dict[int, int] = config.get_meal_structure(headcount, banquet=banquet)[meal_key]
        selected_staple: Optional[dict[str, Any]] = None

        # 早餐按结构表逐类填充：优先 dish_type=5 早餐专用菜谱（包子/稀饭/豆浆/
        # 凉拌小菜等），再按结构补素菜(type=2)等。候选不足时仅放宽「避免集」
        # （重配）回退，不重复已选，也绝不引入重油重辣主菜。
        if meal_key == "breakfast":
            for dish_type, count in structure.items():
                if count <= 0:
                    continue
                candidates: list[dict[str, Any]] = [
                    dish for dish in all_dishes if int(dish.get("dish_type", 0)) == dish_type
                ]
                pool: list[dict[str, Any]] = _candidate_pool(
                    candidates,
                    constraints,
                    vegetarian_map,
                    rule,
                    region,
                    meal_key,
                    d,
                    count,
                    rotation_seed,
                    avoided_ids,
                )
                selected: list[dict[str, Any]] = _select(
                    pool,
                    count,
                    selected=meals_result[meal_key],
                    excluded_ids=selected_day_ids | avoided_ids,
                )
                # 仅靠「避免集」回退补位：候选确实不足时，不再排除重配菜单，
                # 但仍排除同日已选的菜，避免早午晚跨餐重复。
                if len(selected) < count and avoided_ids:
                    selected += _select(
                        pool,
                        count - len(selected),
                        selected=meals_result[meal_key] + selected,
                        excluded_ids=selected_day_ids,
                    )
                meals_result[meal_key].extend(selected)
                selected_day_ids.update(int(dish.get("id", 0)) for dish in selected)
            continue  # 早餐处理完毕，跳过标准逻辑

        # 午晚餐使用标准逻辑
        for dish_type in (1, 2, 3, 4):
            count: int = int(structure.get(dish_type, 0))
            if dish_type != 1:
                structure = _adjust_structure_for_noodle(structure, selected_staple, meal_key)
                count = int(structure.get(dish_type, 0))
            if count <= 0:
                continue

            candidates: list[dict[str, Any]] = [
                dish for dish in all_dishes if int(dish.get("dish_type", 0)) == dish_type
            ]
            pool: list[dict[str, Any]] = _candidate_pool(
                candidates,
                constraints,
                vegetarian_map,
                rule,
                region,
                meal_key,
                d,
                count,
                rotation_seed,
                avoided_ids,
            )
            if dish_type == 1:
                pool = _prefer_lunch_dinner_staples(pool, meal_key)

            excluded_ids: set[int] = selected_day_ids | avoided_ids
            selected: list[dict[str, Any]] = _select(
                pool,
                count,
                selected=meals_result[meal_key],
                excluded_ids=excluded_ids,
            )
            if len(selected) < count and avoided_ids:
                selected = _select(
                    pool,
                    count,
                    selected=meals_result[meal_key],
                    excluded_ids=selected_day_ids,
                )
            meals_result[meal_key].extend(selected)
            selected_day_ids.update(int(dish.get("id", 0)) for dish in selected)
            if dish_type == 1 and selected:
                selected_staple = selected[0]

    _remember_generated_meals(d, meals_result)
    return {
        "term": environment["solar_term"],
        "health_tip": environment["health_tip"],
        "recommend_food": rule["recommend_food"],
        "forbid_food": rule["forbid_food"],
        "meals": meals_result,
    }


def replace_dish(
    d: date,
    region: int,
    plan: Optional[dict[str, Any]],
    meal_key: str,
    old_dish_id: int,
    current_dish_ids: set[int],
) -> Optional[dict[str, Any]]:
    """替换单道菜，返回同类型、未在当前结果中使用的新菜品。

    替换同样遵循早餐重口过滤、节气优先和成员硬性忌口；候选不足时只放宽
    年龄/健康适配，不会放宽忌口或素食限制。
    """
    if meal_key not in config.MEAL_KEYS:
        return None

    all_dishes: list[dict[str, Any]] = _load_dishes(region)
    old_dish: Optional[dict[str, Any]] = next(
        (dish for dish in all_dishes if int(dish.get("id", 0)) == old_dish_id),
        None,
    )
    if old_dish is None:
        return None

    environment: dict[str, Any] = detect(d)
    rule: dict[str, Any] = {
        "solar_term": environment["solar_term"],
        "recommend_food": environment.get("recommend_food", []),
        "forbid_food": environment.get("forbid_food", []),
    }
    dining: list[dict[str, Any]] = (plan or {}).get(meal_key, []) or []
    constraints: dict[str, Any] = _build_constraints(dining, rule)
    same_type: list[dict[str, Any]] = [
        dish
        for dish in all_dishes
        if int(dish.get("dish_type", 0)) == int(old_dish.get("dish_type", 0))
    ]
    pool: list[dict[str, Any]] = _candidate_pool(
        same_type,
        constraints,
        _load_veg_map(),
        rule,
        region,
        meal_key,
        d,
        1,
    )
    blocked_ids: set[int] = set(current_dish_ids)
    blocked_ids.add(old_dish_id)
    replacements: list[dict[str, Any]] = _select(pool, 1, excluded_ids=blocked_ids)
    return replacements[0] if replacements else None
