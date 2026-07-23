"""「家庭四季养生配餐 APP V1.0」核心逻辑单元测试。

使用 Python 标准库 ``unittest``，不引入任何额外依赖（flet 可能未安装）。
所有数据库访问均在临时 SQLite 文件上进行，绝不污染交付目录的 ``meal.db``。

覆盖范围：
  * ``age_service``    — 年龄层级边界值
  * ``env_service``     — 寿星公式节气计算 + detect 默认地域
  * ``seed_loader``     — 幂等性（24 节气 / 80 菜 / 87 食材）
  * ``member_service``  — 成员 CRUD + build_today_plan 聚合
  * ``meal_planner``    — ★核心配餐算法（素食 / 忌口 / 确定性 / 三餐结构 / 空成员）
  * ``shopping_service``— 买菜清单分类聚合 + 克斤换算 + 年龄系数

遵循 Google Python 风格指南（PEP8）。
"""

from __future__ import annotations

import atexit
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter

import flet as ft
from datetime import date

# ---------------------------------------------------------------------------
# 路径与真实数据库保护
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 在 import app.database 之前记录真实 meal.db 是否存在，
# 以便测试结束后清理「本次运行产生的空文件」，避免污染交付目录。
_REAL_DB_PATH = os.path.join(_PROJECT_ROOT, "meal.db")
_real_db_existed = os.path.exists(_REAL_DB_PATH)

import app.database as db_mod  # noqa: E402  (会在 import 时连接真实库)
from app import config, theme  # noqa: E402
from app.models.member import FamilyMember  # noqa: E402
from app.data.seed_loader import run as seed_run  # noqa: E402
from app.services.age_service import calc_age_type, age_label  # noqa: E402
from app.services.env_service import (  # noqa: E402
    get_solar_term,
    detect,
    get_region,
)
from app.services.member_service import (  # noqa: E402
    save_member,
    get_member,
    list_members,
    delete_member,
    member_count,
    build_today_plan,
    build_plan_from_selection,
    build_banquet_plan,
    save_diner_selection,
    load_diner_selection,
    save_banquet_selection,
    load_banquet_selection,
)
from app.services.meal_planner import (  # noqa: E402
    _RECENT_MEAL_HISTORY,
    _adjust_structure_for_noodle,
    _is_noodle_staple,
    generate_daily_meals,
    replace_dish,
)
from app.services.shopping_service import (  # noqa: E402
    build_shopping_list,
    convert_weight,
    is_shopping_ingredient,
)
from app.pages.diner_select_page import (  # noqa: E402
    build_meal_checkbox_row,
    diner_select_page,
)
from app.pages.member_page import (  # noqa: E402
    build_taste_preference_row,
    member_page,
    member_edit_page,
)
from app.pages.dish_detail_page import dish_detail_page  # noqa: E402
from app.pages.result_page import (  # noqa: E402
    build_result_action_grid,
    result_action_labels,
)
from app.pages.dish_detail_page import build_recipe_details  # noqa: E402


