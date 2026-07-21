"""家庭模板模型（UserTemplate）。"""

from __future__ import annotations

from app import config


class UserTemplate:
    """家庭模板（日常 / 招待）领域对象。"""

    def __init__(
        self,
        template_name: str = "",
        template_type: int = 1,
        family_config: list | None = None,
        guest_num: int = 0,
        guest_child_num: int = 0,
        template_id: int = 0,
        user_id: int = config.DEFAULT_USER_ID,
    ) -> None:
        self.id = template_id
        self.user_id = user_id
        self.template_name = template_name
        self.template_type = template_type
        self.family_config = family_config or []
        self.guest_num = guest_num
        self.guest_child_num = guest_child_num

    def to_dict(self) -> dict:
        """转为可展示字典。"""
        return {
            "id": self.id,
            "template_name": self.template_name,
            "template_type": self.template_type,
            "template_type_name": config.AGE_TYPES and (
                "日常" if self.template_type == 1 else "招待"
            ),
            "family_config": list(self.family_config),
            "guest_num": self.guest_num,
            "guest_child_num": self.guest_child_num,
        }

    @classmethod
    def from_row(cls, row: dict) -> "UserTemplate":
        """从数据库行构造对象。"""
        family_config = config.json_decode(row.get("family_config"))
        if not isinstance(family_config, list):
            family_config = []
        return cls(
            template_name=row.get("template_name", ""),
            template_type=int(row.get("template_type", 1)),
            family_config=family_config,
            guest_num=int(row.get("guest_num", 0)),
            guest_child_num=int(row.get("guest_child_num", 0)),
            template_id=int(row.get("id", 0)),
            user_id=int(row.get("user_id", config.DEFAULT_USER_ID)),
        )

    def to_storage(self) -> dict:
        """转为可直接 upsert 的字段字典。"""
        data = {
            "user_id": self.user_id,
            "template_name": self.template_name,
            "template_type": self.template_type,
            "family_config": config.json_encode(self.family_config),
            "guest_num": self.guest_num,
            "guest_child_num": self.guest_child_num,
        }
        if self.id:
            data["id"] = self.id
        return data

    def __repr__(self) -> str:
        return f"<UserTemplate {self.template_name} type={self.template_type}>"
