"""③ 家庭成员管理。

提供成员增删改查：出生年月（年 / 月下拉）、口味滑动条、
体质多选、忌口（分类 + 食材 + 素食）配置。编辑通过独立页面完成（无对话框）。
用餐餐次已移至「今日就餐人员」页，成员档案不再保存餐次。
"""

from __future__ import annotations

from app.nav import navigate

from datetime import date

import flet as ft

from app import config
from app import theme
from app.database import DB
from app.models.member import FamilyMember
from app.services.age_service import calc_age_type, age_label
from app.services.member_service import list_members, save_member, delete_member


def _year_options() -> list:
    cur = date.today().year
    return [ft.dropdown.Option(str(y)) for y in range(cur, 1919, -1)]


def _month_options() -> list:
    return [ft.dropdown.Option(f"{m:02d}") for m in range(1, 13)]


def _chunked_rows(items: list, n: int = 3) -> list:
    """将控件列表按每行 n 个分组为 Row 列表（用于多列布局）。"""
    rows = []
    for i in range(0, len(items), n):
        rows.append(ft.Row(items[i:i + n]))
    return rows


def member_page(page: ft.Page) -> ft.View:
    """构建家庭成员管理视图。"""
    members = list_members()

    cards = []
    if not members:
        cards.append(
            theme.text("还没有家庭成员，点击下方按钮添加第一位吧。",
                       theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT)
        )

    for m in members:
        m_dict = m.to_dict()
        card = theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            theme.text(m_dict["nick_name"], theme.SUBTITLE_TEXT,
                                       color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                            theme.text("（" + m_dict["age_name"] + "）", theme.LARGE_TEXT,
                                       color=theme.COLOR_SECONDARY_TEXT),
                            ft.Container(expand=True),
                            ft.IconButton(ft.Icons.EDIT, tooltip="编辑",
                                          on_click=lambda e, mid=m.id: navigate(page, f"/member_edit/{mid}")),
                            ft.IconButton(ft.Icons.DELETE, tooltip="删除",
                                          icon_color=theme.COLOR_ACCENT,
                                          on_click=lambda e, mid=m.id: _do_delete(page, mid)),
                        ]
                    ),
                    theme.text(
                        "体质：" + ("、".join(m_dict["health_tag"]) if m_dict["health_tag"] else "无"),
                        theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT,
                    ),
                ]
            )
        )
        cards.append(card)

    add_btn = theme.big_button("添加家庭成员", icon=ft.Icons.ADD,
                               width=400, on_click=lambda e: navigate(page, "/member_edit"))

    body = ft.Column(
        [
            theme.text(f"共 {len(members)} 位家庭成员", theme.LARGE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=8),
            *cards,
            ft.Container(height=16),
            add_btn,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/member",
        appbar=theme.app_bar("家庭成员管理",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )


def member_edit_page(page: ft.Page) -> ft.View:
    """成员编辑/新增页面（独立页面，非对话框）。"""
    # 从路由解析成员 ID
    parts = page.route.split("/")
    editing_id = 0
    if len(parts) >= 3 and parts[2].isdigit():
        editing_id = int(parts[2])

    member = None
    if editing_id:
        for m in list_members():
            if m.id == editing_id:
                member = m
                break

    default_year = str(date.today().year - 30)
    default_month = "01"
    if member and member.birth_ym:
        bp = member.birth_ym.split("-")
        if len(bp) == 2:
            default_year, default_month = bp[0], bp[1]

    name_field = ft.TextField(
        label="昵称", value=member.nick_name if member else "",
        text_size=theme.LARGE_TEXT, width=320,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
    )
    year_dd = ft.Dropdown(label="出生年", options=_year_options(), value=default_year,
                          width=150, text_size=theme.LARGE_TEXT)
    month_dd = ft.Dropdown(label="出生月", options=_month_options(), value=default_month,
                           width=120, text_size=theme.LARGE_TEXT)
    _initial_age = age_label(calc_age_type(f"{default_year}-{default_month}"))
    age_text = theme.text("推算年龄层：" + _initial_age, theme.LARGE_TEXT, color=theme.COLOR_PRIMARY)

    taste_sliders = {}
    taste_labels = {}

    def _on_taste(e, dim, lbl) -> None:
        lbl.value = config.TASTE_DIM_NAMES[dim] + "：" + config.TASTE_LABELS[int(e.control.value)]
        page.update()

    for dim in config.TASTE_DIMS:
        default_val = int((member.taste.get(dim, config.BASE_TASTE[dim])) if member else config.BASE_TASTE[dim])
        lbl = theme.text(config.TASTE_DIM_NAMES[dim] + "：" + config.TASTE_LABELS[default_val],
                         theme.LARGE_TEXT, color=theme.COLOR_TEXT)
        sl = ft.Slider(min=1, max=4, divisions=3, value=default_val, width=240,
                       on_change=lambda e, d=dim, l=lbl: _on_taste(e, d, l))
        taste_sliders[dim] = sl
        taste_labels[dim] = lbl

    health_cbs = {
        tag: ft.Checkbox(label=tag, value=tag in (member.health_tag if member else []))
        for tag in config.HEALTH_TAGS
    }
    avoid_cbs = {
        cat: ft.Checkbox(label=cat, value=cat in ((member.avoid_food.get("categories", [])) if member else []))
        for cat in config.AVOID_CATS
    }
    avoid_items = ft.TextField(
        label="忌口食材（逗号分隔，如 牛肉、虾）",
        value=",".join((member.avoid_food.get("items", [])) if member else []),
        text_size=theme.LARGE_TEXT, width=320,
        label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT),
    )
    veg_switch = ft.Switch(label="素食（剔除荤腥）",
                           value=bool((member.avoid_food.get("vegetarian", False)) if member else False))

    def _refresh_age(e=None) -> None:
        ym = f"{year_dd.value}-{month_dd.value}"
        at = calc_age_type(ym)
        age_text.value = "推算年龄层：" + age_label(at)
        page.update()

    year_dd.on_change = _refresh_age
    month_dd.on_change = _refresh_age

    def _on_save(e=None) -> None:
        ym = f"{year_dd.value}-{month_dd.value}"
        taste = {d: int(taste_sliders[d].value) for d in config.TASTE_DIMS}
        avoid_food = {
            "categories": [c for c, cb in avoid_cbs.items() if cb.value],
            "items": [x.strip() for x in avoid_items.value.split(",") if x.strip()],
            "vegetarian": bool(veg_switch.value),
        }
        health_tag = [t for t, cb in health_cbs.items() if cb.value]
        new_member = FamilyMember(
            nick_name=name_field.value.strip() or "家人",
            birth_ym=ym,
            age_type=calc_age_type(ym),
            is_eat_breakfast=1,
            is_eat_lunch=1,
            is_eat_dinner=1,
            taste=taste,
            avoid_food=avoid_food,
            health_tag=health_tag,
            member_id=editing_id,
        )
        save_member(new_member)
        navigate(page, "/member")

    body = ft.Column(
        [
            name_field,
            ft.Row([year_dd, month_dd]),
            age_text,
            ft.Container(height=6),
            theme.text("口味偏好（1 无 / 2 微 / 3 中 / 4 重）", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_PRIMARY),
            *[ft.Row([taste_labels[d], taste_sliders[d]]) for d in config.TASTE_DIMS],
            ft.Container(height=6),
            theme.text("体质 / 健康标签", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY),
            *_chunked_rows([health_cbs[t] for t in config.HEALTH_TAGS], 3),
            ft.Container(height=6),
            theme.text("忌口设置", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY),
            *_chunked_rows([avoid_cbs[c] for c in config.AVOID_CATS], 3),
            avoid_items,
            veg_switch,
            ft.Container(height=16),
            ft.Row([
                theme.big_button("保存", width=160, on_click=_on_save),
                theme.big_button("取消", width=160, bgcolor=theme.COLOR_SECONDARY_TEXT,
                                 on_click=lambda e: navigate(page, "/member")),
            ]),
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/member_edit",
        appbar=theme.app_bar("编辑成员" if editing_id else "添加成员",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/member"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )


def _eat_summary(m_dict: dict) -> str:
    parts = []
    if m_dict.get("is_eat_breakfast"):
        parts.append("早")
    if m_dict.get("is_eat_lunch"):
        parts.append("午")
    if m_dict.get("is_eat_dinner"):
        parts.append("晚")
    return "、".join(parts) if parts else "均未用餐"


def _do_delete(page: ft.Page, member_id: int) -> None:
    """直接删除成员并刷新列表（无确认对话框）。"""
    delete_member(member_id)
    page.views.clear()
    page.views.append(member_page(page))
    page.update()
