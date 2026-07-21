"""⑦ 菜品详情。

详情页只保留家庭实际下厨所需的信息：主要食材、家庭做法、搭配建议、
忌口提示、注意事项和返回导航。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import theme
from app.database import DB
from app.models.dish import DishMain


def _join(labels: list) -> str:
    return "、".join(labels) if labels else "通用 / 无特殊"


def build_recipe_details(dish: dict) -> dict[str, str]:
    """从完整或旧版菜品数据构建详情页所需的可读辅助说明。"""
    steps: list[str] = dish.get("recipe_steps", []) or []
    taboo: str = str(dish.get("taboo_crowd", "")).strip()
    return {
        "steps": "\n".join(f"{index + 1}. {step}" for index, step in enumerate(steps)) or "食材洗净切好后，用少油少盐的方式炒、煮或蒸熟即可；口味可按家庭成员调整。",
        "pairing_tip": "搭配主食与不同颜色蔬菜，营养更均衡；口味宜清淡，按家庭成员食量调整。",
        "taboo_tip": taboo or "无特殊忌口；对主材过敏者请勿食用。",
    }


def dish_detail_page(page: ft.Page) -> ft.View:
    """构建菜品详情视图（从 page.route 解析菜品 id）。"""
    try:
        dish_id = int(page.route.split("/")[-1])
    except (ValueError, IndexError):
        dish_id = 0

    row = DB.get_by_id("dish_main", dish_id)
    if not row:
        body = ft.Column(
            [
                theme.text("未找到该菜品", theme.SUBTITLE_TEXT,
                           color=theme.COLOR_ACCENT),
                ft.Container(height=16),
                theme.big_button("返回", on_click=lambda e: navigate(page, "/result")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route=page.route,
            appbar=theme.app_bar("菜品详情",
                                 leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                       on_click=lambda e: navigate(page, "/result"))),
            controls=[body],
            padding=20,
        )

    dish = DishMain.from_row(row).to_dict()

    ingredients_lines = "\n".join(
        f"· {ing['name']}（{ing['grams']}克）" for ing in dish["main_ingredients"]
    ) or "无"
    recipe_details = build_recipe_details(dish)

    info = ft.Column(
        [
            theme.text("主要食材（每人份）", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(ingredients_lines, theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("家庭做法", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(recipe_details["steps"], theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("搭配建议", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(recipe_details["pairing_tip"], theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("忌口提示", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(recipe_details["taboo_tip"], theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            theme.text("注意事项：" + (dish["note"] or "无"), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
        ]
    )

    body = ft.Column([theme.card(info)], scroll=ft.ScrollMode.AUTO)

    return ft.View(
        route=page.route,
        appbar=theme.app_bar("菜品详情",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/result"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
