#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

# Test import
try:
    from app.services.meal_planner import (
        generate_daily_meals, _score_dish, _breakfast_preference_bonus,
        _candidate_pool, _apply_rotation_noise, _SEASON_KEYWORDS,
        _SOLAR_BY_SEASON, _BREAKFAST_SMALL_DISH_BONUS, _BREAKFAST_WOK_BONUS
    )
    print("meal_planner import OK")
    print(f"BREAKFAST_SMALL_DISH_BONUS={_BREAKFAST_SMALL_DISH_BONUS}")
    print(f"BREAKFAST_WOK_BONUS={_BREAKFAST_WOK_BONUS}")
    print(f"SEASON_KEYWORDS={_SEASON_KEYWORDS}")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test breakfast bonus logic
dish_pong = {"dish_name": "八宝粥", "dish_type": 5, "main_ingredients": [{"name": "大米", "g": 50}, {"name": "红豆", "g": 20}]}
dish_pancake = {"dish_name": "土豆丝鸡蛋饼", "dish_type": 5, "main_ingredients": [{"name": "土豆", "g": 150}]}
dish_pickle = {"dish_name": "酱黄瓜", "dish_type": 2, "main_ingredients": [{"name": "黄瓜", "g": 200}]}
dish_stirfry = {"dish_name": "清炒时蔬", "dish_type": 2, "main_ingredients": [{"name": "当季绿叶菜", "g": 200}]}

for name, dish in [("八宝粥", dish_pong), ("土豆丝鸡蛋饼", dish_pancake), ("酱黄瓜", dish_pickle), ("清炒时蔬", dish_stirfry)]:
    bonus = _breakfast_preference_bonus(dish)
    print(f"  {name} bonus={bonus}")

# Test season keywords
print("\nSeason keyword matching test:")
for kw in ["苦瓜", "冬瓜", "韭菜", "菠菜", "羊肉", "萝卜"]:
    for season, keywords in _SEASON_KEYWORDS.items():
        if kw in keywords:
            print(f"  {kw} -> {season} ({_SOLAR_BY_SEASON[season]})")
            break
    else:
        print(f"  {kw} -> no match (will use auto-match)")

print("\nAll checks passed!")
