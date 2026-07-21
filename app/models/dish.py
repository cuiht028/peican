"""菜品主表模型（DishMain）。"""

from __future__ import annotations

from typing import Any

from app import config


class DishMain:
    """菜品（成渝家常菜）领域对象。"""

    def __init__(
        self,
        dish_name: str = "",
        dish_type: int = 2,
        region_type: int = 1,
        taste: dict | None = None,
        suit_age: list | None = None,
        forbid_age: list | None = None,
        suit_health: list | None = None,
        forbid_health: list | None = None,
        main_ingredients: list | None = None,
        recipe_steps: list | None = None,
        efficacy: str = "",
        suitable_crowd: str = "",
        taboo_crowd: str = "",
        note: str = "",
        suit_solar: list | None = None,
        dish_id: int = 0,
    ) -> None:
        self.id = dish_id
        self.dish_name = dish_name
        self.dish_type = dish_type
        self.region_type = region_type
        self.taste = taste or {d: config.BASE_TASTE[d] for d in config.TASTE_DIMS}
        self.suit_age = suit_age or []
        self.forbid_age = forbid_age or []
        self.suit_health = suit_health or []
        self.forbid_health = forbid_health or []
        self.main_ingredients = main_ingredients or []
        self.recipe_steps = recipe_steps or []
        self.efficacy = efficacy
        self.suitable_crowd = suitable_crowd
        self.taboo_crowd = taboo_crowd
        self.note = note
        self.suit_solar = suit_solar or []

    @classmethod
    def from_row(cls, row: dict) -> "DishMain":
        """从数据库行构造对象。"""
        taste = {d: int(row.get(f"{d}_level", config.BASE_TASTE[d])) for d in config.TASTE_DIMS}

        def _list(field: str) -> list:
            value = config.json_decode(row.get(field))
            return value if isinstance(value, list) else []

        return cls(
            dish_name=row.get("dish_name", ""),
            dish_type=int(row.get("dish_type", 2)),
            region_type=int(row.get("region_type", 1)),
            taste=taste,
            suit_age=_list("suit_age"),
            forbid_age=_list("forbid_age"),
            suit_health=_list("suit_health"),
            forbid_health=_list("forbid_health"),
            main_ingredients=_list("main_ingredients"),
            recipe_steps=_list("recipe_steps"),
            efficacy=row.get("efficacy", ""),
            suitable_crowd=row.get("suitable_crowd", ""),
            taboo_crowd=row.get("taboo_crowd", ""),
            note=row.get("note", ""),
            suit_solar=_list("suit_solar"),
            dish_id=int(row.get("id", 0)),
        )

    def to_dict(self) -> dict:
        """转为可展示字典。"""
        return {
            "id": self.id,
            "dish_name": self.dish_name,
            "dish_type": self.dish_type,
            "dish_type_name": config.DISH_TYPES.get(self.dish_type, "其他"),
            "region_type": self.region_type,
            "taste": dict(self.taste),
            "suit_age": list(self.suit_age),
            "forbid_age": list(self.forbid_age),
            "suit_health": list(self.suit_health),
            "forbid_health": list(self.forbid_health),
            "main_ingredients": list(self.main_ingredients),
            "recipe_steps": list(self.recipe_steps),
            "efficacy": self.efficacy,
            "suitable_crowd": self.suitable_crowd,
            "taboo_crowd": self.taboo_crowd,
            "note": self.note,
            "suit_solar": list(self.suit_solar),
        }

    def to_storage(self) -> dict:
        """转为可直接 upsert 的字段字典。"""
        data = {
            "dish_name": self.dish_name,
            "dish_type": self.dish_type,
            "region_type": self.region_type,
            "spicy_level": int(self.taste.get("spicy", 2)),
            "numb_level": int(self.taste.get("numb", 2)),
            "acid_level": int(self.taste.get("acid", 1)),
            "salt_level": int(self.taste.get("salt", 2)),
            "sweet_level": int(self.taste.get("sweet", 1)),
            "suit_age": config.json_encode(self.suit_age),
            "forbid_age": config.json_encode(self.forbid_age),
            "suit_health": config.json_encode(self.suit_health),
            "forbid_health": config.json_encode(self.forbid_health),
            "main_ingredients": config.json_encode(self.main_ingredients),
            "recipe_steps": config.json_encode(self.recipe_steps),
            "efficacy": self.efficacy,
            "suitable_crowd": self.suitable_crowd,
            "taboo_crowd": self.taboo_crowd,
            "note": self.note,
            "suit_solar": config.json_encode(self.suit_solar),
        }
        if self.id:
            data["id"] = self.id
        return data

    def __repr__(self) -> str:
        return f"<DishMain {self.dish_name}>"
