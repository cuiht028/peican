"""⑧ 买菜清单。

根据最近一次配餐结果与用餐计划，按食材分类聚合「克 / 斤」买菜清单，
支持一键复制为文本。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import theme
from app.pages.home_page import get_last
from app.services.shopping_service import build_shopping_list


def _build_text(shopping: dict) -> str:
    """将清单转为可复制文本。"""
    lines = ["【家庭养生配餐 · 买菜清单】"]
    for cat, items in shopping.items():
        lines.append(f"\n== {cat} ==")
        for it in items:
            lines.append(f"{it['name']}：{int(it['grams'])}克（{it['jin']}斤）")
    return "\n".join(lines)


def shopping_page(page: ft.Page) -> ft.View:
    """构建买菜清单视图。"""
    result, plan = get_last()

    if result is None or plan is None:
        body = ft.Column(
            [
                theme.text("还没有生成配餐结果", theme.SUBTITLE_TEXT,
                           color=theme.COLOR_ACCENT),
                ft.Container(height=12),
                theme.text("请先在首页点击「今日一键配餐」。", theme.LARGE_TEXT,
                           color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=20),
                theme.big_button("去配餐", on_click=lambda e: navigate(page, "/home")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route="/shopping",
            appbar=theme.app_bar("买菜清单",
                                 leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                       on_click=lambda e: navigate(page, "/result"))),
            controls=[body],
            padding=20,
        )

    shopping = build_shopping_list(result["meals"], plan)

    sections = []
    if not shopping:
        sections.append(theme.text("暂无需要采购的食材。", theme.LARGE_TEXT,
                                    color=theme.COLOR_SECONDARY_TEXT))
    for cat, items in shopping.items():
        rows = []
        for it in items:
            rows.append(
                ft.Row(
                    [
                        theme.text(it["name"], theme.LARGE_TEXT,
                                   color=theme.COLOR_TEXT, weight=ft.FontWeight.BOLD),
                        theme.text(f"{int(it['grams'])}克", theme.LARGE_TEXT,
                                   color=theme.COLOR_SECONDARY_TEXT),
                        theme.text(f"约{it['jin']}斤", theme.LARGE_TEXT,
                                   color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                    ],
                    wrap=True,
                )
            )
        sections.append(
            theme.card(
                ft.Column(
                    [
                        theme.text(cat, theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                                   weight=ft.FontWeight.BOLD),
                        ft.Container(height=6),
                        *rows,
                    ]
                )
            )
        )

    save_btn = theme.big_button(
        "暂存清单",
        icon=ft.Icons.SAVE,
        bgcolor=theme.COLOR_SECONDARY_TEXT,
        on_click=lambda e: _on_save(page, _build_text(shopping)),
    )

    body = ft.Column(
        [
            theme.text("按食材分类（克 / 斤）", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=8),
            *sections,
            ft.Container(height=12),
            save_btn,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/shopping",
        appbar=theme.app_bar("买菜清单",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/result"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )


def _on_save(page: ft.Page, text: str) -> None:
    """暂存清单到数据库。"""
    from app.database import DB
    DB.set_setting("shopping_list", text)
    theme.snack(page, "买菜清单已暂存", theme.COLOR_PRIMARY)
