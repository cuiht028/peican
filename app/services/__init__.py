"""服务层包：配餐算法、年龄判定、节气识别、买菜换算。"""

from __future__ import annotations

from app.services.env_service import detect, get_solar_term, get_region, get_city
from app.services.age_service import calc_age_type, age_label
from app.services.member_service import (
    list_members,
    get_member,
    save_member,
    delete_member,
    build_today_plan,
    list_templates,
    save_template,
    delete_template,
    apply_template,
)
from app.services.meal_planner import generate_daily_meals
from app.services.shopping_service import build_shopping_list, convert_weight

__all__ = [
    "detect",
    "get_solar_term",
    "get_region",
    "get_city",
    "calc_age_type",
    "age_label",
    "list_members",
    "get_member",
    "save_member",
    "delete_member",
    "build_today_plan",
    "list_templates",
    "save_template",
    "delete_template",
    "apply_template",
    "generate_daily_meals",
    "build_shopping_list",
    "convert_weight",
]
