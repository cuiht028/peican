"""② 首页。

展示当前城市 / 节气 / 养生提示，并提供主要功能的适老化大入口：
今日一键配餐（→选人）、家庭宴请配餐、家庭成员管理、养生菜谱库。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import theme
from app.services.env_service import detect
from app.services.member_service import member_count

# 跨页共享：最近一次配餐结果与计划（被 result / shopping 页面读取）
_LAST = {"result": None, "plan": None}


def store_plan(result: dict, plan: dict) -> None:
    """保存最近一次配餐结果，供结果页 / 买菜页读取。"""
    _LAST["result"] = result
    _LAST["plan"] = plan


def get_last() -> tuple:
    """返回 (result, plan)，未生成时均为 None。"""
    return _LAST["result"], _LAST["plan"]


def home_page(page: ft.Page) -> ft.View:
    """构建首页视图。"""
    env = detect()
    has_member = member_count() > 0

    info_card = theme.card(
        ft.Column(
            [
                ft.Row(
                    [
                        theme.text("城市：", theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
                        theme.text(env["city"], theme.LARGE_TEXT,
                                   color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Container(width=16),
                        theme.text("节气：", theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
                        theme.text(env["solar_term"], theme.LARGE_TEXT,
                                   color=theme.COLOR_ACCENT, weight=ft.FontWeight.BOLD),
                    ]
                ),
                ft.Container(height=6),
                theme.text("今日：" + env["date"], theme.HINT_TEXT,
                           color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=10),
                theme.text("养生提示", theme.SUBTITLE_TEXT,
                           color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                theme.text(env["health_tip"], theme.LARGE_TEXT, color=theme.COLOR_TEXT),
            ]
        )
    )

    if not has_member:
        hint = theme.text(
            "温馨提示：尚未添加家庭成员，建议先到「家庭成员管理」中录入信息，"
            "配餐将更贴合全家体质。",
            theme.LARGE_TEXT, color=theme.COLOR_ACCENT,
        )
    else:
        hint = ft.Container()

    body = ft.Column(
        [
            info_card,
            ft.Container(height=14),
            hint,
            ft.Container(height=8),
            theme.big_button("今日一键配餐", icon=ft.Icons.RESTAURANT_MENU,
                             on_click=lambda e: navigate(page, "/diner_select"), width=400),
            ft.Container(height=12),
            theme.big_button("家庭宴请配餐", icon=ft.Icons.DINNER_DINING,
                             bgcolor=theme.COLOR_ACCENT,
                             on_click=lambda e: navigate(page, "/banquet"), width=400),
            ft.Container(height=12),
            theme.big_button("家庭成员管理", icon=ft.Icons.GROUP,
                             bgcolor=theme.COLOR_ACCENT,
                             on_click=lambda e: navigate(page, "/member"), width=400),
            ft.Container(height=12),
            theme.big_button("养生菜谱库", icon=ft.Icons.MENU_BOOK,
                             bgcolor=theme.COLOR_SECONDARY_TEXT,
                             on_click=lambda e: navigate(page, "/dish_library"), width=400),
            ft.Container(height=12),
            theme.big_button("今日买菜清单", icon=ft.Icons.SHOPPING_CART,
                             bgcolor=theme.COLOR_PRIMARY_LIGHT,
                             on_click=lambda e: navigate(page, "/shopping"), width=400),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/home",
        appbar=theme.app_bar("家庭养生配餐",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/"))),
        controls=[body],
        padding=20,
        scroll=ft.ScrollMode.AUTO,
    )
