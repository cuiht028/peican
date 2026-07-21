"""① 启动页 & 定位权限页。

引导式请求定位权限：单机离线场景默认成渝，并允许用户在进入前手动
切换城市 / 地域。确认后进入首页。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import config
from app import theme
from app.database import DB
from app.services.env_service import get_city


def splash_page(page: ft.Page) -> ft.View:
    """构建启动页视图。"""
    current_city = get_city()
    city_options = ["成都", "重庆", "其他"]
    if current_city not in city_options:
        current_city = "成都"

    city_dropdown = ft.Dropdown(
        label="所在城市（用于推荐本地时令饮食）",
        options=[ft.dropdown.Option(c) for c in city_options],
        value=current_city,
        width=360,
        text_size=theme.LARGE_TEXT,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
        on_select=lambda e: _on_city_change(e.control.value),
    )

    def _on_city_change(value: str) -> None:
        if value in ("成都", "重庆"):
            DB.set_setting("city", value)
            DB.set_setting("region_type", "1")
        else:
            DB.set_setting("city", "其他")
            DB.set_setting("region_type", "2")

    enter_btn = theme.big_button(
        "进入首页",
        icon=ft.Icons.ARROW_FORWARD,
        on_click=lambda e: navigate(page, "/home"),
        width=360,
    )

    body = ft.Column(
        [
            ft.Container(height=40),
            theme.text(
                "家庭四季养生配餐",
                theme.BIG_TITLE_TEXT,
                color=theme.COLOR_PRIMARY,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Container(height=8),
            theme.text("适老 · 时令 · 家常", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=28),
            theme.card(
                ft.Column(
                    [
                        theme.text("位置权限说明", theme.SUBTITLE_TEXT,
                                   color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Container(height=8),
                        theme.text(
                            "本应用可在离线状态下，根据您所在的城市与当前节气，"
                            "为您推荐合适的成渝家常养生膳食。我们默认使用「成渝」"
                            "地区，您也可以下方切换城市。真实 GPS 定位将在后续版本增强。",
                            theme.LARGE_TEXT,
                            color=theme.COLOR_TEXT,
                        ),
                    ]
                )
            ),
            ft.Container(height=20),
            city_dropdown,
            ft.Container(height=24),
            enter_btn,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/",
        appbar=theme.app_bar("欢迎使用", leading=None),
        controls=[body],
        padding=24,
        scroll=ft.ScrollMode.AUTO,
    )
