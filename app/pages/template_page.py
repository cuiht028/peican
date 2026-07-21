# @deprecated V1.1: 模板功能已内联到 diner_select_page
"""⑤ 家庭模板管理。

保存 / 重命名 / 删除 / 应用家庭模板（日常 / 招待）。无对话框，全部用页面内交互。

.. deprecated:: V1.1
    模板功能已由 ``diner_select_page`` 内联实现（模板 Dropdown + 保存按钮），
    独立页面不再注册路由。保留文件仅为向后兼容参考。
"""

from __future__ import annotations

import flet as ft

from app import config
from app import theme
from app.models.template import UserTemplate
from app.services.member_service import (
    list_members,
    list_templates,
    save_template,
    delete_template,
    apply_template,
)


def template_page(page: ft.Page) -> ft.View:
    """构建模板管理视图（无对话框）。"""
    templates = list_templates()

    # --- 保存模板的表单（始终显示在页面顶部）---
    tpl_name = ft.TextField(label="模板名称", value="", text_size=theme.LARGE_TEXT, width=320,
                            label_style=theme.text_style(theme.LARGE_TEXT, theme.COLOR_SECONDARY_TEXT))
    tpl_type = ft.Dropdown(label="模板类型", width=320, text_size=theme.LARGE_TEXT,
                           options=[ft.dropdown.Option(key="1", text="日常"),
                                    ft.dropdown.Option(key="2", text="招待")],
                           value="1")
    tpl_guest_adult = ft.TextField(label="招待-成人访客数", value="0", width=150,
                                   text_size=theme.LARGE_TEXT,
                                   label_style=theme.text_style(theme.LARGE_TEXT,
                                                               theme.COLOR_SECONDARY_TEXT))
    tpl_guest_child = ft.TextField(label="招待-儿童数", value="0", width=150,
                                   text_size=theme.LARGE_TEXT,
                                   label_style=theme.text_style(theme.LARGE_TEXT,
                                                               theme.COLOR_SECONDARY_TEXT))

    def _save_new(e=None):
        family_config = [m.to_dict() for m in list_members()]
        try:
            gn = int(tpl_guest_adult.value or 0)
        except ValueError:
            gn = 0
        try:
            gc = int(tpl_guest_child.value or 0)
        except ValueError:
            gc = 0
        template = UserTemplate(
            template_name=tpl_name.value.strip() or "未命名模板",
            template_type=int(tpl_type.value or 1),
            family_config=family_config,
            guest_num=gn,
            guest_child_num=gc,
        )
        save_template(template)
        page.views.clear()
        page.views.append(template_page(page))
        page.update()

    save_form = theme.card(
        ft.Column([
            theme.text("保存当前家庭配置为模板", theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                       weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            tpl_name,
            tpl_type,
            ft.Row([tpl_guest_adult, tpl_guest_child]),
            ft.Container(height=8),
            theme.big_button("保存模板", width=320, on_click=_save_new),
        ])
    )

    # --- 模板列表 ---
    cards = []
    if not templates:
        cards.append(
            theme.text("还没有保存的模板。在上方填写名称后点击「保存模板」即可创建。",
                       theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT)
        )

    for t in templates:
        type_name = "日常" if t.template_type == 1 else "招待"
        sub = f"类型：{type_name}"
        if t.template_type == 2:
            sub += f"　访客成人 {t.guest_num} 人 / 儿童 {t.guest_child_num} 人"

        # 内联重命名输入框
        rename_field = ft.TextField(label="新名称", value=t.template_name,
                                    text_size=theme.LARGE_TEXT, width=200,
                                    label_style=theme.text_style(theme.LARGE_TEXT,
                                                                theme.COLOR_SECONDARY_TEXT))

        def _do_rename(e, tmpl=t, nf=rename_field):
            tmpl.template_name = nf.value.strip() or tmpl.template_name
            save_template(tmpl)
            page.views.clear()
            page.views.append(template_page(page))
            page.update()

        def _do_apply(e, tid=t.id):
            if apply_template(tid):
                theme.snack(page, "模板已应用", theme.COLOR_PRIMARY)
            else:
                theme.snack(page, "应用失败", theme.COLOR_ACCENT)
            page.views.clear()
            page.views.append(template_page(page))
            page.update()

        def _do_delete(e, tid=t.id):
            delete_template(tid)
            page.views.clear()
            page.views.append(template_page(page))
            page.update()

        card = theme.card(
            ft.Column([
                theme.text(t.template_name, theme.SUBTITLE_TEXT, color=theme.COLOR_PRIMARY,
                           weight=ft.FontWeight.BOLD),
                theme.text(sub, theme.LARGE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
                ft.Container(height=8),
                ft.Row([
                    theme.big_button("应用", width=110, height=48, on_click=_do_apply),
                    theme.big_button("删除", width=110, height=48, bgcolor=theme.COLOR_ACCENT,
                                     on_click=_do_delete),
                ]),
                ft.Row([rename_field,
                        theme.big_button("重命名", width=120, height=48,
                                         bgcolor=theme.COLOR_SECONDARY_TEXT,
                                         on_click=_do_rename)]),
            ])
        )
        cards.append(card)

    body = ft.Column(
        [
            save_form,
            ft.Container(height=12),
            theme.text("已保存的模板", theme.SUBTITLE_TEXT, color=theme.COLOR_SECONDARY_TEXT),
            ft.Container(height=8),
            *cards,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/template",
        appbar=theme.app_bar("家庭模板管理",
                             leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                   on_click=lambda e: page.go("/home"))),
        controls=[body],
        padding=16,
        scroll=ft.ScrollMode.AUTO,
    )
