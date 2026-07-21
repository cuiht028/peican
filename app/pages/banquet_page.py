"""③b 家庭宴请配餐页。

选择参加宴请的家庭成员 + 输入访客成人/儿童/老人数 + 选择餐次（午餐/晚餐），
确认后构建含虚拟访客的 plan → 生成配餐 → 跳转结果页。

路由：/banquet
"""

from __future__ import annotations

from app.nav import navigate

from datetime import date

import flet as ft

from app import config
from app import theme
from app.services.member_service import (
    list_members,
    load_banquet_selection,
    save_banquet_selection,
    build_banquet_plan,
)
from app.services.meal_planner import generate_daily_meals
from app.services.env_service import get_region
from app.pages.home_page import store_plan


def banquet_page(page: ft.Page) -> ft.View:
    """构建宴请配餐视图。"""
    members = list_members()
    last_sel = load_banquet_selection()

    # 从上次选择恢复
    prev_ids: set = set()
    prev_adults = 0
    prev_children = 0
    prev_elderly = 0
    prev_meal = "dinner"
    if last_sel:
        prev_ids = set(last_sel.get("member_ids", []))
        prev_adults = int(last_sel.get("guest_adults", 0))
        prev_children = int(last_sel.get("guest_children", 0))
        prev_elderly = int(last_sel.get("guest_elderly", 0))
        prev_meal = last_sel.get("meal_key", "dinner")

    # 无成员时的空态提示
    if not members:
        body = ft.Column(
            [
                theme.text("还没有家庭成员", theme.SUBTITLE_TEXT,
                           color=theme.COLOR_ACCENT),
                ft.Container(height=12),
                theme.text("请先到「家庭成员管理」添加成员后再进行宴请配餐。",
                           theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=20),
                theme.big_button("去添加成员", on_click=lambda e: navigate(page, "/member")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route="/banquet",
            appbar=theme.app_bar("家庭宴请配餐",
                                 leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                       on_click=lambda e: navigate(page, "/home"))),
            controls=[body],
            padding=20,
            scroll=ft.ScrollMode.AUTO,
        )

    # 成员 Checkbox 列表
    member_checks: list[ft.Control] = []
    check_map: dict[int, ft.Checkbox] = {}
    for m in members:
        age_name = config.AGE_TYPES.get(m.age_type, "未知")
        cb = ft.Checkbox(
            label=f"{m.nick_name}（{age_name}）",
            value=m.id in prev_ids,
            label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_TEXT),
        )
        check_map[m.id] = cb
        member_checks.append(cb)

    # 访客人数输入
    guest_adults = ft.TextField(
        label="成人访客数",
        value=str(prev_adults),
        width=150,
        text_size=theme.LARGE_TEXT,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    guest_children = ft.TextField(
        label="儿童数",
        value=str(prev_children),
        width=150,
        text_size=theme.LARGE_TEXT,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    guest_elderly = ft.TextField(
        label="老人数",
        value=str(prev_elderly),
        width=150,
        text_size=theme.LARGE_TEXT,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # 餐次选择
    meal_radio = ft.RadioGroup(
        value=prev_meal,
        content=ft.Row(
            [
                ft.Radio(
                    value="lunch",
                    label="午餐",
                    label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_TEXT),
                ),
                ft.Radio(
                    value="dinner",
                    label="晚餐",
                    label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_TEXT),
                ),
            ]
        ),
    )

    def _on_start(e) -> None:
        """收集选择 → 构建宴请plan → 生成配餐 → 跳转结果页。"""
        # 选中的家庭成员 ID
        member_ids = [mid for mid, cb in check_map.items() if cb.value]

        # 解析访客数（容错）
        def _parse_int(tf: ft.TextField) -> int:
            try:
                return max(0, int(tf.value or 0))
            except (ValueError, TypeError):
                return 0

        adults = _parse_int(guest_adults)
        children = _parse_int(guest_children)
        elderly = _parse_int(guest_elderly)
        meal_key = meal_radio.value or "dinner"

        # 至少有1人（家庭成员或访客）
        total_people = len(member_ids) + adults + children + elderly
        if total_people == 0:
            theme.snack(page, "请至少选择一位家庭成员或输入访客人数", theme.COLOR_ACCENT)
            return

        # 持久化宴请选择
        sel_data = {
            "member_ids": member_ids,
            "guest_adults": adults,
            "guest_children": children,
            "guest_elderly": elderly,
            "meal_key": meal_key,
        }
        save_banquet_selection(sel_data)

        # 构建宴请计划并生成配餐
        all_members = list_members()
        plan = build_banquet_plan(
            all_members, member_ids, adults, children, elderly, meal_key,
        )
        region = get_region()
        result = generate_daily_meals(date.today(), region, plan)
        store_plan(result, plan)
        navigate(page, "/result")

    body = ft.Column(
        [
            theme.text("选择参加宴请的家庭成员", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=10),
            theme.card(
                ft.Column(member_checks)
            ),
            ft.Container(height=12),
            theme.text("访客人数", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            ft.Row([guest_adults, guest_children, guest_elderly], wrap=True),
            ft.Container(height=16),
            theme.text("餐次选择", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            meal_radio,
            ft.Container(height=20),
            theme.big_button("开始配餐", icon=ft.Icons.RESTAURANT_MENU,
                             on_click=_on_start),
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/banquet",
        appbar=theme.app_bar("家庭宴请配餐",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
