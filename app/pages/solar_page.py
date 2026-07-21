"""⑨ 节气养生知识库。

以可展开列表展示二十四节气（成渝地区）的气候特点、养生重点、宜食与
忌食食材。
"""

from __future__ import annotations

from app.nav import navigate

import flet as ft

from app import theme
from app.database import DB
from app.services.env_service import get_region


def solar_page(page: ft.Page) -> ft.View:
    """构建节气知识库视图。"""
    region = get_region()
    rows = DB.query(
        "SELECT * FROM solar_health_rule WHERE region_type = ? ORDER BY id ASC", [region]
    )
    if not rows:
        rows = DB.query("SELECT * FROM solar_health_rule ORDER BY id ASC")

    # 按节气去重（保留首个）
    seen = set()
    rules = []
    for r in rows:
        term = r["solar_term"]
        if term in seen:
            continue
        seen.add(term)
        rules.append(r)

    tiles = []
    for r in rules:
        recommend = r.get("recommend_food") or "[]"
        forbid = r.get("forbid_food") or "[]"
        import json
        try:
            rec = json.loads(recommend)
        except (ValueError, TypeError):
            rec = []
        try:
            forb = json.loads(forbid)
        except (ValueError, TypeError):
            forb = []

        detail = ft.Column(
            [
                theme.text("气候：" + (r.get("climate") or ""), theme.LARGE_TEXT,
                           color=theme.COLOR_TEXT),
                ft.Container(height=6),
                theme.text("养生重点：" + (r.get("health_core") or ""), theme.LARGE_TEXT,
                           color=theme.COLOR_TEXT),
                ft.Container(height=6),
                theme.text("宜食：" + ("、".join(rec) if rec else "无特殊"),
                           theme.LARGE_TEXT, color=theme.COLOR_PRIMARY),
                ft.Container(height=6),
                theme.text("忌食：" + ("、".join(forb) if forb else "无特殊"),
                           theme.LARGE_TEXT, color=theme.COLOR_ACCENT),
            ]
        )
        tiles.append(
            ft.ExpansionTile(
                title=theme.text(r["solar_term"], theme.SUBTITLE_TEXT,
                                 color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                subtitle=theme.text(r.get("health_core") or "", theme.HINT_TEXT,
                                    color=theme.COLOR_SECONDARY_TEXT),
                controls=[ft.Container(content=detail, padding=12)],
                expanded=False,
            )
        )

    body = ft.Column(
        [
            theme.text("二十四节气 · 成渝养生", theme.SUBTITLE_TEXT,
                       color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=8),
            *tiles,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/solar",
        appbar=theme.app_bar("节气养生知识",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
