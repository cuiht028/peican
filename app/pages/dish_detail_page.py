"""⑦ 菜品详情。

展示单道菜的完整信息：类型、口味、适宜 / 禁忌年龄与体质、主材、菜谱
步骤、功效、适宜 / 禁忌人群、注意事项、适宜节气。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import config
from app import theme
from app.database import DB
from app.models.dish import DishMain


def _join(labels: list) -> str:
    return "、".join(labels) if labels else "通用 / 无特殊"


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

    def fmt_taste(taste: dict) -> str:
        return "，".join(
            f"{config.TASTE_DIM_NAMES[d]}{config.TASTE_LABELS.get(taste.get(d, 2), '')}"
            for d in config.TASTE_DIMS
        )

    ingredients_lines = "\n".join(
        f"· {ing['name']}（{ing['grams']}克）" for ing in dish["main_ingredients"]
    ) or "无"
    steps_lines = "\n".join(
        f"{i + 1}. {s}" for i, s in enumerate(dish["recipe_steps"])
    ) or "无"

    info = ft.Column(
        [
            theme.text("菜名：" + dish["dish_name"], theme.TITLE_TEXT,
                       color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            theme.text("类型：" + dish["dish_type_name"], theme.LARGE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=6),
            theme.text("口味：" + fmt_taste(dish["taste"]), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            ft.Container(height=6),
            theme.text("适宜年龄：" + _join([config.AGE_TYPES.get(a, str(a)) for a in dish["suit_age"]]),
                       theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            theme.text("禁忌年龄：" + _join([config.AGE_TYPES.get(a, str(a)) for a in dish["forbid_age"]]),
                       theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            theme.text("适宜体质：" + _join(dish["suit_health"]), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            theme.text("禁忌体质：" + _join(dish["forbid_health"]), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            ft.Container(height=10),
            theme.text("功效", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(dish["efficacy"] or "无", theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("主材（每人份）", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(ingredients_lines, theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("菜谱步骤", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            theme.text(steps_lines, theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ft.Container(height=8),
            theme.text("适宜人群：" + (dish["suitable_crowd"] or "无"), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            theme.text("禁忌人群：" + (dish["taboo_crowd"] or "无"), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            theme.text("注意事项：" + (dish["note"] or "无"), theme.LARGE_TEXT,
                       color=theme.COLOR_TEXT),
            theme.text("适宜节气：" + (_join(dish["suit_solar"]) if dish["suit_solar"] else "四季通用"),
                       theme.LARGE_TEXT, color=theme.COLOR_TEXT),
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
