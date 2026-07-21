"""家庭成员与模板服务。

提供：
  * 成员增删改查（FamilyMember 对象 <-> DB）
  * 家庭模板（日常 / 招待）增删改查
  * build_today_plan()：聚合今日各餐用餐成员与统计
  * build_plan_from_selection()：根据显式选人结果构建用餐计划
  * build_banquet_plan()：构建宴请用餐计划（含虚拟访客）
  * save/load_diner_selection()：选人记忆持久化
  * save/load_banquet_selection()：宴请选择记忆持久化

遵循 Google Python 风格指南。
"""

from __future__ import annotations

from typing import Optional

from app import config
from app.database import DB
from app.models.member import FamilyMember
from app.models.template import UserTemplate
from app.services.age_service import calc_age_type


# ---------------------------------------------------------------------------
# 家庭成员
# ---------------------------------------------------------------------------
def list_members() -> list[FamilyMember]:
    """返回全部家庭成员（按 id 升序）。"""
    rows = DB.query("SELECT * FROM family_member ORDER BY id ASC")
    return [FamilyMember.from_row(r) for r in rows]


def get_member(member_id: int) -> Optional[FamilyMember]:
    """按 id 获取成员，未命中返回 None。"""
    row = DB.get_by_id("family_member", member_id)
    if not row:
        return None
    return FamilyMember.from_row(row)


def save_member(member: FamilyMember) -> int:
    """保存（新增 / 更新）成员，返回 id。"""
    # 自动刷新年龄层级
    if member.birth_ym:
        member.age_type = calc_age_type(member.birth_ym)
    return DB.upsert("family_member", member.to_storage())


def delete_member(member_id: int) -> None:
    """删除成员。"""
    DB.delete("family_member", member_id)


def member_count() -> int:
    """返回成员总数。"""
    rows = DB.query("SELECT COUNT(*) AS c FROM family_member")
    return rows[0]["c"] if rows else 0


# ---------------------------------------------------------------------------
# 今日用餐计划聚合
# ---------------------------------------------------------------------------
def build_today_plan(members: Optional[list[FamilyMember]] = None) -> dict:
    """聚合今日各餐用餐成员与统计。

    Args:
        members: 可选成员列表；缺省时读取全部成员。

    Returns:
        字典：{'breakfast':[member_dict], 'lunch':[...], 'dinner':[...],
              'stats': {meal: {headcount, age_dist, health_dist}}}。
        始终返回完整结构，空场景返回空列表与 0 统计。
    """
    if members is None:
        members = list_members()

    plan: dict = {meal: [] for meal in config.MEAL_KEYS}
    for m in members:
        m_dict = m.to_dict()
        for meal in m.eat_meals():
            plan[meal].append(m_dict)

    _build_stats(plan)
    return plan


# ---------------------------------------------------------------------------
# V1.1: 统计填充（提取自 build_today_plan 的公共逻辑）
# ---------------------------------------------------------------------------
def _build_stats(plan: dict) -> None:
    """填充 plan["stats"]，含各餐人数 / 年龄分布 / 体质标签分布。

    Args:
        plan: 用餐计划字典（原地修改，添加 "stats" 键）。
    """
    stats: dict = {}
    for meal in config.MEAL_KEYS:
        diners = plan[meal]
        age_dist: dict = {}
        health_dist: dict = {}
        for m_dict in diners:
            at = m_dict["age_type"]
            age_dist[at] = age_dist.get(at, 0) + 1
            for h in m_dict.get("health_tag", []):
                health_dist[h] = health_dist.get(h, 0) + 1
        stats[meal] = {
            "headcount": len(diners),
            "age_dist": age_dist,
            "health_dist": health_dist,
        }
    plan["stats"] = stats


# ---------------------------------------------------------------------------
# V1.1: 显式选人构建用餐计划
# ---------------------------------------------------------------------------
def build_plan_from_selection(
    members: list[FamilyMember],
    selection: list[dict],
) -> dict:
    """根据显式选人结果构建用餐计划（不写 DB）。

    Args:
        members: 全部家庭成员列表。
        selection: [{"id":1, "breakfast":True, "lunch":True, "dinner":False}, ...]

    Returns:
        与 build_today_plan 相同结构的 plan dict。
    """
    plan: dict = {meal: [] for meal in config.MEAL_KEYS}
    sel_map: dict = {s["id"]: s for s in selection}
    for m in members:
        s = sel_map.get(m.id)
        if not s:
            continue
        m_dict = m.to_dict()
        for meal in config.MEAL_KEYS:
            if s.get(meal):
                plan[meal].append(m_dict)
    _build_stats(plan)
    return plan


