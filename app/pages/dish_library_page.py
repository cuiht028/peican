"""③c 养生菜谱库。

浏览全部菜品，按类型筛选（全部 / 主食 / 素菜 / 荤菜 / 汤品），点击菜品
卡片跳转到菜品详情页。

路由：/dish_library
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import config
from app import theme
from app.database import DB
from app.models.dish import DishMain


def dish_library_page(page: ft.Page) -> ft.View:
    """构建养生菜谱库视图。"""
    # 加载全部菜品
    rows = DB.query("SELECT * FROM dish_main ORDER BY id ASC")
    all_dishes = [DishMain.from_row(r).to_dict() for r in rows]

    # 当前筛选类型：0 = 全部
    current_filter: dict = {"type": 0}

    # 类型筛选按钮
    filter_buttons: list[ft.Control] = []
    filter_specs = [
        (0, "全部"),
        (1, "主食"),
        (2, "素菜"),
        (3, "荤菜"),
        (4, "汤品"),
    ]

    # 菜品列表容器（用 Column 动态刷新内容）
    dish_list_col = ft.Column([], scroll=ft.ScrollMode.AUTO)

    def _refresh_dish_list() -> None:
        """根据当前筛选类型刷新菜品列表。"""
        ft_type = current_filter["type"]
        if ft_type == 0:
            shown = all_dishes
        else:
            shown = [d for d in all_dishes if d["dish_type"] == ft_type]

        dish_list_col.controls.clear()
        if not shown:
            dish_list_col.controls.append(
                theme.text("暂无该类型菜品", theme.LARGE_TEXT,
                           color=theme.COLOR_SECONDARY_TEXT)
            )
        for dish in shown:
            # 口味描述
            taste_parts = []
            for dim in config.TASTE_DIMS:
                level = dish["taste"].get(dim, 2)
                label = config.TASTE_LABELS.get(level, "")
                if level > 1:  # 只显示非"无"的口味
                    taste_parts.append(
                        f"{config.TASTE_DIM_NAMES[dim]}{label}"
                    )
            taste_str = " / ".join(taste_parts) if taste_parts else "清淡"

            dish_card = theme.card(
                ft.Row(
                    [
                        ft.Column(
                            [
                                theme.text(dish["dish_name"], theme.LARGE_TEXT,
                                           color=theme.COLOR_TEXT,
                                           weight=ft.FontWeight.BOLD),
                                ft.Container(height=4),
                                ft.Row(
                                    [
                                        theme.text(
                                            "【" + dish["dish_type_name"] + "】",
                                            theme.HINT_TEXT,
                                            color=theme.COLOR_PRIMARY,
                                        ),
                                        ft.Container(width=12),
                                        theme.text(taste_str, theme.HINT_TEXT,
                                                   color=theme.COLOR_SECONDARY_TEXT),
                                    ]
                                ),
                            ]
                        ),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.COLOR_BORDER),
                    ]
                ),
                bgcolor=theme.COLOR_SURFACE,
            )
            dish_card.on_click = lambda e, did=dish["id"]: navigate(page, f"/dish/{did}")
            dish_list_col.controls.append(dish_card)

        page.update()

    def _make_filter_handler(ftype: int):
        def _handler(e) -> None:
            current_filter["type"] = ftype
            _refresh_dish_list()
        return _handler

    for ftype, label in filter_specs:
        bgcolor = theme.COLOR_PRIMARY if ftype == 0 else theme.COLOR_SURFACE
        txt_color = theme.COLOR_WHITE if ftype == 0 else theme.COLOR_TEXT
        btn = ft.ElevatedButton(
            label,
            on_click=_make_filter_handler(ftype),
            bgcolor=bgcolor,
            color=txt_color,
            height=48,
            style=ft.ButtonStyle(
                text_style=theme.text_style(theme.LARGE_TEXT, txt_color,
                                            ft.FontWeight.BOLD),
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )
        filter_buttons.append(btn)

    body = ft.Column(
        [
            theme.text("养生菜谱库", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=10),
            ft.Row(filter_buttons, wrap=True),
            ft.Container(height=12),
            dish_list_col,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    # 初始填充菜品列表
    _refresh_dish_list()

    return ft.View(
        route="/dish_library",
        appbar=theme.app_bar("养生菜谱库",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
