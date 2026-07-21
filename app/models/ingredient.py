"""食材基础模型（Ingredient）。"""

from __future__ import annotations

from app import config


class Ingredient:
    """食材领域对象，支撑买菜清单分类与素食判定。"""

    def __init__(
        self,
        name: str = "",
        category: int = 5,
        unit: str = "克",
        alias: str = "",
        is_vegetarian: int = 1,
        ingredient_id: int = 0,
    ) -> None:
        self.id = ingredient_id
        self.name = name
        self.category = category
        self.unit = unit
        self.alias = alias
        self.is_vegetarian = is_vegetarian

    @classmethod
    def from_row(cls, row: dict) -> "Ingredient":
        """从数据库行构造对象。"""
        return cls(
            name=row.get("name", ""),
            category=int(row.get("category", 5)),
            unit=row.get("unit", "克"),
            alias=row.get("alias", ""),
            is_vegetarian=int(row.get("is_vegetarian", 1)),
            ingredient_id=int(row.get("id", 0)),
        )

    def to_dict(self) -> dict:
        """转为可展示字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "category_name": config.INGREDIENT_CATS.get(self.category, "其他"),
            "unit": self.unit,
            "alias": self.alias,
            "is_vegetarian": self.is_vegetarian,
        }

    def to_storage(self) -> dict:
        """转为可直接 upsert 的字段字典。"""
        data = {
            "name": self.name,
            "category": self.category,
            "unit": self.unit,
            "alias": self.alias,
            "is_vegetarian": self.is_vegetarian,
        }
        if self.id:
            data["id"] = self.id
        return data

    def __repr__(self) -> str:
        return f"<Ingredient {self.name}>"
