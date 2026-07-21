"""二十四节气养生规则种子数据（成渝地区）。

本文件提供 24 条 ``solar_health_rule`` 记录，描述每个节气的气候特点、
养生重点、宜食与忌食食材。食材名称与 ``seed_ingredients.py`` 中的名称
保持一致，供配餐算法做节气加分 / 忌口剔除。

数据仅作离线预置，后续可由养生顾问迭代完善。
"""

from __future__ import annotations

from typing import Any

# 每条记录字段：
# solar_term, climate, health_core, recommend_food, forbid_food, region_type
SOLAR_SEED: list[dict[str, Any]] = [
    {
        "solar_term": "立春",
        "climate": "乍暖还寒，风邪渐盛，成渝多阴湿。",
        "health_core": "养肝护阳，少酸多辛，早睡早起。",
        "recommend_food": ["韭菜", "豆芽", "香菜", "菠菜", "葱", "姜"],
        "forbid_food": ["羊肉", "花椒", "白酒"],
        "region_type": 1,
    },
    {
        "solar_term": "雨水",
        "climate": "降水增多，寒湿加重，脾胃易弱。",
        "health_core": "健脾祛湿，调养肠胃，忌生冷。",
        "recommend_food": ["山药", "红枣", "薏米", "鲫鱼", "胡萝卜"],
        "forbid_food": ["冰饮", "西瓜", "螃蟹"],
        "region_type": 1,
    },
    {
        "solar_term": "惊蛰",
        "climate": "春雷始动，肝阳上亢，易内热。",
        "health_core": "清肝润燥，少油腻，多吃梨。",
        "recommend_food": ["梨", "芹菜", "银耳", "百合", "菠菜"],
        "forbid_food": ["辣椒", "羊肉", "油炸食品"],
        "region_type": 1,
    },
    {
        "solar_term": "春分",
        "climate": "昼夜平分，阴阳调和，气候温和。",
        "health_core": "平和饮食，均衡营养，疏肝健脾。",
        "recommend_food": ["荠菜", "春笋", "鸡蛋", "豆腐", "枸杞"],
        "forbid_food": ["过量辛辣", "烈酒"],
        "region_type": 1,
    },
    {
        "solar_term": "清明",
        "climate": "气清景明，湿气渐重，极易困乏。",
        "health_core": "柔肝养血，祛湿明目，宜清淡。",
        "recommend_food": ["荠菜", "香椿", "猪肝", "薏米", "菊花"],
        "forbid_food": ["发物海鲜", "公鸡", "竹笋(过敏体质慎)"],
        "region_type": 1,
    },
    {
        "solar_term": "谷雨",
        "climate": "雨生百谷，湿气最重，脾土受困。",
        "health_core": "健脾利湿，防过敏，少食辛辣。",
        "recommend_food": ["薏米", "赤小豆", "山药", "鲫鱼", "冬瓜"],
        "forbid_food": ["浓茶", "羊肉", "海鲜"],
        "region_type": 1,
    },
    {
        "solar_term": "立夏",
        "climate": "暑气初临，心火易旺，汗多耗气。",
        "health_core": "养心安神，增酸减苦，补水。",
        "recommend_food": ["苦瓜", "莲子", "红豆", "鸭肉", "番茄"],
        "forbid_food": ["辛辣烧烤", "肥肉"],
        "region_type": 1,
    },
    {
        "solar_term": "小满",
        "climate": "湿热交织，成渝闷湿，皮肤易痒。",
        "health_core": "清热利湿，健脾，防湿疹。",
        "recommend_food": ["苦瓜", "冬瓜", "黄瓜", "绿豆", "薏米"],
        "forbid_food": ["狗肉", "羊肉", "辛辣"],
        "region_type": 1,
    },
    {
        "solar_term": "芒种",
        "climate": "闷热多雨，暑湿困脾，食欲不振。",
        "health_core": "清暑祛湿，益气健脾，多补水。",
        "recommend_food": ["绿豆", "冬瓜", "西瓜", "荷叶", "鸭肉"],
        "forbid_food": ["油腻", "甜腻", "冰镇"],
        "region_type": 1,
    },
    {
        "solar_term": "夏至",
        "climate": "阳气最盛，暑热逼人，汗多伤阴。",
        "health_core": "养阴生津，清心降火，忌大汗。",
        "recommend_food": ["苦瓜", "西瓜", "绿豆", "鸭肉", "番茄"],
        "forbid_food": ["羊肉", "辣椒", "烈酒"],
        "region_type": 1,
    },
    {
        "solar_term": "小暑",
        "climate": "暑热上升，湿闷难耐，易中暑。",
        "health_core": "清热解暑，健脾开胃，补水盐。",
        "recommend_food": ["绿豆", "丝瓜", "冬瓜", "莲子", "鸭肉"],
        "forbid_food": ["辛辣", "油炸", "羊肉"],
        "region_type": 1,
    },
    {
        "solar_term": "大暑",
        "climate": "一年最热，湿热鼎盛，耗气伤津。",
        "health_core": "益气养阴，清暑利湿，莫贪凉。",
        "recommend_food": ["绿豆", "冬瓜", "苦瓜", "丝瓜", "鸭肉"],
        "forbid_food": ["冰饮", "羊肉", "辛辣"],
        "region_type": 1,
    },
    {
        "solar_term": "立秋",
        "climate": "暑去凉来，燥气初显，肺金当令。",
        "health_core": "滋阴润燥，养肺，少辛增酸。",
        "recommend_food": ["梨", "银耳", "百合", "蜂蜜", "芝麻"],
        "forbid_food": ["生姜", "蒜(过量)", "辛辣"],
        "region_type": 1,
    },
    {
        "solar_term": "处暑",
        "climate": "暑气渐消，秋燥明显，咽干鼻燥。",
        "health_core": "润燥清肺，健脾，防秋乏。",
        "recommend_food": ["梨", "银耳", "百合", "莲藕", "鸭肉"],
        "forbid_food": ["辛辣", "烧烤", "羊肉"],
        "region_type": 1,
    },
    {
        "solar_term": "白露",
        "climate": "昼夜温差大，燥邪伤肺，寒从足生。",
        "health_core": "润肺防燥，保暖，忌生冷。",
        "recommend_food": ["梨", "龙眼", "百合", "银耳", "糯米"],
        "forbid_food": ["冰饮", "西瓜", "螃蟹"],
        "region_type": 1,
    },
    {
        "solar_term": "秋分",
        "climate": "阴阳各半，燥凉并重，易感冒。",
        "health_core": "平补润燥，养肺胃，适温补。",
        "recommend_food": ["莲藕", "山药", "南瓜", "银耳", "鸭肉"],
        "forbid_food": ["辛辣", "生冷", "螃蟹(胃寒慎)"],
        "region_type": 1,
    },
    {
        "solar_term": "寒露",
        "climate": "气温骤降，燥寒交加，关节易痛。",
        "health_core": "温润滋补，暖身，护关节。",
        "recommend_food": ["板栗", "核桃", "羊肉(适量)", "山药", "糯米"],
        "forbid_food": ["冰饮", "生冷瓜果", "螃蟹"],
        "region_type": 1,
    },
    {
        "solar_term": "霜降",
        "climate": "秋末冬初，寒燥最甚，进补佳时。",
        "health_core": "平补气血，健脾养胃，润燥。",
        "recommend_food": ["板栗", "柿子", "山药", "牛肉", "萝卜"],
        "forbid_food": ["生冷", "西瓜", "螃蟹"],
        "region_type": 1,
    },
    {
        "solar_term": "立冬",
        "climate": "水始冰，地始冻，阳气内藏。",
        "health_core": "温补养藏，补肾，避寒就温。",
        "recommend_food": ["羊肉", "牛肉", "萝卜", "核桃", "糯米"],
        "forbid_food": ["生冷", "螃蟹", "西瓜"],
        "region_type": 1,
    },
    {
        "solar_term": "小雪",
        "climate": "天寒地冻，阴盛阳衰，气血凝滞。",
        "health_core": "温补肾阳，养血，防寒。",
        "recommend_food": ["羊肉", "牛肉", "黑豆", "核桃", "桂圆"],
        "forbid_food": ["冰饮", "生冷", "螃蟹"],
        "region_type": 1,
    },
    {
        "solar_term": "大雪",
        "climate": "雪盛寒极，万物潜藏，易阳虚。",
        "health_core": "大温补，扶阳，滋阴相济。",
        "recommend_food": ["羊肉", "牛肉", "桂圆", "红枣", "黑芝麻"],
        "forbid_food": ["生冷", "螃蟹", "西瓜"],
        "region_type": 1,
    },
    {
        "solar_term": "冬至",
        "climate": "阴极阳生，一年最寒，养藏关键。",
        "health_core": "补肾壮阳，养精蓄锐，冬至进补。",
        "recommend_food": ["羊肉", "牛肉", "饺子馅料", "桂圆", "红枣"],
        "forbid_food": ["生冷", "螃蟹", "西瓜"],
        "region_type": 1,
    },
    {
        "solar_term": "小寒",
        "climate": "冷气积久，成渝湿冷刺骨。",
        "health_core": "温补为主，驱寒，健脾。",
        "recommend_food": ["羊肉", "牛肉", "红枣", "桂圆", "糯米"],
        "forbid_food": ["生冷", "螃蟹", "西瓜"],
        "region_type": 1,
    },
    {
        "solar_term": "大寒",
        "climate": "一年最末，寒极将回暖。",
        "health_core": "温阳散寒，养血，为春发蓄力。",
        "recommend_food": ["羊肉", "牛肉", "萝卜", "红枣", "核桃"],
        "forbid_food": ["生冷", "螃蟹", "西瓜"],
        "region_type": 1,
    },
]
