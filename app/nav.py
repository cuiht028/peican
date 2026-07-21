"""页面导航工具。

替代 flet 0.86 中不可靠的 page.go()（asyncio.create_task 有时不触发 on_route_change）。
通过直接设置 page.route 并调用 on_route_change 事件处理器来可靠导航。
"""


def navigate(page, route: str) -> None:
    """设置路由并触发 on_route_change 重建视图。"""
    page.route = route
    if page.on_route_change:
        page.on_route_change(None)