# ---------------------------------------------------------------------------
# V1.1: 宴请配餐计划（含虚拟访客）
# ---------------------------------------------------------------------------
def build_banquet_plan(
    members: list[FamilyMember],
    member_ids: list[int],
    guest_adults: int,
    guest_children: int,
    guest_elderly: int,
    meal_key: str,
) -> dict:
    """构建宴请用餐计划。

    老人计入成人总数（age_type=5），儿童标注 age_type=2。
    访客不参与忌口过滤，仅贡献人数和展示标签。

    Args:
        members: 全部家庭成员列表。
        member_ids: 参加宴请的家庭成员 ID 列表。
        guest_adults: 访客成人数。
        guest_children: 访客儿童数。
        guest_elderly: 访客老人数。
        meal_key: 宴请餐次（"lunch" 或 "dinner"）。

    Returns:
        plan dict，含 banquet=True / banquet_meal 标记。
    """
    plan: dict = {meal: [] for meal in config.MEAL_KEYS}

    # 家庭成员加入指定餐次
    id_set = set(member_ids)
    for m in members:
        if m.id in id_set:
            plan[meal_key].append(m.to_dict())

    # 虚拟访客
    idx = 0
    for _ in range(guest_adults):
        plan[meal_key].append(_make_guest_dish(idx, age_type=4, tags=[]))
        idx += 1
    for _ in range(guest_children):
        plan[meal_key].append(_make_guest_dish(idx, age_type=2, tags=["儿童易消化"]))
        idx += 1
    for _ in range(guest_elderly):
        plan[meal_key].append(_make_guest_dish(idx, age_type=5, tags=["老人养胃"]))
        idx += 1

    plan["banquet"] = True
    plan["banquet_meal"] = meal_key
    _build_stats(plan)
    return plan


def _make_guest_dish(idx: int, age_type: int, tags: list) -> dict:
    """构造虚拟访客 dict。

    Args:
        idx: 访客序号（用于生成负数 ID）。
        age_type: 年龄层级（4 成人 / 2 儿童 / 5 老年）。
        tags: 体质标签列表。

    Returns:
        与 FamilyMember.to_dict() 兼容的 dict，id 为负数。
    """
    return {
        "id": -(idx + 1),
        "nick_name": "访客",
        "age_type": age_type,
        "taste": dict(config.BASE_TASTE),
        "avoid_food": {"categories": [], "items": [], "vegetarian": False},
        "health_tag": tags,
    }


# ---------------------------------------------------------------------------
# V1.1: 选人记忆持久化（app_setting JSON 读写）
# ---------------------------------------------------------------------------
def save_diner_selection(selection: list[dict]) -> None:
    """将选人结果序列化存入 app_setting。

    Args:
        selection: [{"id":1, "breakfast":True, ...}, ...]
    """
    DB.set_setting(config.SETTING_KEY_LAST_DINER, config.json_encode(selection))


def load_diner_selection() -> list[dict]:
    """从 app_setting 读取上次选人结果。

    Returns:
        选人列表；无记录时返回空列表。
    """
    raw = DB.get_setting(config.SETTING_KEY_LAST_DINER)
    data = config.json_decode(raw)
    return data if isinstance(data, list) else []


def save_banquet_selection(data: dict) -> None:
    """将宴请选择序列化存入 app_setting。

    Args:
        data: {"member_ids":[...], "guest_adults":n, ...}
    """
    DB.set_setting(config.SETTING_KEY_LAST_BANQUET, config.json_encode(data))


def load_banquet_selection() -> dict:
    """从 app_setting 读取上次宴请选择。

    Returns:
        宴请选择字典；无记录时返回空字典。
    """
    raw = DB.get_setting(config.SETTING_KEY_LAST_BANQUET)
    data = config.json_decode(raw)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# 家庭模板
# ---------------------------------------------------------------------------
def list_templates(template_type: Optional[int] = None) -> list[UserTemplate]:
    """返回模板列表，可按类型筛选。"""
    if template_type is None:
        rows = DB.query("SELECT * FROM user_template ORDER BY id ASC")
    else:
        rows = DB.query(
            "SELECT * FROM user_template WHERE template_type = ? ORDER BY id ASC",
            [template_type],
        )
    return [UserTemplate.from_row(r) for r in rows]


def get_template(template_id: int) -> Optional[UserTemplate]:
    """按 id 获取模板。"""
    row = DB.get_by_id("user_template", template_id)
    if not row:
        return None
    return UserTemplate.from_row(row)


def save_template(template: UserTemplate) -> int:
    """保存（新增 / 更新）模板，返回 id。"""
    return DB.upsert("user_template", template.to_storage())


def delete_template(template_id: int) -> None:
    """删除模板。"""
    DB.delete("user_template", template_id)


def apply_template(template_id: int) -> bool:
    """应用模板：将模板中保存的家族配置写回 family_member 表。

    模板仅保存成员口味 / 忌口 / 用餐开关快照，应用即覆盖现有成员档案。

    Returns:
        是否成功应用。
    """
    template = get_template(template_id)
    if template is None:
        return False
    for cfg in template.family_config:
        member = FamilyMember(
            nick_name=cfg.get("nick_name", ""),
            birth_ym=cfg.get("birth_ym", ""),
            age_type=cfg.get("age_type", 4),
            is_eat_breakfast=cfg.get("is_eat_breakfast", 1),
            is_eat_lunch=cfg.get("is_eat_lunch", 1),
            is_eat_dinner=cfg.get("is_eat_dinner", 1),
            taste=cfg.get("taste"),
            avoid_food=cfg.get("avoid_food"),
            health_tag=cfg.get("health_tag"),
            member_id=cfg.get("id", 0),
        )
        save_member(member)
    return True
