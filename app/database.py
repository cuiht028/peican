"""SQLite 连接、建表与通用 CRUD 辅助。

本模块封装本地 SQLite 访问（Python 标准库 sqlite3，零额外依赖）。
提供：
  * 固定数据库路径 ``DB_PATH``（项目根目录下的 meal.db）
  * ``init_schema()`` 创建 6 张表
  * 通用方法 ``execute / query / get_by_id / upsert / delete``
  * 键值配置读写 ``get_setting / set_setting``

所有 JSON 字段以 TEXT 存取，业务层使用 ``app.config.json_encode/decode``。

遵循 Google Python 风格指南。
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Optional

# 项目根目录（app/ 的上一级）
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_APP_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "meal.db")


class Database:
    """SQLite 轻封装。

    使用单连接 + row_factory=sqlite3.Row，方便以字典方式读取记录。
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------
    # 建表
    # ------------------------------------------------------------------
    def init_schema(self) -> None:
        """创建全部数据表（幂等，已存在则跳过）。"""
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS family_member (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                nick_name TEXT NOT NULL,
                birth_ym TEXT NOT NULL DEFAULT '',
                age_type INTEGER NOT NULL DEFAULT 4,
                is_eat_breakfast INTEGER NOT NULL DEFAULT 1,
                is_eat_lunch INTEGER NOT NULL DEFAULT 1,
                is_eat_dinner INTEGER NOT NULL DEFAULT 1,
                spicy_level INTEGER NOT NULL DEFAULT 2,
                numb_level INTEGER NOT NULL DEFAULT 2,
                acid_level INTEGER NOT NULL DEFAULT 1,
                salt_level INTEGER NOT NULL DEFAULT 2,
                sweet_level INTEGER NOT NULL DEFAULT 1,
                avoid_food TEXT NOT NULL DEFAULT '{}',
                health_tag TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS user_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                template_name TEXT NOT NULL,
                template_type INTEGER NOT NULL DEFAULT 1,
                family_config TEXT NOT NULL DEFAULT '[]',
                guest_num INTEGER NOT NULL DEFAULT 0,
                guest_child_num INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS solar_health_rule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solar_term TEXT NOT NULL,
                climate TEXT NOT NULL DEFAULT '',
                health_core TEXT NOT NULL DEFAULT '',
                recommend_food TEXT NOT NULL DEFAULT '[]',
                forbid_food TEXT NOT NULL DEFAULT '[]',
                region_type INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS dish_main (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dish_name TEXT NOT NULL,
                dish_type INTEGER NOT NULL DEFAULT 2,
                region_type INTEGER NOT NULL DEFAULT 1,
                spicy_level INTEGER NOT NULL DEFAULT 2,
                numb_level INTEGER NOT NULL DEFAULT 2,
                acid_level INTEGER NOT NULL DEFAULT 1,
                salt_level INTEGER NOT NULL DEFAULT 2,
                sweet_level INTEGER NOT NULL DEFAULT 1,
                suit_age TEXT NOT NULL DEFAULT '[]',
                forbid_age TEXT NOT NULL DEFAULT '[]',
                suit_health TEXT NOT NULL DEFAULT '[]',
                forbid_health TEXT NOT NULL DEFAULT '[]',
                main_ingredients TEXT NOT NULL DEFAULT '[]',
                recipe_steps TEXT NOT NULL DEFAULT '[]',
                efficacy TEXT NOT NULL DEFAULT '',
                suitable_crowd TEXT NOT NULL DEFAULT '',
                taboo_crowd TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                suit_solar TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredient (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category INTEGER NOT NULL DEFAULT 5,
                unit TEXT NOT NULL DEFAULT '克',
                alias TEXT NOT NULL DEFAULT '',
                is_vegetarian INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS app_setting (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
            """
        )

    # ------------------------------------------------------------------
    # 通用 CRUD
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: Optional[list] = None) -> sqlite3.Cursor:
        """执行写操作并提交。"""
        cur = self.conn.execute(sql, params or [])
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Optional[list] = None) -> list[dict]:
        """查询并返回字典列表。"""
        cur = self.conn.execute(sql, params or [])
        return [dict(row) for row in cur.fetchall()]

    def get_by_id(self, table: str, _id: int) -> dict:
        """按整型主键查询单行；未命中返回空字典。"""
        rows = self.query(f"SELECT * FROM {table} WHERE id = ?", [_id])
        return rows[0] if rows else {}

    def upsert(self, table: str, data: dict) -> int:
        """插入或替换一行（以主键冲突判定），返回 lastrowid。"""
        cols = list(data.keys())
        col_str = ", ".join(cols)
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"
        cur = self.conn.execute(sql, [data[c] for c in cols])
        self.conn.commit()
        return cur.lastrowid

    def delete(self, table: str, _id: int) -> None:
        """按整型主键删除一行。"""
        self.execute(f"DELETE FROM {table} WHERE id = ?", [_id])

    # ------------------------------------------------------------------
    # 键值配置（app_setting）
    # ------------------------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """读取键值配置。"""
        rows = self.query("SELECT value FROM app_setting WHERE key = ?", [key])
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: Any) -> None:
        """写入 / 覆盖键值配置。"""
        self.execute(
            "INSERT OR REPLACE INTO app_setting (key, value) VALUES (?, ?)",
            [key, str(value)],
        )

    def close(self) -> None:
        """关闭连接。"""
        self.conn.close()


# 模块级单例，供各服务直接 import 使用。
DB = Database()


def get_db() -> Database:
    """返回数据库单例。"""
    return DB
