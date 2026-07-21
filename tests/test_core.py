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
from app import config  # noqa: E402
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
from app.services.meal_planner import generate_daily_meals  # noqa: E402
from app.services.shopping_service import (  # noqa: E402
    build_shopping_list,
    convert_weight,
)


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
        self.assertEqual(expected["dish_main"], 105)
        self.assertEqual(expected["ingredient"], 115)

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
        self.assertEqual(
            self._count_types(meals["breakfast"]),
            {1: 1, 2: 1},
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
                self.assertEqual(
                    self._count_types(meals["breakfast"]),
                    {1: 1, 2: 1},
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
                # 比较三餐结构完全一致（banquet=False 时）
                for meal in config.MEAL_KEYS:
                    self.assertEqual(result[meal], expected[meal],
                                     f"headcount={headcount} meal={meal} mismatch")

    def test_zero_headcount_returns_all_zero(self) -> None:
        """0人时返回全零结构。"""
        result = config.get_meal_structure(0)
        for meal in config.MEAL_KEYS:
            for dt in (1, 2, 3, 4):
                self.assertEqual(result[meal][dt], 0,
                                 f"0人时 {meal}[{dt}] 应为 0")

    def test_total_dish_counts_match_spec(self) -> None:
        """V1.1 规格：1-2人7道 / 3-4人10道 / 5-6人12道 / ≥7人15道。"""
        expected_totals = {
            1: 7, 2: 7,
            3: 10, 4: 10,
            5: 12, 6: 12,
            7: 15, 10: 15,
        }
        for headcount, expected_total in expected_totals.items():
            with self.subTest(headcount=headcount):
                result = config.get_meal_structure(headcount)
                actual = sum(
                    result[meal][dt]
                    for meal in config.MEAL_KEYS
                    for dt in (1, 2, 3, 4)
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