@atexit.register
def _cleanup_real_db() -> None:
    """解释器退出时关闭真实连接，并删除本次运行产生的空 meal.db。"""
    try:
        if db_mod.DB.conn is not None:
            db_mod.DB.conn.close()
    except Exception:
        pass
    try:
        if os.path.exists(_REAL_DB_PATH) and os.path.getsize(_REAL_DB_PATH) == 0:
            os.remove(_REAL_DB_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 测试基类：管理临时数据库与连接重定向
# ---------------------------------------------------------------------------
class BaseDBTest(unittest.TestCase):
    """每个测试类使用独立的临时数据库，并复用同一份种子数据。"""

    _tmpdir: str = ""
    _db_path: str = ""
    _orig_conn = None
    _orig_path: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.mkdtemp(prefix="mealqa_")
        cls._db_path = os.path.join(cls._tmpdir, "test_meal.db")
        cls._orig_conn = db_mod.DB.conn
        cls._orig_path = db_mod.DB.db_path

        conn = sqlite3.connect(cls._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        db_mod.DB.conn = conn
        db_mod.DB.db_path = cls._db_path
        db_mod.DB.init_schema()
        seed_run()

    @classmethod
    def tearDownClass(cls) -> None:
        db_mod.DB.conn.close()
        db_mod.DB.conn = cls._orig_conn
        db_mod.DB.db_path = cls._orig_path
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def _reseed(self) -> None:
        """清空全部表并重新写入种子数据，保证每个用例处于干净状态。"""
        for table in (
            "family_member",
            "user_template",
            "solar_health_rule",
            "dish_main",
            "ingredient",
            "app_setting",
        ):
            db_mod.DB.execute(f"DELETE FROM {table}")
        seed_run()

    def _clear_members(self) -> None:
        db_mod.DB.execute("DELETE FROM family_member")

    def _insert_dish(
        self,
        dish_name: str,
        dish_type: int,
        main_ingredients: list,
        region_type: int = 1,
    ) -> None:
        """向 dish_main 插入一条受控菜品（用于忌口机制的精准验证）。"""
        db_mod.DB.execute(
            "INSERT INTO dish_main "
            "(dish_name, dish_type, region_type, spicy_level, numb_level, "
            "acid_level, salt_level, sweet_level, main_ingredients) "
            "VALUES (?, ?, ?, 2, 2, 1, 2, 1, ?)",
            [
                dish_name,
                dish_type,
                region_type,
                config.json_encode(main_ingredients),
            ],
        )

    @staticmethod
    def _count_types(dishes: list) -> Counter:
        return Counter(d["dish_type"] for d in dishes)

    def _all_dishes(self, result: dict) -> list:
        out = []
        for meal in config.MEAL_KEYS:
            out.extend(result["meals"][meal])
        return out


# ---------------------------------------------------------------------------
# 1. age_service — 年龄层级边界值（纯函数，无需数据库）
# ---------------------------------------------------------------------------
class TestAgeService(unittest.TestCase):
    TODAY = date(2024, 7, 1)  # 固定参考日期，保证可复现

    def test_boundary_ages(self) -> None:
        cases = [
            # (出生年月, 期望年龄层级, 说明)
            ("2024-06", 1, "0岁 -> 婴幼儿"),
            ("2022-06", 1, "2岁 -> 婴幼儿"),
            ("2021-06", 2, "3岁 -> 儿童(边界)"),
            ("2019-06", 2, "5岁(5.9临界) -> 儿童"),
            ("2018-06", 2, "6岁 -> 儿童"),
            ("2017-06", 3, "7岁 -> 少年(边界)"),
            ("2015-06", 3, "9岁(9.9临界) -> 少年"),
            ("2014-06", 3, "10岁 -> 少年"),
            ("2007-06", 3, "17岁(17.9临界) -> 少年"),
            ("2006-06", 4, "18岁 -> 中青年(边界)"),
            ("1965-06", 4, "59岁 -> 中青年"),
            ("1964-06", 5, "60岁 -> 老年(边界)"),
            ("1959-06", 5, "65岁(64.9临界) -> 老年"),
        ]
        for birth_ym, expected, desc in cases:
            with self.subTest(desc=desc, birth_ym=birth_ym):
                self.assertEqual(
                    calc_age_type(birth_ym, self.TODAY),
                    expected,
                    desc,
                )

    def test_invalid_inputs_fallback(self) -> None:
        cases = ["", "bad", "1990", "1899-01", "2000-13", None]
        for bad in cases:
            with self.subTest(bad=bad):
                self.assertEqual(calc_age_type(bad, self.TODAY), 4)

    def test_age_label(self) -> None:
        self.assertEqual(age_label(1), "婴幼儿")
        self.assertEqual(age_label(2), "儿童")
        self.assertEqual(age_label(3), "少年")
        self.assertEqual(age_label(4), "中青年")
        self.assertEqual(age_label(5), "老年")
        self.assertEqual(age_label(99), "未知")


# ---------------------------------------------------------------------------
# 2. env_service — 寿星公式节气 + detect 默认地域
# ---------------------------------------------------------------------------
class TestEnvService(BaseDBTest):
    def test_solar_term_known_points(self) -> None:
        cases = [
            (date(2024, 2, 4), "立春"),
            (date(2024, 6, 21), "夏至"),
            (date(2024, 12, 22), "冬至"),
            (date(2024, 9, 23), "秋分"),
        ]
        for d, expected in cases:
            with self.subTest(date=d.isoformat()):
                self.assertEqual(get_solar_term(d), expected)

    def test_get_region_default_chengyu(self) -> None:
        # 种子已写入 region_type=1，默认即「成渝」
        self.assertEqual(get_region(), 1)

    def test_detect_default_chengyu_and_term(self) -> None:
        d = date(2024, 2, 4)
        env = detect(d)
        self.assertEqual(env["region_type"], 1)
        self.assertEqual(env["region_name"], "成渝")
        self.assertEqual(env["city"], "成都")
        self.assertEqual(env["solar_term"], get_solar_term(d))
        self.assertIn("health_tip", env)


# ---------------------------------------------------------------------------
# 3. seed_loader — 幂等性
# ---------------------------------------------------------------------------
class TestSeedLoader(BaseDBTest):
    def test_idempotent_and_counts(self) -> None:
        self._reseed()  # 清空后从头写入
        from app.data.seed_solar import SOLAR_SEED
        from app.data.seed_dishes import DISH_SEED
        from app.data.seed_ingredients import INGREDIENT_SEED

        expected = {
            "solar_health_rule": len(SOLAR_SEED),
            "dish_main": len(DISH_SEED),
            "ingredient": len(INGREDIENT_SEED),
        }
        self.assertEqual(expected["solar_health_rule"], 24)
        # 原有108道菜、115种食材；家常菜谱融合后保留扩展下限，避免未来
        # 合理补充家常菜时让测试反向限制种子库增长。
        self.assertGreaterEqual(expected["dish_main"], 171)
        self.assertGreaterEqual(expected["ingredient"], 146)

        def counts() -> dict:
            out = {}
            for table in ("solar_health_rule", "dish_main", "ingredient"):
                rows = db_mod.DB.query(f"SELECT COUNT(*) AS c FROM {table}")
                out[table] = rows[0]["c"]
            return out

        first = seed_run()      # 第二次运行（幂等，应写入 0）
        after_first = counts()
        second = seed_run()     # 第三次运行（幂等，应写入 0）
        after_second = counts()

        # 每次运行写入量应为 0（已存在）
        self.assertEqual(first, {"solar": 0, "dish": 0, "ingredient": 0})
        self.assertEqual(second, {"solar": 0, "dish": 0, "ingredient": 0})
        # 记录数在多次运行后保持不变，且符合预期
        self.assertEqual(after_first, expected)
        self.assertEqual(after_second, expected)

    def test_home_recipe_merge_has_complete_unique_representatives(self) -> None:
        """融合菜谱可加载，代表性四类菜字段完整且无重名。"""
        rows = db_mod.DB.query("SELECT * FROM dish_main ORDER BY id")
        names = [str(row["dish_name"]) for row in rows]
        self.assertEqual(len(names), len(set(names)), "菜品种子不得有重名")

        expected_types = {
            "杂粮粥": 1,
            "蒜蓉油麦菜": 2,
            "清蒸鲈鱼": 3,
            "紫菜蛋花汤": 4,
            "皮蛋拌豆腐": 2,
            "凉拌鸡丝": 3,
        }
        by_name = {str(row["dish_name"]): row for row in rows}
        for dish_name, dish_type in expected_types.items():
            with self.subTest(dish_name=dish_name):
                row = by_name.get(dish_name)
                self.assertIsNotNone(row)
                self.assertEqual(int(row["dish_type"]), dish_type)
                self.assertTrue(config.json_decode(row["main_ingredients"]))
                self.assertTrue(config.json_decode(row["recipe_steps"]))
                self.assertTrue(str(row["efficacy"]).strip())
                self.assertTrue(str(row["suitable_crowd"]).strip())


# ---------------------------------------------------------------------------
# 4. member_service — 成员 CRUD + 今日计划聚合
# ---------------------------------------------------------------------------
class TestMemberService(BaseDBTest):
    def setUp(self) -> None:
        self._clear_members()

    def test_save_and_get(self) -> None:
        m = FamilyMember(nick_name="爸爸", birth_ym="1980-06", age_type=4)
        mid = save_member(m)
        self.assertGreater(mid, 0)
        got = get_member(mid)
        self.assertIsNotNone(got)
        self.assertEqual(got.nick_name, "爸爸")
        self.assertEqual(got.age_type, 4)

    def test_age_auto_refresh_on_save(self) -> None:
        # 构造一个年龄层级与出生年月明显矛盾的成员，保存时应被重算
        # （2020 年出生者在任何合理当前日期下都不会是「老年」）
        m = FamilyMember(nick_name="孩子", birth_ym="2020-06", age_type=5)
        mid = save_member(m)
        got = get_member(mid)
        self.assertEqual(got.age_type, calc_age_type("2020-06"))
        self.assertNotEqual(got.age_type, 5)

    def test_list_and_delete(self) -> None:
        save_member(FamilyMember(nick_name="A"))
        save_member(FamilyMember(nick_name="B"))
        self.assertEqual(member_count(), 2)
        members = list_members()
        self.assertEqual(len(members), 2)
        delete_member(members[0].id)
        self.assertEqual(member_count(), 1)
        self.assertIsNone(get_member(members[0].id))

    def test_build_today_plan_aggregation(self) -> None:
        a = FamilyMember(
            nick_name="爸", age_type=4, health_tag=["低脂"],
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1,
        )
        b = FamilyMember(
            nick_name="婴", age_type=1, health_tag=[],
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=0,
        )
        plan = build_today_plan([a, b])

        self.assertEqual(plan["stats"]["breakfast"]["headcount"], 2)
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 2)
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 1)

        self.assertEqual(plan["stats"]["breakfast"]["age_dist"], {4: 1, 1: 1})
        self.assertEqual(plan["stats"]["dinner"]["age_dist"], {4: 1})
        self.assertEqual(plan["stats"]["breakfast"]["health_dist"], {"低脂": 1})
        self.assertEqual(plan["stats"]["dinner"]["health_dist"], {"低脂": 1})

        # 成员字典正确聚合进各餐（顺序无关，比较集合）
        self.assertEqual(
            {m["nick_name"] for m in plan["breakfast"]}, {"爸", "婴"}
        )
        self.assertEqual(
            {m["nick_name"] for m in plan["lunch"]}, {"爸", "婴"}
        )
        self.assertEqual(
            {m["nick_name"] for m in plan["dinner"]}, {"爸"}
        )

    def test_build_today_plan_empty(self) -> None:
        plan = build_today_plan([])
        for meal in config.MEAL_KEYS:
            self.assertEqual(plan[meal], [])
            self.assertEqual(plan["stats"][meal]["headcount"], 0)
            self.assertEqual(plan["stats"][meal]["age_dist"], {})


