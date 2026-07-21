"""节气养生规则模型（SolarHealthRule）。"""

from __future__ import annotations

from app import config


class SolarHealthRule:
    """二十四节气养生规则领域对象。"""

    def __init__(
        self,
        solar_term: str = "",
        climate: str = "",
        health_core: str = "",
        recommend_food: list | None = None,
        forbid_food: list | None = None,
        region_type: int = 1,
        rule_id: int = 0,
    ) -> None:
        self.id = rule_id
        self.solar_term = solar_term
        self.climate = climate
        self.health_core = health_core
        self.recommend_food = recommend_food or []
        self.forbid_food = forbid_food or []
        self.region_type = region_type

    @classmethod
    def from_row(cls, row: dict) -> "SolarHealthRule":
        """从数据库行构造对象。"""
        recommend = config.json_decode(row.get("recommend_food"))
        forbid = config.json_decode(row.get("forbid_food"))
        return cls(
            solar_term=row.get("solar_term", ""),
            climate=row.get("climate", ""),
            health_core=row.get("health_core", ""),
            recommend_food=recommend if isinstance(recommend, list) else [],
            forbid_food=forbid if isinstance(forbid, list) else [],
            region_type=int(row.get("region_type", 1)),
            rule_id=int(row.get("id", 0)),
        )

    def to_dict(self) -> dict:
        """转为可展示字典。"""
        return {
            "id": self.id,
            "solar_term": self.solar_term,
            "climate": self.climate,
            "health_core": self.health_core,
            "recommend_food": list(self.recommend_food),
            "forbid_food": list(self.forbid_food),
            "region_type": self.region_type,
            "region_name": config.REGION_TYPES.get(self.region_type, "其他"),
        }

    def to_storage(self) -> dict:
        """转为可直接 upsert 的字段字典。"""
        data = {
            "solar_term": self.solar_term,
            "climate": self.climate,
            "health_core": self.health_core,
            "recommend_food": config.json_encode(self.recommend_food),
            "forbid_food": config.json_encode(self.forbid_food),
            "region_type": self.region_type,
        }
        if self.id:
            data["id"] = self.id
        return data

    def __repr__(self) -> str:
        return f"<SolarHealthRule {self.solar_term}>"
