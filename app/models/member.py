"""家庭成员模型（FamilyMember）。

封装单条 family_member 记录与领域对象之间的转换，并提供口味、忌口、
体质等便捷访问。
"""

from __future__ import annotations

from typing import Any

from app import config


class FamilyMember:
    """家庭成员领域对象。"""

    def __init__(
        self,
        nick_name: str = "",
        birth_ym: str = "",
        age_type: int = 4,
        is_eat_breakfast: int = 1,
        is_eat_lunch: int = 1,
        is_eat_dinner: int = 1,
        taste: dict | None = None,
        avoid_food: dict | None = None,
        health_tag: list | None = None,
        member_id: int = 0,
        user_id: int = config.DEFAULT_USER_ID,
    ) -> None:
        self.id = member_id
        self.user_id = user_id
        self.nick_name = nick_name
        self.birth_ym = birth_ym
        self.age_type = age_type
        self.is_eat_breakfast = is_eat_breakfast
        self.is_eat_lunch = is_eat_lunch
        self.is_eat_dinner = is_eat_dinner
        self.taste = taste or {d: config.BASE_TASTE[d] for d in config.TASTE_DIMS}
        self.avoid_food = avoid_food or {"categories": [], "items": [], "vegetarian": False}
        self.health_tag = health_tag or []

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        """转为可入库 / 可展示的字典。"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "nick_name": self.nick_name,
            "birth_ym": self.birth_ym,
            "age_type": self.age_type,
            "is_eat_breakfast": self.is_eat_breakfast,
            "is_eat_lunch": self.is_eat_lunch,
            "is_eat_dinner": self.is_eat_dinner,
            "taste": dict(self.taste),
            "avoid_food": dict(self.avoid_food),
            "health_tag": list(self.health_tag),
            "age_name": config.AGE_TYPES.get(self.age_type, "未知"),
        }

    @classmethod
    def from_row(cls, row: dict) -> "FamilyMember":
        """从数据库行构造对象。"""
        taste = {d: int(row.get(f"{d}_level", config.BASE_TASTE[d])) for d in config.TASTE_DIMS}
        avoid_food = config.json_decode(row.get("avoid_food"))
        if not isinstance(avoid_food, dict):
            avoid_food = {"categories": [], "items": [], "vegetarian": False}
        health_tag = config.json_decode(row.get("health_tag"))
        if not isinstance(health_tag, list):
            health_tag = []
        return cls(
            nick_name=row.get("nick_name", ""),
            birth_ym=row.get("birth_ym", ""),
            age_type=int(row.get("age_type", 4)),
            is_eat_breakfast=int(row.get("is_eat_breakfast", 1)),
            is_eat_lunch=int(row.get("is_eat_lunch", 1)),
            is_eat_dinner=int(row.get("is_eat_dinner", 1)),
            taste=taste,
            avoid_food=avoid_food,
            health_tag=health_tag,
            member_id=int(row.get("id", 0)),
            user_id=int(row.get("user_id", config.DEFAULT_USER_ID)),
        )

    def to_storage(self) -> dict:
        """转为可直接 upsert 的字段字典（含拆分的口味等级字段）。"""
        data = {
            "user_id": self.user_id,
            "nick_name": self.nick_name,
            "birth_ym": self.birth_ym,
            "age_type": self.age_type,
            "is_eat_breakfast": self.is_eat_breakfast,
            "is_eat_lunch": self.is_eat_lunch,
            "is_eat_dinner": self.is_eat_dinner,
            "spicy_level": int(self.taste.get("spicy", 2)),
            "numb_level": int(self.taste.get("numb", 2)),
            "acid_level": int(self.taste.get("acid", 1)),
            "salt_level": int(self.taste.get("salt", 2)),
            "sweet_level": int(self.taste.get("sweet", 1)),
            "avoid_food": config.json_encode(self.avoid_food),
            "health_tag": config.json_encode(self.health_tag),
        }
        if self.id:
            data["id"] = self.id
        return data

    def eat_meals(self) -> list[str]:
        """返回该成员今日用餐的餐次键列表。"""
        meals: list[str] = []
        if self.is_eat_breakfast:
            meals.append("breakfast")
        if self.is_eat_lunch:
            meals.append("lunch")
        if self.is_eat_dinner:
            meals.append("dinner")
        return meals

    def __repr__(self) -> str:
        return f"<FamilyMember {self.nick_name} age={self.age_type}>"