# ---------------------------------------------------------------------------
# 5. meal_planner — 核心配餐算法
# ---------------------------------------------------------------------------
class TestMealPlanner(BaseDBTest):
    def setUp(self) -> None:
        self._reseed()
        _RECENT_MEAL_HISTORY.clear()

    def _normal_member(self) -> FamilyMember:
        return FamilyMember(
            nick_name="普通成员", age_type=4,
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1,
        )

    def test_three_meal_structure(self) -> None:
        """V1.1: 1人用餐按 (1,2) 人数段查表。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        meals = result["meals"]

        # 1人 → DISH_COUNT_BY_HEADCOUNT[(1,2)]
        # 早餐主食可以是 type=1 或 type=5（早餐专用）
        breakfast_types = self._count_types(meals["breakfast"])
        self.assertEqual(len(meals["breakfast"]), 2, "早餐应有两道菜")
        self.assertTrue(
            (breakfast_types.get(1) == 1 and breakfast_types.get(2) == 1) or
            (breakfast_types.get(5) == 1 and breakfast_types.get(2) == 1),
            "早餐应是主食+素菜（主食可为type=1或type=5）"
        )
        self.assertEqual(
            self._count_types(meals["lunch"]),
            {1: 1, 2: 1, 3: 1},
        )
        self.assertEqual(
            self._count_types(meals["dinner"]),
            {1: 1, 3: 1},
        )

    def test_vegetarian_no_meat_no_animal(self) -> None:
        veg = FamilyMember(
            nick_name="素食者", age_type=4,
            avoid_food={"categories": [], "items": [], "vegetarian": True},
        )
        plan = build_today_plan([veg])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)

        # 素食食材映射：name -> is_vegetarian
        veg_rows = db_mod.DB.query(
            "SELECT name, is_vegetarian FROM ingredient"
        )
        non_veg = {r["name"] for r in veg_rows if int(r["is_vegetarian"]) == 0}

        all_dishes = self._all_dishes(result)
        self.assertGreater(len(all_dishes), 0)  # 素食仍有可吃菜品
        for dish in all_dishes:
            self.assertNotEqual(dish["dish_type"], 3)  # 无荤菜
            for ing in dish.get("main_ingredients", []):
                self.assertNotIn(ing["name"], non_veg)  # 无蛋奶/荤腥冲突

    def test_avoid_pork_mechanism(self) -> None:
        # 机制验证：用真实存在的「猪肉」验证忌口硬剔除生效
        pork_pool = [
            d for d in db_mod.DB.query("SELECT * FROM dish_main")
            if any(
                ing["name"] == "猪肉"
                for ing in config.json_decode(d["main_ingredients"])
            )
        ]
        self.assertGreater(len(pork_pool), 0, "前置：种子库应含猪肉菜品")

        member = FamilyMember(
            nick_name="忌猪肉", age_type=4,
            avoid_food={"categories": [], "items": ["猪肉"], "vegetarian": False},
        )
        plan = build_today_plan([member])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        for dish in self._all_dishes(result):
            for ing in dish.get("main_ingredients", []):
                self.assertNotEqual(ing["name"], "猪肉")

    def test_avoid_scallion_garlic(self) -> None:
        member = FamilyMember(
            nick_name="忌葱蒜", age_type=4,
            avoid_food={
                "categories": [],
                "items": ["葱", "蒜", "大蒜"],
                "vegetarian": False,
            },
        )
        plan = build_today_plan([member])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        for dish in self._all_dishes(result):
            for ing in dish.get("main_ingredients", []):
                self.assertNotIn(ing["name"], ("葱", "蒜", "大蒜"))

    def test_determinism_same_date(self) -> None:
        plan = build_today_plan([self._normal_member()])
        d = date(2024, 6, 21)
        r1 = generate_daily_meals(d, 1, plan)
        r2 = generate_daily_meals(d, 1, plan)
        self.assertEqual(r1, r2)

    def test_structure_holds_across_dates(self) -> None:
        """V1.1: 1人用餐结构在不同日期一致。"""
        plan = build_today_plan([self._normal_member()])
        for d in (date(2024, 6, 21), date(2024, 12, 22), date(2024, 2, 4)):
            with self.subTest(date=d.isoformat()):
                result = generate_daily_meals(d, 1, plan)
                meals = result["meals"]
                # 1人 → DISH_COUNT_BY_HEADCOUNT[(1,2)]
                # 早餐主食可以是 type=1 或 type=5（早餐专用）
                breakfast_types = self._count_types(meals["breakfast"])
                self.assertEqual(len(meals["breakfast"]), 2, "早餐应有两道菜")
                self.assertTrue(
                    (breakfast_types.get(1) == 1 and breakfast_types.get(2) == 1) or
                    (breakfast_types.get(5) == 1 and breakfast_types.get(2) == 1),
                    "早餐应是主食+素菜（主食可为type=1或type=5）"
                )
                self.assertEqual(
                    self._count_types(meals["lunch"]),
                    {1: 1, 2: 1, 3: 1},
                )
                self.assertEqual(
                    self._count_types(meals["dinner"]),
                    {1: 1, 3: 1},
                )

    def test_empty_members_no_crash(self) -> None:
        plan = build_today_plan([])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        self.assertEqual(set(result["meals"].keys()), set(config.MEAL_KEYS))
        for meal in config.MEAL_KEYS:
            self.assertEqual(result["meals"][meal], [])
        self.assertIn("term", result)
        self.assertIn("health_tip", result)

    def test_breakfast_excludes_heavy_spicy_main_dishes(self) -> None:
        """早餐只选清淡候选，不出现重辣重油主菜。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        prohibited = ("毛血旺", "冒菜", "肥肠鱼", "肥肠", "水煮", "辣子", "麻辣")
        for dish in result["meals"]["breakfast"]:
            self.assertFalse(any(token in dish["dish_name"] for token in prohibited))
            self.assertLess(dish["taste"]["spicy"], 3)
            self.assertLess(dish["taste"]["numb"], 3)

    def test_daily_menu_has_no_cross_meal_duplicate_dishes(self) -> None:
        """同一天早餐、午餐、晚餐之间不得重复同一道菜。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        all_ids = [dish["id"] for dish in self._all_dishes(result)]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_regenerate_avoids_previous_menu_when_candidates_are_sufficient(self) -> None:
        """主动重配优先避开上一套菜，候选充足时整体菜品不重合。"""
        plan = build_today_plan([self._normal_member()])
        first = generate_daily_meals(date(2024, 6, 21), 1, plan, rotation_seed=0)
        first_ids = {dish["id"] for dish in self._all_dishes(first)}
        refreshed = generate_daily_meals(
            date(2024, 6, 21),
            1,
            plan,
            rotation_seed=1,
            avoid_dish_ids=first_ids,
        )
        refreshed_ids = {dish["id"] for dish in self._all_dishes(refreshed)}
        self.assertTrue(refreshed_ids)
        self.assertFalse(first_ids & refreshed_ids)
        self.assertEqual(
            len([dish["id"] for dish in self._all_dishes(refreshed)]),
            len(refreshed_ids),
        )

    def test_recent_plan_penalty_rotates_next_day_dishes(self) -> None:
        """连续生成相邻日期方案时，历史记录降低完全重复概率。"""
        plan = build_today_plan([self._normal_member()])
        first = generate_daily_meals(date(2024, 6, 21), 1, plan)
        second = generate_daily_meals(date(2024, 6, 22), 1, plan)
        first_ids = {dish["id"] for dish in self._all_dishes(first)}
        second_ids = {dish["id"] for dish in self._all_dishes(second)}
        self.assertLess(len(first_ids & second_ids), len(first_ids))

    def test_breakfast_prefers_porridge_and_small_dish(self) -> None:
        """早餐候选充足时优先粥类主食和小菜/凉菜。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        breakfast = result["meals"]["breakfast"]
        names = {dish["dish_name"] for dish in breakfast}

        self.assertTrue(any("粥" in name or "羹" in name for name in names))
        self.assertTrue(
            any("凉拌" in name or "豆花" in name or "小菜" in name for name in names)
        )

    def test_lunch_and_dinner_prioritize_solar_term_dishes(self) -> None:
        """午晚餐在当令菜候选存在时至少选入一项。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        solar_term = result["term"]
        lunch_dinner = result["meals"]["lunch"] + result["meals"]["dinner"]

        self.assertTrue(
            any(solar_term in dish["suit_solar"] for dish in lunch_dinner),
            f"午晚餐未选择适合{solar_term}的菜品",
        )

    def test_replace_dish_returns_compatible_unused_dish(self) -> None:
        """替换菜品保持类型，且不返回当前方案已使用的菜。"""
        plan = build_today_plan([self._normal_member()])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        old_dish = result["meals"]["lunch"][0]
        current_ids = {
            dish["id"] for dish in self._all_dishes(result)
        }

        replacement = replace_dish(
            date(2024, 6, 21),
            1,
            plan,
            "lunch",
            old_dish["id"],
            current_ids,
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement["dish_type"], old_dish["dish_type"])
        self.assertNotIn(replacement["id"], current_ids)

    def test_replace_dish_rejects_invalid_meal_key(self) -> None:
        """替换接口对非定义餐次安全返回空结果。"""
        plan = build_today_plan([self._normal_member()])

        replacement = replace_dish(
            date(2024, 6, 21), 1, plan, "brunch", 1, set()
        )

        self.assertIsNone(replacement)

    def test_noodle_staple_reduces_side_dishes_but_keeps_balance(self) -> None:
        noodle = {"dish_type": 1, "dish_name": "番茄鸡蛋面"}
        normal = {"dish_type": 1, "dish_name": "粗粮饭"}
        self.assertTrue(_is_noodle_staple(noodle))
        self.assertFalse(_is_noodle_staple(normal))
        source = {1: 1, 2: 2, 3: 1, 4: 1}
        adjusted = _adjust_structure_for_noodle(source, noodle, "lunch")
        self.assertEqual(adjusted[2], 1)
        self.assertEqual(adjusted[3], 1)
        self.assertEqual(adjusted[4], 1)
        self.assertEqual(source[2], 2)


# 羊肉忌口：种子库当前没有任何使用「羊肉」的菜品，
# 故通过注入一条受控的羊肉菜品来真正验证忌口剔除逻辑。
class TestMealPlannerAvoidLamb(BaseDBTest):
    def setUp(self) -> None:
        self._reseed()
        self._insert_dish(
            "测试羊肉煲",
            dish_type=3,
            main_ingredients=[{"name": "羊肉", "grams": 200, "category": 2}],
        )

    def test_avoid_lamb_removes_dish(self) -> None:
        member = FamilyMember(
            nick_name="忌羊肉", age_type=4,
            avoid_food={"categories": [], "items": ["羊肉"], "vegetarian": False},
        )
        plan = build_today_plan([member])
        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        names = {d["dish_name"] for d in self._all_dishes(result)}
        self.assertNotIn("测试羊肉煲", names)
        for dish in self._all_dishes(result):
            for ing in dish.get("main_ingredients", []):
                self.assertNotEqual(ing["name"], "羊肉")


# ---------------------------------------------------------------------------
# 6. shopping_service — 买菜清单 + 重量换算
# ---------------------------------------------------------------------------
class TestShoppingService(BaseDBTest):
    def setUp(self) -> None:
        self._reseed()

    def test_convert_weight(self) -> None:
        self.assertEqual(convert_weight(1000), {"grams": 1000.0, "jin": 2.0})
        self.assertEqual(convert_weight(500), {"grams": 500.0, "jin": 1.0})
        self.assertEqual(convert_weight(250), {"grams": 250.0, "jin": 0.5})
        self.assertEqual(
            convert_weight(1000, 1, 2.0), {"grams": 2000.0, "jin": 4.0}
        )

    def test_category_aggregation(self) -> None:
        meals = {
            "breakfast": [
                {
                    "dish_name": "早A",
                    "main_ingredients": [
                        {"name": "白菜", "grams": 200},
                        {"name": "猪肉", "grams": 300},
                    ],
                }
            ],
            "lunch": [],
            "dinner": [],
        }
        plan = {
            "breakfast": [{"age_type": 4}],
            "lunch": [],
            "dinner": [],
        }
        res = build_shopping_list(meals, plan)
        self.assertIn("蔬菜", res)
        self.assertIn("肉类", res)
        veg = {e["name"]: e for e in res["蔬菜"]}
        meat = {e["name"]: e for e in res["肉类"]}
        self.assertEqual(veg["白菜"]["grams"], 200)
        self.assertEqual(veg["白菜"]["jin"], 0.4)
        self.assertEqual(meat["猪肉"]["grams"], 300)
        self.assertEqual(meat["猪肉"]["jin"], 0.6)

    def test_age_portion_factor(self) -> None:
        meals = {
            "breakfast": [
                {
                    "dish_name": "早B",
                    "main_ingredients": [{"name": "白菜", "grams": 200}],
                }
            ],
            "lunch": [],
            "dinner": [],
        }
        # 中青年(1.0) 单份
        plan_adult = {
            "breakfast": [{"age_type": 4}],
            "lunch": [],
            "dinner": [],
        }
        res_adult = build_shopping_list(meals, plan_adult)
        self.assertEqual(res_adult["蔬菜"][0]["grams"], 200)
        self.assertEqual(res_adult["蔬菜"][0]["jin"], 0.4)

        # 婴幼儿(0.7) + 老年(0.7) = 1.4 份
        plan_mixed = {
            "breakfast": [{"age_type": 1}, {"age_type": 5}],
            "lunch": [],
            "dinner": [],
        }
        res_mixed = build_shopping_list(meals, plan_mixed)
        self.assertEqual(res_mixed["蔬菜"][0]["grams"], 280)
        self.assertEqual(res_mixed["蔬菜"][0]["jin"], 0.6)

    def test_empty_input_no_crash(self) -> None:
        res = build_shopping_list({}, {})
        self.assertEqual(res, {})

    def test_excludes_staples_and_seasonings(self) -> None:
        meals = {
            "breakfast": [{"main_ingredients": [
                {"name": "大米", "grams": 150}, {"name": "葱", "grams": 5},
                {"name": "酱油", "grams": 8}, {"name": "食用油", "grams": 20},
                {"name": "料酒", "grams": 10}, {"name": "蚝油", "grams": 8},
                {"name": "鸡精", "grams": 3}, {"name": "白菜", "grams": 200},
                {"name": "鸡蛋", "grams": 50},
            ]}],
            "lunch": [], "dinner": [],
        }
        plan = {"breakfast": [{"age_type": 4}], "lunch": [], "dinner": []}
        flattened = {item["name"] for items in build_shopping_list(meals, plan).values() for item in items}
        self.assertEqual(flattened, {"白菜", "鸡蛋"})
        self.assertFalse(is_shopping_ingredient("大米"))
        self.assertFalse(is_shopping_ingredient("糯米"))
        self.assertFalse(is_shopping_ingredient("面粉"))
        self.assertFalse(is_shopping_ingredient("面条"))
        self.assertFalse(is_shopping_ingredient("辣椒油"))
        for seasoning in ("食用油", "料酒", "蚝油", "鸡精"):
            self.assertFalse(is_shopping_ingredient(seasoning))
        self.assertTrue(is_shopping_ingredient("猪肉"))
        self.assertTrue(is_shopping_ingredient("鸡肉"))
        self.assertTrue(is_shopping_ingredient("西红柿"))


class TestFletCompatibility(unittest.TestCase):
    """验证主题和页面模块可在当前 Flet API 下安全导入。"""

    def test_theme_card_uses_current_border_api(self) -> None:
        """构建主题卡片时不访问已移除的 ``ft.border.all``。"""
        card = theme.card(ft.Text("边框兼容性"))
        self.assertIsInstance(card.border, ft.Border)
        self.assertEqual(card.border.top.width, 1)
        self.assertEqual(card.border.top.color, theme.COLOR_BORDER)

    def test_big_button_uses_supported_content_argument(self) -> None:
        """主题按钮工厂不向 Flet ``Button`` 传入已移除的 ``text`` 参数。"""
        button = theme.big_button("按钮兼容性", disabled=True)

        self.assertIsInstance(button, ft.ElevatedButton)
        self.assertEqual(button.content, "按钮兼容性")
        self.assertTrue(button.disabled)

    def test_page_package_imports_without_legacy_border_error(self) -> None:
        """页面包导入不触发旧版 ``border.all`` 属性错误。"""
        import app.pages as pages

        self.assertTrue(callable(pages.home_page))
        self.assertTrue(callable(pages.member_page))


class _StubPage:
    """无需 GUI 会话即可构造 Flet 路由视图的最小页面替身。"""

    def __init__(self, route: str) -> None:
        self.route = route
        self.views: list[ft.View] = []
        self.on_route_change = None

    def update(self) -> None:
        """模拟 Flet 页面更新。"""

    def show_dialog(self, dialog: ft.Control) -> None:
        """模拟 Flet 对话框展示。"""


class TestRouteViewConstruction(BaseDBTest):
    """确认受影响路由可离线构造，不会退化为空白页。"""

    def setUp(self) -> None:
        self._reseed()

    def test_member_and_member_edit_views_construct_controls(self) -> None:
        member_view = member_page(_StubPage("/member"))
        add_view = member_edit_page(_StubPage("/member_edit"))
        self.assertIsInstance(member_view, ft.View)
        self.assertGreater(len(member_view.controls), 0)
        self.assertGreater(len(add_view.controls), 0)
        self.assertEqual(add_view.appbar.title.value, "添加成员")

        saved_id = save_member(FamilyMember(nick_name="路由成员", birth_ym="1990-01"))
        edit_view = member_edit_page(_StubPage(f"/member_edit/{saved_id}"))
        self.assertGreater(len(edit_view.controls), 0)
        self.assertEqual(edit_view.appbar.title.value, "编辑成员")

    def test_diner_and_dish_detail_views_construct_controls(self) -> None:
        diner_view = diner_select_page(_StubPage("/diner_select"))
        detail_view = dish_detail_page(_StubPage("/dish/1"))
        self.assertGreater(len(diner_view.controls), 0)
        self.assertGreater(len(detail_view.controls), 0)


class TestPresentationHelpers(unittest.TestCase):
    """验证关键页面的独立布局辅助函数。"""

    def test_meal_checkbox_row_forces_single_line_with_native_labels(self) -> None:
        checkboxes = [
            ft.Checkbox(label="早餐"),
            ft.Checkbox(label="午餐"),
            ft.Checkbox(label="晚餐"),
        ]
        row = build_meal_checkbox_row(checkboxes)
        self.assertEqual(row.controls, checkboxes)
        self.assertFalse(row.wrap)
        self.assertEqual(row.spacing, 8)
        self.assertEqual(row.alignment, ft.MainAxisAlignment.START)
        self.assertEqual([checkbox.label for checkbox in checkboxes], ["早餐", "午餐", "晚餐"])

    def test_taste_preference_row_keeps_slider_compact(self) -> None:
        label = ft.Text("辣度：中")
        slider = ft.Slider(min=1, max=4, value=3, width=220)
        row = build_taste_preference_row(label, slider)
        self.assertEqual(row.controls, [label, slider])
        self.assertFalse(bool(slider.expand))
        self.assertEqual(slider.width, 220)
        self.assertIsNone(slider.height)

    def test_member_edit_form_keeps_controls_after_taste_preferences(self) -> None:
        view = member_edit_page(_StubPage("/member_edit"))
        body = view.controls[0]
        control_values = [
            control.value
            for control in body.controls
            if isinstance(control, ft.Text)
        ]
        self.assertIn("体质 / 健康标签", control_values)
        self.assertIn("忌口设置", control_values)
        self.assertTrue(any(
            isinstance(control, ft.Switch)
            and control.label == "素食（剔除荤腥）"
            for control in body.controls
        ))
        self.assertTrue(any(
            isinstance(control, ft.Row)
            and any(isinstance(item, ft.Slider) for item in control.controls)
            for control in body.controls
        ))

    def test_result_action_grid_uses_fixed_two_by_two_order(self) -> None:
        labels = result_action_labels()
        self.assertEqual(labels, ("重新配餐", "更替选菜", "买菜清单", "保存配餐"))
        grid = build_result_action_grid([theme.big_button(label) for label in labels])
        self.assertEqual(len(grid.controls), 2)
        first_row = [container.content.content for container in grid.controls[0].controls]
        second_row = [container.content.content for container in grid.controls[1].controls]
        self.assertEqual(first_row, list(labels[:2]))
        self.assertEqual(second_row, list(labels[2:]))
        with self.assertRaises(ValueError):
            build_result_action_grid([theme.big_button("仅一个")])

    def test_recipe_details_only_exposes_practical_sections(self) -> None:
        details = build_recipe_details({"recipe_steps": [], "taboo_crowd": ""})
        self.assertIn("少油少盐", details["steps"])
        self.assertIn("搭配", details["pairing_tip"])
        self.assertIn("过敏", details["taboo_tip"])
        self.assertNotIn("meal_time", details)
        self.assertNotIn("nutrition_tip", details)


# ===========================================================================
# V1.1 增量测试
# ===========================================================================

# ---------------------------------------------------------------------------
# V1.1-1. get_meal_structure — 按人数段查表（纯函数，无需数据库）
# ---------------------------------------------------------------------------
class TestGetMealStructure(unittest.TestCase):
    """验证 get_meal_structure 对各人数段的查表逻辑。"""

    def test_headcount_segments(self) -> None:
        """1/2→(1,2), 3/4→(3,4), 5/6→(5,6), 7/10→(7,999)。"""
        cases = [
            (1, (1, 2)),
            (2, (1, 2)),
            (3, (3, 4)),
            (4, (3, 4)),
            (5, (5, 6)),
            (6, (5, 6)),
            (7, (7, 999)),
            (10, (7, 999)),
        ]
        for headcount, expected_key in cases:
            with self.subTest(headcount=headcount):
                result = config.get_meal_structure(headcount)
                expected = config.DISH_COUNT_BY_HEADCOUNT[expected_key]
                # 比较三餐结构完全一致（banquet=False 时）。
                # get_meal_structure 已归一化含 1..5 全部键，期望值同步归一化。
                for meal in config.MEAL_KEYS:
                    expected_meal = dict(expected[meal])
                    for dt in (1, 2, 3, 4, 5):
                        expected_meal.setdefault(dt, 0)
                    self.assertEqual(result[meal], expected_meal,
                                     f"headcount={headcount} meal={meal} mismatch")

    def test_zero_headcount_returns_all_zero(self) -> None:
        """0人时返回全零结构。"""
        result = config.get_meal_structure(0)
        for meal in config.MEAL_KEYS:
            for dt in (1, 2, 3, 4):
                self.assertEqual(result[meal][dt], 0,
                                 f"0人时 {meal}[{dt}] 应为 0")

    def test_total_dish_counts_match_spec(self) -> None:
        """V1.1 规格（早餐改用 type=5 轻量结构，共 2 道）：
        1-2人7道 / 3-4人9道 / 5-6人11道 / ≥7人13道。
        统计含 dish_type=1..5 全部键。
        """
        expected_totals = {
            1: 7, 2: 7,
            3: 9, 4: 9,
            5: 11, 6: 11,
            7: 13, 10: 13,
        }
        for headcount, expected_total in expected_totals.items():
            with self.subTest(headcount=headcount):
                result = config.get_meal_structure(headcount)
                actual = sum(
                    result[meal][dt]
                    for meal in config.MEAL_KEYS
                    for dt in (1, 2, 3, 4, 5)
                )
                self.assertEqual(actual, expected_total,
                                 f"headcount={headcount} 总菜数={actual}, 期望={expected_total}")


# ---------------------------------------------------------------------------
# V1.1-2. banquet 加成 — 每餐荤菜+1（纯函数）
# ---------------------------------------------------------------------------
class TestBanquetBonus(unittest.TestCase):
    """验证 banquet=True 时每餐荤菜(类型3)数量+1。"""

    def test_banquet_adds_one_meat_per_meal(self) -> None:
        for headcount in (1, 3, 5, 7):
            with self.subTest(headcount=headcount):
                normal = config.get_meal_structure(headcount, banquet=False)
                banquet = config.get_meal_structure(headcount, banquet=True)
                for meal in config.MEAL_KEYS:
                    self.assertEqual(
                        banquet[meal][3],
                        normal[meal][3] + 1,
                        f"headcount={headcount} meal={meal} banquet荤菜应+1",
                    )

    def test_banquet_does_not_affect_other_types(self) -> None:
        """banquet 只影响荤菜(3)，不影响主食(1)/素菜(2)/汤品(4)。"""
        for headcount in (1, 3, 5, 7):
            with self.subTest(headcount=headcount):
                normal = config.get_meal_structure(headcount, banquet=False)
                banquet = config.get_meal_structure(headcount, banquet=True)
                for meal in config.MEAL_KEYS:
                    for dt in (1, 2, 4):
                        self.assertEqual(
                            banquet[meal][dt],
                            normal[meal][dt],
                            f"headcount={headcount} meal={meal} type={dt} 不应受banquet影响",
                        )


# ---------------------------------------------------------------------------
# V1.1-3. 0人跳过 — 某餐0人时该餐菜品列表为空
# ---------------------------------------------------------------------------
class TestZeroPersonSkip(BaseDBTest):
    """验证 meal_planner 对0人餐次的跳过逻辑。"""

    def setUp(self) -> None:
        self._reseed()

    def test_zero_person_meal_skipped(self) -> None:
        """成员只吃午餐，早餐晚餐0人 → 早餐晚餐菜品为空，午餐有菜。"""
        member = FamilyMember(
            nick_name="只吃午餐", age_type=4,
            is_eat_breakfast=0, is_eat_lunch=1, is_eat_dinner=0,
        )
        plan = build_today_plan([member])
        # 前置验证：breakfast 和 dinner 0人
        self.assertEqual(plan["stats"]["breakfast"]["headcount"], 0)
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 0)
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 1)

        result = generate_daily_meals(date(2024, 6, 21), 1, plan)
        # 0人餐次菜品列表应为空
        self.assertEqual(result["meals"]["breakfast"], [])
        self.assertEqual(result["meals"]["dinner"], [])
        # 午餐应有菜品
        self.assertGreater(len(result["meals"]["lunch"]), 0)


# ---------------------------------------------------------------------------
# V1.1-4. build_plan_from_selection — 显式选人构建计划
# ---------------------------------------------------------------------------
class TestBuildPlanFromSelection(BaseDBTest):
    """验证 build_plan_from_selection 的选人聚合逻辑。"""

    def setUp(self) -> None:
        self._clear_members()
        # 插入3个成员
        self.m1 = FamilyMember(
            nick_name="A", age_type=4,
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1,
        )
        self.m2 = FamilyMember(
            nick_name="B", age_type=4,
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1,
        )
        self.m3 = FamilyMember(
            nick_name="C", age_type=4,
            is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1,
        )
        self.m1.id = save_member(self.m1)
        self.m2.id = save_member(self.m2)
        self.m3.id = save_member(self.m3)
        self.members = list_members()

    def test_select_2_members_for_lunch_only(self) -> None:
        """选2人只参与午餐 → 午餐2人，早餐晚餐0人。"""
        selection = [
            {"id": self.m1.id, "breakfast": False, "lunch": True, "dinner": False},
            {"id": self.m2.id, "breakfast": False, "lunch": True, "dinner": False},
            {"id": self.m3.id, "breakfast": False, "lunch": False, "dinner": False},
        ]
        plan = build_plan_from_selection(self.members, selection)

        self.assertEqual(plan["stats"]["lunch"]["headcount"], 2)
        self.assertEqual(plan["stats"]["breakfast"]["headcount"], 0)
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 0)
        self.assertEqual(len(plan["lunch"]), 2)
        self.assertEqual(len(plan["breakfast"]), 0)
        self.assertEqual(len(plan["dinner"]), 0)

    def test_selection_mixed_meals(self) -> None:
        """成员A全选、成员B只选晚餐、成员C不参与。"""
        selection = [
            {"id": self.m1.id, "breakfast": True, "lunch": True, "dinner": True},
            {"id": self.m2.id, "breakfast": False, "lunch": False, "dinner": True},
            {"id": self.m3.id, "breakfast": False, "lunch": False, "dinner": False},
        ]
        plan = build_plan_from_selection(self.members, selection)

        self.assertEqual(plan["stats"]["breakfast"]["headcount"], 1)
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 1)
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 2)

    def test_empty_selection(self) -> None:
        """空选择列表 → 所有餐次0人。"""
        plan = build_plan_from_selection(self.members, [])
        for meal in config.MEAL_KEYS:
            self.assertEqual(plan["stats"][meal]["headcount"], 0)


# ---------------------------------------------------------------------------
# V1.1-5. build_banquet_plan — 宴请计划（含虚拟访客）
# ---------------------------------------------------------------------------
class TestBuildBanquetPlan(BaseDBTest):
    """验证 build_banquet_plan 的宴请计划构建逻辑。"""

    def setUp(self) -> None:
        self._clear_members()
        self.m1 = FamilyMember(nick_name="爸", age_type=4)
        self.m2 = FamilyMember(nick_name="妈", age_type=4)
        self.m1.id = save_member(self.m1)
        self.m2.id = save_member(self.m2)
        self.members = list_members()

    def test_banquet_plan_2_members_1_adult_1_child(self) -> None:
        """2家庭成员 + 1成人访客 + 1儿童 → 午餐4人，banquet=True。"""
        plan = build_banquet_plan(
            self.members,
            member_ids=[self.m1.id, self.m2.id],
            guest_adults=1,
            guest_children=1,
            guest_elderly=0,
            meal_key="lunch",
        )

        # banquet 标记
        self.assertTrue(plan["banquet"])
        self.assertEqual(plan["banquet_meal"], "lunch")

        # 午餐4人
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 4)
        # 其他餐次0人
        self.assertEqual(plan["stats"]["breakfast"]["headcount"], 0)
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 0)

        # 验证成员构成：2家庭成员 + 1成人(age_type=4) + 1儿童(age_type=2)
        lunch_diners = plan["lunch"]
        age_dist = plan["stats"]["lunch"]["age_dist"]
        self.assertEqual(age_dist.get(4, 0), 3)  # 2家庭成员 + 1成人访客
        self.assertEqual(age_dist.get(2, 0), 1)  # 1儿童访客

        # 访客 id 应为负数
        guest_ids = [d["id"] for d in lunch_diners if d["id"] < 0]
        self.assertEqual(len(guest_ids), 2)  # 1成人 + 1儿童

    def test_banquet_plan_dinner_meal(self) -> None:
        """宴请餐次为晚餐时，晚餐有人、午餐无人。"""
        plan = build_banquet_plan(
            self.members,
            member_ids=[self.m1.id],
            guest_adults=2,
            guest_children=0,
            guest_elderly=1,
            meal_key="dinner",
        )
        self.assertTrue(plan["banquet"])
        self.assertEqual(plan["banquet_meal"], "dinner")
        # 1家庭成员 + 2成人 + 1老人 = 4人
        self.assertEqual(plan["stats"]["dinner"]["headcount"], 4)
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 0)

    def test_banquet_no_members_only_guests(self) -> None:
        """不选家庭成员、只有访客也能构建计划。"""
        plan = build_banquet_plan(
            self.members,
            member_ids=[],
            guest_adults=3,
            guest_children=0,
            guest_elderly=0,
            meal_key="lunch",
        )
        self.assertEqual(plan["stats"]["lunch"]["headcount"], 3)
        self.assertTrue(plan["banquet"])


# ---------------------------------------------------------------------------
# V1.1-6. 选人记忆持久化
# ---------------------------------------------------------------------------
class TestSelectionPersistence(BaseDBTest):
    """验证 save/load_diner_selection 和 banquet_selection 的持久化。"""

    def setUp(self) -> None:
        self._clear_members()

    def test_diner_selection_roundtrip(self) -> None:
        sel = [
            {"id": 1, "breakfast": True, "lunch": False, "dinner": True},
            {"id": 2, "breakfast": False, "lunch": True, "dinner": False},
        ]
        save_diner_selection(sel)
        loaded = load_diner_selection()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["id"], 1)
        self.assertTrue(loaded[0]["breakfast"])
        self.assertFalse(loaded[0]["lunch"])
        self.assertEqual(loaded[1]["id"], 2)

    def test_diner_selection_empty_when_no_record(self) -> None:
        loaded = load_diner_selection()
        self.assertEqual(loaded, [])

    def test_banquet_selection_roundtrip(self) -> None:
        data = {
            "member_ids": [1, 2],
            "guest_adults": 3,
            "guest_children": 1,
            "guest_elderly": 0,
            "meal_key": "dinner",
        }
        save_banquet_selection(data)
        loaded = load_banquet_selection()
        self.assertEqual(loaded["member_ids"], [1, 2])
        self.assertEqual(loaded["guest_adults"], 3)
        self.assertEqual(loaded["meal_key"], "dinner")

    def test_banquet_selection_empty_when_no_record(self) -> None:
        loaded = load_banquet_selection()
        self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
