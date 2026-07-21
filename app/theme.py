"""全应用视觉令牌与可复用 Flet 控件工厂。"""

from __future__ import annotations

from typing import Optional

import flet as ft

LARGE_TEXT: int = 18
SUBTITLE_TEXT: int = 22
TITLE_TEXT: int = 27
BIG_TITLE_TEXT: int = 33
HINT_TEXT: int = 15
BUTTON_HEIGHT: int = 44

# 自然、低刺激的家庭配餐色板。
COLOR_BG: str = "#F5F5F0"
COLOR_SURFACE: str = "#E8EADD"
COLOR_SURFACE_ALT: str = "#D2D7BF"
COLOR_BORDER: str = "#B5BD99"
COLOR_PRIMARY: str = "#808C50"
COLOR_PRIMARY_LIGHT: str = "#9AA477"
COLOR_TEXT: str = "#363C2B"
COLOR_SECONDARY_TEXT: str = "#4B5437"
COLOR_DEEP: str = "#3E4430"
COLOR_ACCENT: str = COLOR_DEEP
COLOR_ACCENT_LIGHT: str = COLOR_SURFACE_ALT
COLOR_DISABLED: str = "#B5BD99"
COLOR_WHITE: str = "#FFFFFF"


def text_style(
    size: int = LARGE_TEXT,
    color: str = COLOR_TEXT,
    weight: ft.FontWeight = ft.FontWeight.NORMAL,
    italic: bool = False,
) -> ft.TextStyle:
    """返回统一、深色可读的文本样式。"""
    return ft.TextStyle(size=size, color=color, weight=weight, italic=italic)


def title_style() -> ft.TextStyle:
    """返回页面标题样式。"""
    return text_style(TITLE_TEXT, COLOR_DEEP, ft.FontWeight.BOLD)


def big_title_style() -> ft.TextStyle:
    """返回首页标题样式。"""
    return text_style(BIG_TITLE_TEXT, COLOR_DEEP, ft.FontWeight.BOLD)


def subtitle_style(color: str = COLOR_SECONDARY_TEXT) -> ft.TextStyle:
    """返回分区标题样式。"""
    return text_style(SUBTITLE_TEXT, color, ft.FontWeight.BOLD)


def text(value: str, size: int = LARGE_TEXT, **kwargs: object) -> ft.Text:
    """创建会自然换行的统一文本控件。"""
    style: Optional[ft.TextStyle] = kwargs.pop("style", None)  # type: ignore[assignment]
    if style is None:
        style = text_style(
            size,
            kwargs.pop("color", COLOR_TEXT),  # type: ignore[arg-type]
            kwargs.pop("weight", ft.FontWeight.NORMAL),  # type: ignore[arg-type]
        )
    return ft.Text(value=value, style=style, selectable=False, **kwargs)  # type: ignore[arg-type]


def big_button(
    label: str,
    on_click: object = None,
    bgcolor: str = COLOR_PRIMARY,
    color: str = COLOR_WHITE,
    height: int = BUTTON_HEIGHT,
    width: Optional[int] = None,
    icon: Optional[str] = None,
    disabled: bool = False,
) -> ft.ElevatedButton:
    """创建最小 44dp 点击区域、窄屏不依赖固定宽度的大按钮。"""
    return ft.ElevatedButton(
        content=label,
        on_click=on_click,  # type: ignore[arg-type]
        bgcolor=bgcolor,
        color=color,
        height=max(BUTTON_HEIGHT, height),
        width=width,
        icon=icon,
        disabled=disabled,
        style=ft.ButtonStyle(
            text_style=text_style(LARGE_TEXT, color, ft.FontWeight.BOLD),
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ),
    )


def card(content: ft.Control, padding: int = 16, bgcolor: str = COLOR_SURFACE) -> ft.Container:
    """创建带自然底色和边界的自适应卡片。"""
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=bgcolor,
        border_radius=14,
        border=ft.Border.all(1, COLOR_BORDER),
        margin=ft.Margin.symmetric(vertical=6),
    )


def app_bar(
    title: str,
    leading: Optional[ft.Control] = None,
    actions: Optional[list[ft.Control]] = None,
) -> ft.AppBar:
    """创建高对比应用栏。"""
    return ft.AppBar(
        title=text(title, TITLE_TEXT, color=COLOR_WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=COLOR_DEEP,
        center_title=True,
        leading=leading,
        actions=actions or [],
    )


def divider() -> ft.Divider:
    """创建主题分隔线。"""
    return ft.Divider(height=1, color=COLOR_BORDER, thickness=1)


def snack(page: ft.Page, message: str, color: str = COLOR_DEEP) -> None:
    """显示高对比操作提示。"""
    snackbar = ft.SnackBar(content=text(message, color=COLOR_WHITE), bgcolor=color)
    snackbar.open = True
    page.show_dialog(snackbar)
    page.update()
