# @deprecated V1.1: 功能已合并到 diner_select_page
"""④ 三餐用餐配置。

为每位家庭成员勾选其今日用餐的餐次（早 / 午 / 晚），即时保存到数据库。

.. deprecated:: V1.1
    本页面的功能已合并到 ``diner_select_page``（/diner_select 路由），
    不再注册路由。保留文件仅为向后兼容参考。
"""

from __future__ import annotations

import flet as ft

from app import theme
from app.models.member import FamilyMember
from app.services.member_service import list_members, save_member


def meal_config_page(page: ft.Page) -> ft.View:
    """构建三餐配置视图。"""
    members = list_members()

    cards = []
    if not members:
        cards.append(
            theme.text("还没有家庭成员，请先到「家庭成员」添加。",
                       theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT)
        )

    for m in members:
        sw_b = ft.Switch(label="早餐", value=bool(m.is_eat_breakfast))
        sw_l = ft.Switch(label="午餐", value=bool(m.is_eat_lunch))
        sw_d = ft.Switch(label="晚餐", value=bool(m.is_eat_dinner))

        sw_b.on_change = _make_handler(page, m, "breakfast", sw_b)
        sw_l.on_change = _make_handler(page, m, "lunch", sw_l)
        sw_d.on_change = _make_handler(page, m, "dinner", sw_d)

        card = theme.card(
            ft.Column(
                [
                    theme.text(m.nick_name, theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                               weight=ft.FontWeight.BOLD),
                    ft.Row([sw_b, sw_l, sw_d]),
                ]
            )
        )
        cards.append(card)

    body = ft.Column(
        [
            theme.text("勾选每位家人今日用餐的餐次", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=8),
            *cards,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/meal_config",
        appbar=theme.app_bar("三餐用餐配置",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: page.go("/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )


def _make_handler(page: ft.Page, member: FamilyMember, meal: str, switch: ft.Switch):
    """生成开关变更处理器。"""
    field = {
        "breakfast": "is_eat_breakfast",
        "lunch": "is_eat_lunch",
        "dinner": "is_eat_dinner",
    }[meal]

    def _handler(e) -> None:
        setattr(member, field, 1 if switch.value else 0)
        save_member(member)
        theme.snack(page, f"已更新 {member.nick_name} 的{meal}用餐", theme.COLOR_PRIMARY)

    return _handler
