"""⑥ 今日配餐结果。

分栏展示早 / 午 / 晚菜单，每道菜可点击选中（深色高亮）再「更换配菜」；
提供重新配餐、买菜清单、保存等操作。
"""

from __future__ import annotations

from app.nav import navigate

from datetime import date

import flet as ft

from app import config
from app import theme
from app.pages.home_page import get_last, store_plan
from app.services.meal_planner import generate_daily_meals, replace_dish
from app.services.env_service import get_region

# 选中态配色
_COLOR_SELECTED = theme.COLOR_SURFACE_ALT
_COLOR_NORMAL = theme.COLOR_SURFACE


def result_action_labels() -> tuple[str, str, str, str]:
    """返回结果页四个操作的固定展示顺序。"""
    return "重新配餐", "更替选菜", "买菜清单", "保存配餐"


def build_result_action_grid(buttons: list[ft.Control]) -> ft.Column:
    """将四个操作按钮固定为两行两列，避免窄屏横向溢出。"""
    if len(buttons) != 4:
        raise ValueError("结果操作区必须包含四个按钮")
    rows: list[ft.Row] = []
    for start_index in range(0, 4, 2):
        rows.append(
            ft.Row(
                controls=[
                    ft.Container(content=buttons[start_index], expand=True),
                    ft.Container(content=buttons[start_index + 1], expand=True),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        )
    return ft.Column(controls=rows, spacing=8)


def result_page(page: ft.Page) -> ft.View:
    """构建配餐结果视图。"""
    result, plan = get_last()

    if result is None:
        body = ft.Column(
            [
                theme.text("还没有生成配餐结果", theme.SUBTITLE_TEXT, color=theme.COLOR_ACCENT),
                ft.Container(height=12),
                theme.text("请先在首页点击「今日一键配餐」。", theme.LARGE_TEXT,
                           color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=20),
                theme.big_button("去配餐", on_click=lambda e: navigate(page, "/home")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route="/result",
            appbar=theme.app_bar("今日配餐",
                                 leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                       on_click=lambda e: navigate(page, "/home"))),
            controls=[body],
            padding=20,
        )

    # 选中状态：{(meal_key, dish_index): True}
    selected: dict[tuple, bool] = {}

    header = theme.card(
        ft.Column(
            [
                ft.Row(
                    [
                        theme.text("当前节气：", theme.LARGE_TEXT,
                                   color=theme.COLOR_SECONDARY_TEXT),
                        theme.text(result["term"], theme.SUBTITLE_TEXT,
                                   color=theme.COLOR_ACCENT, weight=ft.FontWeight.BOLD),
                    ]
                ),
                ft.Container(height=6),
                theme.text("养生提示：" + result["health_tip"], theme.LARGE_TEXT,
                           color=theme.COLOR_TEXT),
                ft.Container(height=6),
                theme.text("点击菜品可选中（变绿），再点「更替选菜」替换选中菜品",
                           theme.HINT_TEXT, color=theme.COLOR_SECONDARY_TEXT),
            ]
        )
    )

    sections = [header]
    # 保存菜品卡引用，便于刷新
    dish_containers: dict[tuple, ft.Container] = {}

    for meal_key in config.MEAL_KEYS:
        dishes = result["meals"].get(meal_key, []) or []
        dish_controls = []
        if not dishes:
            dish_controls.append(
                theme.text("（暂无合适菜品，可调整成员忌口 / 体质后重试）",
                           theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT)
            )
        for idx, dish in enumerate(dishes):
            key = (meal_key, idx)
            dish_id = dish["id"]
            # 左侧：点击切换选中（变色）
            name_area = ft.Container(
                content=ft.Row(
                    [
                        theme.text(dish["dish_name"], theme.LARGE_TEXT,
                                   color=theme.COLOR_TEXT, weight=ft.FontWeight.BOLD),
                        theme.text("【" + dish["dish_type_name"] + "】", theme.HINT_TEXT,
                                   color=theme.COLOR_PRIMARY),
                    ],
                ),
                bgcolor=_COLOR_NORMAL,
                border_radius=8,
                padding=12,
                expand=True,
                on_click=lambda e, k=key: _toggle_select(k, selected, dish_containers, page),
            )
            container = ft.Container(
                content=ft.Row(
                    [
                        name_area,
                        ft.IconButton(
                            ft.Icons.DESCRIPTION,
                            tooltip="查看菜谱",
                            icon_color=theme.COLOR_PRIMARY,
                            on_click=lambda e, did=dish_id: navigate(page, f"/dish/{did}"),
                        ),
                    ],
                ),
            )
            dish_containers[key] = name_area
            dish_controls.append(container)

        section = theme.card(
            ft.Column(
                [
                    theme.text(config.MEAL_KEY_NAMES[meal_key], theme.SUBTITLE_TEXT,
                               color=theme.COLOR_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Container(height=6),
                    *dish_controls,
                ]
            )
        )
        sections.append(section)

    def _on_replace(e=None) -> None:
        """更换选中的菜品。"""
        sel_keys = [k for k, v in selected.items() if v]
        if not sel_keys:
            theme.snack(page, "请先点击选中要更换的菜品", theme.COLOR_ACCENT)
            return

        region = get_region()
        changed = 0
        for meal_key, idx in sel_keys:
            dishes = result["meals"].get(meal_key, [])
            if idx >= len(dishes):
                continue
            old_dish = dishes[idx]
            current_ids = {d["id"] for d in dishes}
            new_dish = replace_dish(date.today(), region, plan, meal_key,
                                    old_dish["id"], current_ids)
            if new_dish:
                result["meals"][meal_key][idx] = new_dish
                changed += 1

        # 清空选中状态
        selected.clear()
        store_plan(result, plan)

        if changed:
            theme.snack(page, f"已更换 {changed} 道菜", theme.COLOR_PRIMARY)
            page.views.clear()
            page.views.append(result_page(page))
            page.update()
        else:
            theme.snack(page, "没有可替换的候选菜品", theme.COLOR_ACCENT)

    def _on_regenerate(e=None) -> None:
        """保留条件重配，并优先生成一整套明显不同的菜单。"""
        rotation_date = date.today()
        previous_meals = result.get("meals", {})
        previous_ids = {
            int(dish.get("id", 0))
            for dishes in previous_meals.values()
            for dish in dishes
            if dish.get("id")
        }
        previous_seed = int(result.get("_rotation_seed", 0))
        refreshed_result = None

        # 从上次成功 seed 继续向后轮换，避免反复命中同一批候选。
        for rotation_seed in range(previous_seed + 1, previous_seed + 9):
            candidate = generate_daily_meals(
                rotation_date,
                get_region(),
                plan,
                rotation_seed=rotation_seed,
                avoid_dish_ids=previous_ids,
            )
            candidate_ids = {
                int(dish.get("id", 0))
                for dishes in candidate.get("meals", {}).values()
                for dish in dishes
                if dish.get("id")
            }
            if candidate.get("meals") != previous_meals and candidate_ids - previous_ids:
                candidate["_rotation_seed"] = rotation_seed
                refreshed_result = candidate
                break

        if refreshed_result is None:
            theme.snack(page, "当前忌口和营养条件下，暂未找到更明显的整套替换菜单", theme.COLOR_ACCENT)
            return

        store_plan(refreshed_result, plan)
        theme.snack(page, "已重新配餐，整体菜单已更新", theme.COLOR_PRIMARY)
        page.views.clear()
        page.views.append(result_page(page))
        page.update()

    def _on_shopping(e=None) -> None:
        """跳转买菜清单。"""
        navigate(page, "/shopping")

    regenerate_label, replace_label, shopping_label, save_label = result_action_labels()
    actions = build_result_action_grid(
        [
            theme.big_button(regenerate_label, icon=ft.Icons.REFRESH,
                             on_click=_on_regenerate),
            theme.big_button(replace_label, icon=ft.Icons.SWAP_HORIZ,
                             bgcolor=theme.COLOR_PRIMARY_LIGHT, color=theme.COLOR_TEXT,
                             on_click=_on_replace),
            theme.big_button(shopping_label, icon=ft.Icons.SHOPPING_CART,
                             bgcolor=theme.COLOR_DEEP, on_click=_on_shopping),
            theme.big_button(save_label, icon=ft.Icons.SAVE,
                             bgcolor=theme.COLOR_SECONDARY_TEXT,
                             on_click=lambda e: theme.snack(page, "今日配餐已保存",
                                                            theme.COLOR_PRIMARY)),
        ]
    )

    body = ft.Column(
        [
            *sections,
            ft.Container(height=12),
            actions,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/result",
        appbar=theme.app_bar("今日配餐",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: navigate(page, "/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )


def _toggle_select(key, selected, containers, page) -> None:
    """切换菜品选中状态（点击卡片切换深色高亮）。"""
    if selected.get(key):
        selected[key] = False
        containers[key].bgcolor = _COLOR_NORMAL
    else:
        selected[key] = True
        containers[key].bgcolor = _COLOR_SELECTED
    page.update()
