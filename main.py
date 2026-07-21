"""应用程序入口。

职责：
  1. 初始化 SQLite 表结构（幂等）。
  2. 首次启动写入种子数据（节气 / 菜品 / 食材，幂等）。
  3. 挂载路由，按页面构建视图。
  4. 启动 Flet 桌面应用（``flet run main.py``）。

遵循 Google Python 风格指南。
"""

from __future__ import annotations

import flet as ft

from app import theme
from app.database import DB
from app.data.seed_loader import run as seed_run
from app.pages import (
    splash_page,
    home_page,
    member_page,
    member_edit_page,
    diner_select_page,
    banquet_page,
    dish_library_page,
    result_page,
    dish_detail_page,
    shopping_page,
    solar_page,
)


def build_view(page: ft.Page, route: str) -> ft.View:
    """根据路由返回对应页面视图。"""
    if route.startswith("/dish/"):
        return dish_detail_page(page)
    if route.startswith("/member_edit"):
        return member_edit_page(page)

    mapping = {
        "/": home_page,
        "/home": home_page,
        "/member": member_page,
        "/diner_select": diner_select_page,
        "/banquet": banquet_page,
        "/dish_library": dish_library_page,
        "/result": result_page,
        "/shopping": shopping_page,
        "/solar": solar_page,
    }
    builder = mapping.get(route, home_page)
    return builder(page)


def on_route_change(page: ft.Page, route: str = None) -> None:
    """路由变更：清空并重建当前视图。"""
    if route:
        page.route = route
    page.views.clear()
    page.views.append(build_view(page, page.route))
    page.update()


def main(page: ft.Page) -> None:
    """Flet 应用主函数。"""
    page.title = "家庭四季养生配餐"
    page.bgcolor = theme.COLOR_BG
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=theme.COLOR_PRIMARY,
            secondary=theme.COLOR_ACCENT,
            surface=theme.COLOR_BG,
        )
    )
    page.theme_mode = ft.ThemeMode.LIGHT
    page.on_route_change = lambda e=None: on_route_change(page)

    # 初始化数据库与种子数据（幂等，先建表再写种子）
    DB.init_schema()
    seed_run()

    # flet 0.86 中 page.go() 用 asyncio.create_task 异步调度，
    # 在 main() 初始化阶段不会立即执行，故直接构建首页视图
    on_route_change(page, "/home")


if __name__ == "__main__":
    ft.run(main)
