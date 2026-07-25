#!/usr/bin/env python3
import sys
import unittest

sys.path.insert(0, '.')

# Patch the unittest output to a file
import io
log = io.StringIO()

from datetime import date
from app.database import DB
from app.data.seed_loader import run
from app.services.member_service import FamilyMember, build_today_plan
from app.services.meal_planner import generate_daily_meals

DB.init_schema()
run()
print("DB loaded OK")

plan = build_today_plan([FamilyMember(nick_name='test', age_type=4, is_eat_breakfast=1, is_eat_lunch=1, is_eat_dinner=1)])
print("Plan built OK")

# Test breakfast
r = generate_daily_meals(date(2024, 6, 21), 1, plan)
print("Breakfast:", [x['dish_name'] for x in r['meals']['breakfast']])
print("Lunch:", [x['dish_name'] for x in r['meals']['lunch']])
print("Dinner:", [x['dish_name'] for x in r['meals']['dinner']])
