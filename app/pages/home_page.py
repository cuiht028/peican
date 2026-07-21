"""首页：节气信息、城市入口与配餐功能导航。"""

from __future__ import annotations

import flet as ft

from app import config, theme
from app.database import DB
from app.nav import navigate
from app.services.env_service import detect
from app.services.member_service import member_count

_LAST: dict[str, object] = {"result": None, "plan": None}
_CITY_OPTIONS: tuple[str, ...] = ("成都", "重庆", "其他")


def store_plan(result: dict, plan: dict) -> None:
    """保存最近生成的结果与计划，供结果页和购物页使用。"""
    _LAST["result"] = result
    _LAST["plan"] = plan


def get_last() -> tuple[object, object]:
    """返回内存中的最近一次配餐结果和计划。"""
    return _LAST["result"], _LAST["plan"]


def _save_city(city: str) -> None:
    """保存简单的手动城市选择；不依赖网络定位。"""
    normalized: str = city if city in _CITY_OPTIONS else "成都"
    DB.set_setting(config.SETTING_KEY_CITY, normalized)
    DB.set_setting(config.SETTING_KEY_REGION_TYPE, "1" if normalized in ("成都", "重庆") else "2")


def home_page(page: ft.Page) -> ft.View:
    """构建可滚动、窄屏友好的应用主页。"""
    environment: dict = detect()
    current_city: str = str(environment.get("city", "成都"))
    if current_city not in _CITY_OPTIONS:
        current_city = "成都"
    has_member: bool = member_count() > 0

    city_dropdown = ft.Dropdown(
        value=current_city,
        options=[ft.dropdown.Option(city) for city in _CITY_OPTIONS],
        text_size=theme.LARGE_TEXT,
        label="城市",
        label_style=theme.text_style(theme.HINT_TEXT, theme.COLOR_SECONDARY_TEXT),
        dense=True,
        width=145,
        on_select=lambda event: _save_city(str(event.control.value)),
    )
    info_card = theme.card(ft.Column([
        ft.Row([
            city_dropdown,
            ft.Container(width=8),
            theme.text(f"{environment['solar_term']} · {environment['date']}", theme.LARGE_TEXT,
                       color=theme.COLOR_DEEP, weight=ft.FontWeight.BOLD),
        ], wrap=True),
        ft.Container(height=8),
        theme.text("今日养生提示", theme.SUBTITLE_TEXT, color=theme.COLOR_DEEP,
                   weight=ft.FontWeight.BOLD),
        theme.text(str(environment["health_tip"]), theme.LARGE_TEXT, color=theme.COLOR_TEXT),
    ]))
    member_hint: ft.Control = theme.card(theme.text(
        "还没有家庭成员。先录入成员信息，配餐会更贴合全家的口味和忌口。",
        theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT,
    ), bgcolor=theme.COLOR_SURFACE_ALT) if not has_member else ft.Container()

    buttons: list[ft.Control] = [
        theme.big_button("今日一键配餐", icon=ft.Icons.RESTAURANT_MENU,
                         on_click=lambda event: navigate(page, "/diner_select")),
        theme.big_button("家庭宴请配餐", icon=ft.Icons.DINNER_DINING,
                         bgcolor=theme.COLOR_DEEP,
                         on_click=lambda event: navigate(page, "/banquet")),
        theme.big_button("家庭成员管理", icon=ft.Icons.GROUP,
                         bgcolor=theme.COLOR_PRIMARY_LIGHT, color=theme.COLOR_TEXT,
                         on_click=lambda event: navigate(page, "/member")),
        theme.big_button("养生菜谱库", icon=ft.Icons.MENU_BOOK,
                         bgcolor=theme.COLOR_SURFACE_ALT, color=theme.COLOR_TEXT,
                         on_click=lambda event: navigate(page, "/dish_library")),
        theme.big_button("今日买菜清单", icon=ft.Icons.SHOPPING_CART,
                         bgcolor=theme.COLOR_SURFACE_ALT, color=theme.COLOR_TEXT,
                         on_click=lambda event: navigate(page, "/shopping")),
    ]
    body = ft.Column(
        controls=[
            info_card,
            member_hint,
            *[
                ft.Container(
                    content=button,
                    margin=ft.Margin.only(top=8),
                )
                for button in buttons
            ],
        ],
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        expand=True,
    )
    return ft.View(route="/home", appbar=theme.app_bar("家庭养生配餐"), controls=[body],
                   padding=16, scroll=ft.ScrollMode.AUTO)
