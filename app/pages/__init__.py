"""页面层包：适老化页面构建函数。"""

from __future__ import annotations

from app.pages.splash_page import splash_page
from app.pages.home_page import home_page
from app.pages.member_page import member_page, member_edit_page
from app.pages.diner_select_page import diner_select_page
from app.pages.banquet_page import banquet_page
from app.pages.dish_library_page import dish_library_page
from app.pages.result_page import result_page
from app.pages.dish_detail_page import dish_detail_page
from app.pages.shopping_page import shopping_page
from app.pages.solar_page import solar_page

__all__ = [
    "splash_page",
    "home_page",
    "member_page",
    "member_edit_page",
    "diner_select_page",
    "banquet_page",
    "dish_library_page",
    "result_page",
    "dish_detail_page",
    "shopping_page",
    "solar_page",
]
