"""适老化主题样式工厂。

本模块统一提供大字号、大按钮、高对比配色与常用控件样式，全 APP 复用，
禁止在页面内硬编码字号与颜色。所有字号 / 颜色均通过本模块导出，便于
全局调优。

设计目标：正文 >= 20sp、标题 >= 28sp、按钮高度 >= 56dp、深字浅底高对比。
"""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------------------
# 字号（sp）
# ---------------------------------------------------------------------------
LARGE_TEXT: int = 20          # 正文基准
SUBTITLE_TEXT: int = 24       # 次级标题
TITLE_TEXT: int = 28          # 页面标题
BIG_TITLE_TEXT: int = 34      # 首页大标题
HINT_TEXT: int = 16           # 辅助说明（不低于 16，保证可读）

# ---------------------------------------------------------------------------
# 按钮最小高度（dp）
# ---------------------------------------------------------------------------
BUTTON_HEIGHT: int = 56

# ---------------------------------------------------------------------------
# 高对比配色
# ---------------------------------------------------------------------------
COLOR_BG: str = "#FFFFFF"               # 浅底
COLOR_SURFACE: str = "#F5F5F5"          # 卡片底
COLOR_PRIMARY: str = "#1B5E20"          # 主色：深绿（沉稳、养生感）
COLOR_PRIMARY_LIGHT: str = "#E8F5E9"    # 主色浅底
COLOR_ACCENT: str = "#C62828"           # 强调：暖红（开胃、醒目）
COLOR_ACCENT_LIGHT: str = "#FFEBEE"
COLOR_TEXT: str = "#212121"             # 主文字：近黑
COLOR_SECONDARY_TEXT: str = "#424242"   # 次级文字
COLOR_BORDER: str = "#9E9E9E"           # 边框
COLOR_DISABLED: str = "#BDBDBD"
COLOR_WHITE: str = "#FFFFFF"

# ---------------------------------------------------------------------------
# 字号样式工厂
# ---------------------------------------------------------------------------


def text_style(
    size: int = LARGE_TEXT,
    color: str = COLOR_TEXT,
    weight: ft.FontWeight = ft.FontWeight.NORMAL,
    italic: bool = False,
) -> ft.TextStyle:
    """生成统一的文字样式。

    Args:
        size: 字号 sp。
        color: 文字颜色。
        weight: 字重。
        italic: 是否斜体。

    Returns:
        ft.TextStyle 实例。
    """
    return ft.TextStyle(
        size=size,
        color=color,
        weight=weight,
        italic=italic,
    )


def title_style() -> ft.TextStyle:
    """页面大标题样式。"""
    return text_style(TITLE_TEXT, COLOR_PRIMARY, ft.FontWeight.BOLD)


def big_title_style() -> ft.TextStyle:
    """首页超大标题样式。"""
    return text_style(BIG_TITLE_TEXT, COLOR_PRIMARY, ft.FontWeight.BOLD)


def subtitle_style(color: str = COLOR_SECONDARY_TEXT) -> ft.TextStyle:
    """次级标题样式。"""
    return text_style(SUBTITLE_TEXT, color, ft.FontWeight.BOLD)


# ---------------------------------------------------------------------------
# 控件工厂
# ---------------------------------------------------------------------------


def text(value: str, size: int = LARGE_TEXT, **kwargs) -> ft.Text:
    """统一正文文本控件。"""
    style = kwargs.pop("style", None)
    if style is None:
        style = text_style(size, kwargs.pop("color", COLOR_TEXT),
                           kwargs.pop("weight", ft.FontWeight.NORMAL))
    return ft.Text(value, style=style, **kwargs)


def big_button(
    label: str,
    on_click=None,
    bgcolor: str = COLOR_PRIMARY,
    color: str = COLOR_WHITE,
    height: int = BUTTON_HEIGHT,
    width: Optional[int] = None,
    icon: Optional[str] = None,
    disabled: bool = False,
) -> ft.ElevatedButton:
    """适老化大按钮。"""
    return ft.ElevatedButton(
        label,
        on_click=on_click,
        bgcolor=bgcolor,
        color=color,
        height=height,
        width=width,
        icon=icon,
        disabled=disabled,
        style=ft.ButtonStyle(
            text_style=text_style(LARGE_TEXT, color, ft.FontWeight.BOLD),
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.padding.Padding(left=16, top=10, right=16, bottom=10),
        ),
    )


def card(content: ft.Control, padding: int = 16, bgcolor: str = COLOR_SURFACE) -> ft.Container:
    """统一卡片容器。"""
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=bgcolor,
        border_radius=12,
        border=ft.border.Border(ft.border.BorderSide(1, COLOR_BORDER)),
        margin=ft.margin.Margin(left=0, top=6, right=0, bottom=6),
    )


def app_bar(title: str, leading: Optional[ft.Control] = None,
            actions: Optional[list] = None) -> ft.AppBar:
    """统一顶部导航栏。"""
    return ft.AppBar(
        title=text(title, TITLE_TEXT, color=COLOR_WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=COLOR_PRIMARY,
        center_title=True,
        leading=leading,
        actions=actions or [],
    )


def divider() -> ft.Divider:
    """统一分隔线。"""
    return ft.Divider(height=1, color=COLOR_BORDER, thickness=1)


def snack(page: ft.Page, message: str, color: str = COLOR_PRIMARY) -> None:
    """弹出提示条。"""
    sb = ft.SnackBar(
        content=text(message, LARGE_TEXT, color=COLOR_WHITE),
        bgcolor=color,
    )
    sb.open = True
    page.show_dialog(sb)
    page.update()
