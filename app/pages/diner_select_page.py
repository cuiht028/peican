"""③ 就餐人员选择页。

让用户为今日三餐勾选哪些家庭成员、在哪些餐次用餐。页面加载时从
app_setting 恢复上次选择（无则默认全选三餐）。确认后构建 plan → 生成配餐 → 跳转结果页。

路由：/diner_select
"""

from __future__ import annotations

from app.nav import navigate

from datetime import date

import flet as ft

from app import config
from app import theme
from app.services.member_service import (
    list_members,
    load_diner_selection,
    save_diner_selection,
    build_plan_from_selection,
)
from app.services.meal_planner import generate_daily_meals
from app.services.env_service import get_region
from app.pages.home_page import store_plan


def diner_select_page(page: ft.Page) -> ft.View:
    """构建就餐人员选择视图。"""
    members = list_members()
    last_sel = load_diner_selection()

    # 构建 member_id → selection dict 的映射
    sel_map: dict[int, dict] = {}
    if last_sel:
        for s in last_sel:
            if isinstance(s, dict) and "id" in s:
                sel_map[s["id"]] = s

    # 无成员时的空态提示
    if not members:
        body = ft.Column(
            [
                theme.text("还没有家庭成员", theme.SUBTITLE_TEXT,
                           color=theme.COLOR_ACCENT),
                ft.Container(height=12),
                theme.text("请先到「家庭成员管理」添加成员后再进行配餐。",
                           theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=20),
                theme.big_button("去添加成员", on_click=lambda e: navigate(page, "/member")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route="/diner_select",
            appbar=theme.app_bar("今日就餐人员",
                                 leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                       on_click=lambda e: navigate(page, "/home"))),
            controls=[body],
            padding=20,
            scroll=ft.ScrollMode.AUTO,
        )

    # 为每位成员创建三个 Checkbox
    member_cards: list[ft.Control] = []
    checkbox_map: dict[int, dict[str, ft.Checkbox]] = {}

    for m in members:
        # 从上次选择恢复，无则默认全选三餐
        prev = sel_map.get(m.id)
        if prev:
            val_b = bool(prev.get("breakfast", False))
            val_l = bool(prev.get("lunch", False))
            val_d = bool(prev.get("dinner", False))
        else:
            val_b = True
            val_l = True
            val_d = True

        cb_b = ft.Checkbox(label="早餐", value=val_b, label_style=theme.text_style(
            theme.LARGE_TEXT, theme.COLOR_TEXT))
        cb_l = ft.Checkbox(label="午餐", value=val_l, label_style=theme.text_style(
            theme.LARGE_TEXT, theme.COLOR_TEXT))
        cb_d = ft.Checkbox(label="晚餐", value=val_d, label_style=theme.text_style(
            theme.LARGE_TEXT, theme.COLOR_TEXT))

        checkbox_map[m.id] = {"breakfast": cb_b, "lunch": cb_l, "dinner": cb_d}

        age_name = config.AGE_TYPES.get(m.age_type, "未知")
        card = theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            theme.text(m.nick_name, theme.SUBTITLE_TEXT,
                                       color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                            ft.Container(width=8),
                            theme.text(f"（{age_name}）", theme.LARGE_TEXT,
                                       color=theme.COLOR_SECONDARY_TEXT),
                        ]
                    ),
                    ft.Container(height=6),
                    ft.Row([cb_b, cb_l, cb_d]),
                ]
            )
        )
        member_cards.append(card)

    # --- 确认配餐 ---
    def _on_confirm(e) -> None:
        """收集勾选状态 → 构建plan → 生成配餐 → 跳转结果页。"""
        selection: list[dict] = []
        for m in members:
            cbs = checkbox_map[m.id]
            sel = {
                "id": m.id,
                "breakfast": bool(cbs["breakfast"].value),
                "lunch": bool(cbs["lunch"].value),
                "dinner": bool(cbs["dinner"].value),
            }
            # 至少选了一餐才加入
            if sel["breakfast"] or sel["lunch"] or sel["dinner"]:
                selection.append(sel)

        if not selection:
            theme.snack(page, "请至少选择一位成员的一餐", theme.COLOR_ACCENT)
            return

        # 持久化选人记忆
        save_diner_selection(selection)

        # 构建用餐计划并生成配餐
        all_members = list_members()
        plan = build_plan_from_selection(all_members, selection)
        region = get_region()
        result = generate_daily_meals(date.today(), region, plan)
        store_plan(result, plan)
        navigate(page, "/result")

    body = ft.Column(
        [
            theme.text("勾选今日就餐人员及餐次", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=10),
            *member_cards,
            ft.Container(height=16),
            theme.big_button("确认配餐", icon=ft.Icons.RESTAURANT_MENU,
                             on_click=_on_confirm, width=400),
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/diner_select",
        appbar=theme.app_bar("今日就餐人员",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
