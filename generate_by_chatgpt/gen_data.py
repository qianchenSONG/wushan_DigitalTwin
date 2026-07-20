#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成《巫山县城迁建区管网-坡体-房屋-消防复合风险联动可视化》示意数据
所有数值均为汇报演示样例数据，非实测/普查真实数据。
"""
import json, math, random

random.seed(42)

# ---------------------------------------------------------------
# 0. 基础：迁建区沿江走向的中心线（示意，非真实测绘坐标）
#    参照巫山老县城—新县城迁建区沿长江/大宁河呈带状分布的空间特征
# ---------------------------------------------------------------
REGION_ORDER = [
    "朝云", "翠屏", "登龙", "飞凤", "集仙", "净坛", "起云",
    "上升", "神女", "圣泉", "松峦", "宁江", "聚鹤", "西坪村"
]

# 沿江示意中心线（西南->东北，弧形贴合长江河湾+大宁河口）
def centerline_point(t):
    # t in [0,1]
    lon0, lat0 = 109.8520, 31.0530
    lon1, lat1 = 109.9060, 31.0940
    # 加入弧度弯曲，模拟沿江地形
    bow = 0.010 * math.sin(t * math.pi)
    lon = lon0 + (lon1 - lon0) * t
    lat = lat0 + (lat1 - lat0) * t + bow
    return lon, lat

n = len(REGION_ORDER)
centers = {}
for i, name in enumerate(REGION_ORDER):
    t = i / (n - 1)
    lon, lat = centerline_point(t)
    centers[name] = (lon, lat)

def make_polygon(lon, lat, seed, w=0.0048, h=0.0034):
    """生成不规则多边形（六边形抖动），示意片区边界"""
    rnd = random.Random(seed)
    pts = []
    npts = 7
    for k in range(npts):
        ang = 2 * math.pi * k / npts
        rx = w * (0.72 + 0.36 * rnd.random())
        ry = h * (0.72 + 0.36 * rnd.random())
        pts.append([lon + rx * math.cos(ang), lat + ry * math.sin(ang)])
    pts.append(pts[0])
    return pts

# ---------------------------------------------------------------
# 1. 片区属性设定（结合原始汇报材料中的定性描述，量化为示意分值）
# ---------------------------------------------------------------
# 高风险片区（原始材料：高危险区主要集中在集仙社区、松峦社区）
BASE = {
    "朝云":  dict(area=0.42, population=9800,  households=3400, riskLevel="中风险", note="老旧统建房集中，管网建设年代早"),
    "翠屏":  dict(area=0.38, population=8600,  households=3000, riskLevel="一般风险", note="相对平缓，隐患点较少"),
    "登龙":  dict(area=0.51, population=12500, households=4300, riskLevel="中风险", note="县医院宿舍区，车可达水不可达"),
    "飞凤":  dict(area=0.33, population=7200,  households=2500, riskLevel="一般风险", note="局部房屋外墙脱落"),
    "集仙":  dict(area=0.55, population=15600, households=5400, riskLevel="重大风险", note="高危险区，滑坡发育密度大，防护工程病险集中"),
    "净坛":  dict(area=0.47, population=13200, households=4600, riskLevel="高风险", note="章家湾棚户区，车水均不可达"),
    "起云":  dict(area=0.36, population=8900,  households=3100, riskLevel="中风险", note="宿舍污水管道破损，遭受洪涝"),
    "上升":  dict(area=0.40, population=9700,  households=3350, riskLevel="高风险", note="小区内遭受洪涝，排水不畅"),
    "神女":  dict(area=0.34, population=7600,  households=2650, riskLevel="一般风险", note="临江高切坡渗水"),
    "圣泉":  dict(area=0.31, population=6900,  households=2400, riskLevel="一般风险", note="局部管网淤积"),
    "松峦":  dict(area=0.58, population=16200, households=5600, riskLevel="重大风险", note="高危险区，防护工程老化，边坡变形加剧"),
    "宁江":  dict(area=0.44, population=11800, households=4100, riskLevel="高风险", note="宁江社区基础开裂沉降，烟厂宿舍消防隐患"),
    "聚鹤":  dict(area=0.29, population=6200,  households=2150, riskLevel="中风险", note="摸排单元之一，屋顶漏水较普遍"),
    "西坪村": dict(area=0.62, population=5400,  households=1850, riskLevel="高风险", note="金科城片区，消防救援及时性不足"),
}

RISK_SCORE = {"一般风险": (30, 45), "中风险": (46, 60), "高风险": (61, 78), "重大风险": (79, 95)}

DEFECT_TYPES = [
    ("破裂", "rupture", "红色裂纹"),
    ("渗漏", "leak", "蓝色外溢"),
    ("变形", "deform", "橙色压缩"),
    ("淤积", "silt", "黄色沉积"),
    ("堵塞", "block", "红橙阻塞"),
    ("腐蚀", "corrode", "棕色腐蚀"),
    ("树根侵入", "root", "绿色根系"),
    ("混错接", "crossconnect", "紫橙交叉"),
    ("排口顶托", "backflow", "深红回流"),
    ("箱涵结构性缺陷", "culvertfail", "高危闪烁"),
]

SEVERITY_LEVELS = ["低风险", "中风险", "高风险", "重大风险"]
SEVERITY_WEIGHT = [0.30, 0.35, 0.24, 0.11]

PRIORITY_MAP = {"重大风险": "近期", "高风险": "近期", "中风险": "中期", "一般风险": "远期"}

def pick_severity(rnd):
    r = rnd.random()
    c = 0
    for lvl, w in zip(SEVERITY_LEVELS, SEVERITY_WEIGHT):
        c += w
        if r <= c:
            return lvl
    return SEVERITY_LEVELS[-1]

# ---------------------------------------------------------------
# 2. regions.geojson
# ---------------------------------------------------------------
region_features = []
region_meta = {}
for i, name in enumerate(REGION_ORDER):
    lon, lat = centers[name]
    poly = make_polygon(lon, lat, seed=i)
    base = BASE[name]
    lo, hi = RISK_SCORE[base["riskLevel"]]
    rnd = random.Random(i * 17 + 3)
    riskScore = rnd.randint(lo, hi)
    pipeStorm = round(rnd.uniform(1.2, 4.8), 2)
    pipeSewage = round(rnd.uniform(1.0, 4.2), 2)
    culvert = round(rnd.uniform(0.2, 1.6), 2)
    defectCount = rnd.randint(4, 16) if base["riskLevel"] in ("高风险", "重大风险") else rnd.randint(2, 8)
    majorDefectCount = max(1, round(defectCount * rnd.uniform(0.15, 0.35)))
    affectedSlope = rnd.randint(1, 5) if base["riskLevel"] in ("高风险", "重大风险") else rnd.randint(0, 2)
    affectedBuilding = rnd.randint(3, 14) if base["riskLevel"] in ("高风险", "重大风险") else rnd.randint(0, 6)
    priority = PRIORITY_MAP[base["riskLevel"]]

    region_meta[name] = dict(
        id=f"R{i+1:02d}", name=name, center=(lon, lat), riskLevel=base["riskLevel"],
        riskScore=riskScore, note=base["note"]
    )

    region_features.append({
        "type": "Feature",
        "properties": {
            "id": f"R{i+1:02d}",
            "name": name,
            "area": base["area"],
            "population": base["population"],
            "households": base["households"],
            "riskLevel": base["riskLevel"],
            "riskScore": riskScore,
            "pipeLengthStorm": pipeStorm,
            "pipeLengthSewage": pipeSewage,
            "culvertLength": culvert,
            "defectCount": defectCount,
            "majorDefectCount": majorDefectCount,
            "affectedSlopeCount": affectedSlope,
            "affectedBuildingCount": affectedBuilding,
            "recommendation": base["note"],
            "priority": priority,
            "nearbyWater": "长江" if i % 3 != 2 else "大宁河",
            "nearbySlope": f"{name}片区高切坡/挡墙风险段" if affectedSlope > 0 else "暂无重大边坡关联",
            "drainOutlet": f"{name}排口" if i % 2 == 0 else f"{REGION_ORDER[max(0,i-1)]}—{name}联合排口",
        },
        "geometry": {"type": "Polygon", "coordinates": [poly]}
    })

regions_geojson = {"type": "FeatureCollection", "features": region_features,
                    "meta": {"note": "示意数据，待实测成果校核；片区边界为示意，非正式GIS成果"}}

# ---------------------------------------------------------------
# 3. pipes.geojson —— 沿相邻片区连接生成 干管(雨水/污水) + 箱涵支线
# ---------------------------------------------------------------
pipe_features = []
pid = 1
MATERIALS = ["混凝土管", "PVC管", "砖砌箱涵", "钢筋混凝土箱涵", "铸铁管"]

def river_point_near(lon, lat, i):
    # 示意：河道在片区东南侧
    return lon + 0.006, lat - 0.004

for i in range(n - 1):
    a, b = REGION_ORDER[i], REGION_ORDER[i + 1]
    lon_a, lat_a = centers[a]
    lon_b, lat_b = centers[b]
    rnd = random.Random(i * 31 + 7)

    # 雨水干管
    pipe_features.append({
        "type": "Feature",
        "properties": {
            "id": f"P{pid:03d}", "name": f"{a}-{b}雨水干管", "type": "stormwater",
            "diameter": rnd.choice([300, 400, 500, 600, 800]),
            "material": rnd.choice(MATERIALS[:2]),
            "length": round(rnd.uniform(180, 520), 0),
            "buildYear": rnd.randint(1994, 2008),
            "flowDirection": f"{a}→{b}",
            "upstreamRegion": region_meta[a]["id"], "downstreamRegion": region_meta[b]["id"],
            "status": rnd.choice(["运行一般", "存在缺陷", "亟需修复"]),
            "riskLevel": rnd.choice(SEVERITY_LEVELS),
        },
        "geometry": {"type": "LineString", "coordinates": [[lon_a, lat_a], [lon_b, lat_b]]}
    })
    pid += 1

    # 污水干管（稍偏移，避免与雨水管重叠可视化）
    off = 0.0009
    pipe_features.append({
        "type": "Feature",
        "properties": {
            "id": f"P{pid:03d}", "name": f"{a}-{b}污水干管", "type": "sewage",
            "diameter": rnd.choice([200, 300, 400]),
            "material": rnd.choice(MATERIALS),
            "length": round(rnd.uniform(160, 480), 0),
            "buildYear": rnd.randint(1994, 2008),
            "flowDirection": f"{a}→{b}",
            "upstreamRegion": region_meta[a]["id"], "downstreamRegion": region_meta[b]["id"],
            "status": rnd.choice(["运行一般", "存在缺陷", "亟需修复", "雨污混错接"]),
            "riskLevel": rnd.choice(SEVERITY_LEVELS),
        },
        "geometry": {"type": "LineString", "coordinates": [[lon_a + off, lat_a - off], [lon_b + off, lat_b - off]]}
    })
    pid += 1

# 混错接问题管段（挑几段单独标注为 combined 高亮）
for name in ["起云", "上升", "宁江"]:
    lon, lat = centers[name]
    pipe_features.append({
        "type": "Feature",
        "properties": {
            "id": f"P{pid:03d}", "name": f"{name}雨污混错接段", "type": "combined",
            "diameter": 300, "material": "混凝土管", "length": round(random.uniform(80, 180), 0),
            "buildYear": random.randint(1996, 2006), "flowDirection": f"{name}内部",
            "upstreamRegion": region_meta[name]["id"], "downstreamRegion": region_meta[name]["id"],
            "status": "雨污混错接", "riskLevel": "高风险",
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[lon - 0.0015, lat + 0.0009], [lon + 0.0012, lat - 0.0007]]}
    })
    pid += 1

# 排洪箱涵/渠道（片区通往长江/大宁河）
outlet_features = []
oid = 1
for name in ["朝云", "集仙", "净坛", "松峦", "宁江", "西坪村"]:
    lon, lat = centers[name]
    rlon, rlat = river_point_near(lon, lat, 0)
    pipe_features.append({
        "type": "Feature",
        "properties": {
            "id": f"P{pid:03d}", "name": f"{name}排洪箱涵", "type": "culvert",
            "diameter": None, "material": "砖砌/浆砌箱涵", "length": round(random.uniform(300, 900), 0),
            "buildYear": random.randint(1994, 2005), "flowDirection": f"{name}→长江/大宁河",
            "upstreamRegion": region_meta[name]["id"], "downstreamRegion": "OUTLET",
            "status": random.choice(["存在淤积", "存在破损", "存在脱空风险", "运行基本正常"]),
            "riskLevel": random.choice(["中风险", "高风险", "重大风险"]),
        },
        "geometry": {"type": "LineString", "coordinates": [[lon, lat], [rlon, rlat]]}
    })
    # 排口节点
    outlet_features.append({
        "type": "Feature",
        "properties": {
            "id": f"O{oid:02d}", "name": f"{name}入江排口", "regionId": region_meta[name]["id"],
            "backflowRisk": random.choice(["低", "中", "高"]),
        },
        "geometry": {"type": "Point", "coordinates": [rlon, rlat]}
    })
    pid += 1
    oid += 1

pipes_geojson = {"type": "FeatureCollection", "features": pipe_features,
                  "meta": {"note": "示意数据，管径/材质/建设年代/长度均为汇报演示样例"}}
outlets_geojson = {"type": "FeatureCollection", "features": outlet_features}

# ---------------------------------------------------------------
# 4. defects.geojson —— 沿管线撒点
# ---------------------------------------------------------------
defect_features = []
did = 1
line_pipes = [f for f in pipe_features if f["properties"]["type"] in ("stormwater", "sewage", "combined", "culvert")]

for name in REGION_ORDER:
    rmeta = region_meta[name]
    count = next(f["properties"]["defectCount"] for f in region_features if f["properties"]["name"] == name)
    lon0, lat0 = rmeta["center"]
    rnd = random.Random(hash(name) % 10000)
    # 找到与该片区相关的管线
    related_pipes = [p for p in line_pipes if p["properties"]["upstreamRegion"] == rmeta["id"]
                      or p["properties"]["downstreamRegion"] == rmeta["id"]]
    if not related_pipes:
        related_pipes = line_pipes[:3]
    for k in range(count):
        dtype, dtype_en, _ = rnd.choice(DEFECT_TYPES)
        sev = pick_severity(rnd)
        pipe = rnd.choice(related_pipes)
        jitter_lon = lon0 + rnd.uniform(-0.0022, 0.0022)
        jitter_lat = lat0 + rnd.uniform(-0.0016, 0.0016)
        urgency = "立即处置" if sev == "重大风险" else ("近期处置" if sev == "高风险" else ("纳入计划" if sev == "中风险" else "常规巡查"))
        defect_features.append({
            "type": "Feature",
            "properties": {
                "id": f"D{did:04d}",
                "pipeId": pipe["properties"]["id"],
                "regionId": rmeta["id"],
                "regionName": name,
                "defectType": dtype,
                "defectTypeEn": dtype_en,
                "severity": sev,
                "cctvScore": round(rnd.uniform(1.5, 9.8), 1),
                "qvResult": rnd.choice(["确认缺陷", "疑似缺陷", "缺陷已核实", "待复检"]),
                "description": f"{name}片区{pipe['properties']['name']}发现{dtype}问题，示意描述，待现场复核。",
                "photoUrl": "assets/photo_placeholder.svg",
                "impactRadius": {"低风险": 50, "中风险": 100, "高风险": 150, "重大风险": 200}[sev],
                "suggestedAction": {
                    "破裂": "开挖修复/内衬修复", "渗漏": "注浆封堵/管道修复", "变形": "开挖更换/结构补强",
                    "淤积": "清淤疏通", "堵塞": "清疏/清除障碍物", "腐蚀": "管道修复/更换",
                    "树根侵入": "清疏+根系阻隔处理", "混错接": "雨污分流改造", "排口顶托": "排口防倒灌改造",
                    "箱涵结构性缺陷": "箱涵结构修复/加固"
                }[dtype],
                "urgency": urgency,
            },
            "geometry": {"type": "Point", "coordinates": [jitter_lon, jitter_lat]}
        })
        did += 1

defects_geojson = {"type": "FeatureCollection", "features": defect_features,
                    "meta": {"note": "示意数据：缺陷类型/严重程度/CCTV评分均为汇报演示样例，非实测CCTV/QV检测结果"}}

# ---------------------------------------------------------------
# 5. 边坡/挡墙风险面、房屋风险点、消防瓶颈点（用于图层与关联关系）
# ---------------------------------------------------------------
slope_features = []
sid = 1
for name in ["集仙", "松峦", "净坛", "神女", "宁江"]:
    lon, lat = centers[name]
    rmeta = region_meta[name]
    poly = make_polygon(lon + 0.0018, lat + 0.0012, seed=sid * 5, w=0.0022, h=0.0016)
    slope_features.append({
        "type": "Feature",
        "properties": {
            "id": f"S{sid:02d}", "name": f"{name}高切坡/挡墙风险段", "regionId": rmeta["id"],
            "type": random.choice(["高切坡", "高挡墙", "滑坡体防护工程"]),
            "status": random.choice(["变形加剧", "渗水+局部滑塌", "老化/效能不足", "监测中"]),
        },
        "geometry": {"type": "Polygon", "coordinates": [poly]}
    })
    sid += 1
slopes_geojson = {"type": "FeatureCollection", "features": slope_features}

building_features = []
bid = 1
for name in REGION_ORDER:
    rmeta = region_meta[name]
    lon0, lat0 = rmeta["center"]
    cnt = random.randint(1, 4) if rmeta["riskLevel"] in ("高风险", "重大风险") else random.randint(0, 2)
    for k in range(cnt):
        building_features.append({
            "type": "Feature",
            "properties": {
                "id": f"B{bid:03d}", "name": f"{name}#{k+1}疑似结构风险房屋", "regionId": rmeta["id"],
                "issue": random.choice(["墙体开裂", "基础开裂变形", "外墙瓷砖脱落", "楼板疑似开裂", "屋顶漏水"]),
                "grade": random.choice(["B级(危险点)", "C级(局部危房)", "待鉴定"]),
            },
            "geometry": {"type": "Point",
                         "coordinates": [lon0 + random.uniform(-0.0018, 0.0018), lat0 + random.uniform(-0.0013, 0.0013)]}
        })
        bid += 1
buildings_geojson = {"type": "FeatureCollection", "features": building_features}

fire_features = []
fid = 1
for name in ["净坛", "西坪村", "登龙"]:
    rmeta = region_meta[name]
    lon0, lat0 = rmeta["center"]
    fire_features.append({
        "type": "Feature",
        "properties": {
            "id": f"F{fid:02d}", "name": f"{name}消防通道瓶颈点", "regionId": rmeta["id"],
            "issue": random.choice(["车不可达水可达(一般风险)", "车可达水不可达(中风险)", "车水均不可达(高风险)"]),
        },
        "geometry": {"type": "Point",
                     "coordinates": [lon0 + random.uniform(-0.0015, 0.0015), lat0 + random.uniform(-0.001, 0.001)]}
    })
    fid += 1
fire_geojson = {"type": "FeatureCollection", "features": fire_features}

waterlog_features = []
wid = 1
for name in ["起云", "上升", "圣泉"]:
    rmeta = region_meta[name]
    lon0, lat0 = rmeta["center"]
    waterlog_features.append({
        "type": "Feature",
        "properties": {"id": f"W{wid:02d}", "name": f"{name}内涝易发点", "regionId": rmeta["id"]},
        "geometry": {"type": "Point",
                     "coordinates": [lon0 + random.uniform(-0.0012, 0.0012), lat0 + random.uniform(-0.0009, 0.0009)]}
    })
    wid += 1
waterlog_geojson = {"type": "FeatureCollection", "features": waterlog_features}

# ---------------------------------------------------------------
# 6. relations.json —— 风险链关系
# ---------------------------------------------------------------
relations = []
rel_id = 1
REL_TYPES = ["渗漏影响", "排水不畅", "排口顶托", "内涝影响", "消防受阻", "房屋基础影响"]

for d in defect_features:
    p = d["properties"]
    if p["severity"] in ("高风险", "重大风险"):
        # 关联到该片区的边坡（若有）
        region_slopes = [s for s in slope_features if s["properties"]["regionId"] == p["regionId"]]
        if region_slopes and random.random() < 0.7:
            s = random.choice(region_slopes)
            relations.append({
                "id": f"REL{rel_id:04d}", "sourceType": "defect", "sourceId": p["id"],
                "targetType": "slope", "targetId": s["properties"]["id"],
                "relationType": random.choice(["渗漏影响", "排水不畅"]),
                "confidence": round(random.uniform(0.55, 0.92), 2),
                "description": f"{p['defectType']}导致坡体滞水/挡墙渗水风险上升，需与边坡治理协同实施。"
            })
            rel_id += 1
        region_buildings = [b for b in building_features if b["properties"]["regionId"] == p["regionId"]]
        if region_buildings and random.random() < 0.55:
            b = random.choice(region_buildings)
            relations.append({
                "id": f"REL{rel_id:04d}", "sourceType": "defect", "sourceId": p["id"],
                "targetType": "building", "targetId": b["properties"]["id"],
                "relationType": "房屋基础影响",
                "confidence": round(random.uniform(0.5, 0.88), 2),
                "description": f"{p['defectType']}长期渗漏可能影响周边房屋地基不均匀沉降。"
            })
            rel_id += 1
        region_waterlog = [w for w in waterlog_features if w["properties"]["regionId"] == p["regionId"]]
        if region_waterlog and random.random() < 0.4:
            w = random.choice(region_waterlog)
            relations.append({
                "id": f"REL{rel_id:04d}", "sourceType": "defect", "sourceId": p["id"],
                "targetType": "waterlogging", "targetId": w["properties"]["id"],
                "relationType": "内涝影响",
                "confidence": round(random.uniform(0.5, 0.85), 2),
                "description": f"{p['defectType']}降低排水能力，加剧本片区内涝风险。"
            })
            rel_id += 1
        region_fire = [x for x in fire_features if x["properties"]["regionId"] == p["regionId"]]
        if region_fire and random.random() < 0.3:
            x = random.choice(region_fire)
            relations.append({
                "id": f"REL{rel_id:04d}", "sourceType": "defect", "sourceId": p["id"],
                "targetType": "fireAccess", "targetId": x["properties"]["id"],
                "relationType": "消防受阻",
                "confidence": round(random.uniform(0.45, 0.8), 2),
                "description": "道路积水/塌陷风险叠加，可能阻碍消防车辆通行。"
            })
            rel_id += 1

# 箱涵->排口 顶托关系
for p in pipe_features:
    if p["properties"]["type"] == "culvert" and p["properties"]["riskLevel"] in ("高风险", "重大风险"):
        matched_outlet = next((o for o in outlet_features if o["properties"]["regionId"] == p["properties"]["upstreamRegion"]), None)
        if matched_outlet:
            relations.append({
                "id": f"REL{rel_id:04d}", "sourceType": "culvert", "sourceId": p["properties"]["id"],
                "targetType": "outlet", "targetId": matched_outlet["properties"]["id"],
                "relationType": "排口顶托",
                "confidence": round(random.uniform(0.6, 0.9), 2),
                "description": "箱涵结构性缺陷叠加汛期高水位，存在排口顶托、上游壅水风险。"
            })
            rel_id += 1

relations_json = {"relations": relations,
                   "meta": {"note": "示意关系数据，用于展示风险链逻辑，非实测因果关系鉴定结论"}}

# ---------------------------------------------------------------
# 7. 汇总总览指标 & 片区排序（供 app.js 直接使用，避免前端重复计算）
# ---------------------------------------------------------------
total_storm = sum(f["properties"]["pipeLengthStorm"] for f in region_features)
total_sewage = sum(f["properties"]["pipeLengthSewage"] for f in region_features)
total_culvert = sum(f["properties"]["culvertLength"] for f in region_features)
total_defect = sum(f["properties"]["defectCount"] for f in region_features)
total_major_defect = sum(f["properties"]["majorDefectCount"] for f in region_features)
total_slope_affect = sum(f["properties"]["affectedSlopeCount"] for f in region_features)
high_risk_regions = [f["properties"]["name"] for f in region_features if f["properties"]["riskLevel"] in ("高风险", "重大风险")]

overview = {
    "note": "以下均为汇报演示示意数据，正式成果以实测、普查、CCTV/QV检测及甲方确认数据为准",
    "regionArea": round(sum(f["properties"]["area"] for f in region_features), 2),
    "regionCount": len(region_features),
    "totalPipeLength": round(total_storm + total_sewage, 1),
    "totalCulvertLength": round(total_culvert, 1),
    "totalDefects": total_defect,
    "majorDefects": total_major_defect,
    "affectedSlopes": total_slope_affect,
    "priorityRegions": len(high_risk_regions),
    "priorityRegionNames": high_risk_regions,
    "regionRanking": sorted(
        [{"name": f["properties"]["name"], "riskScore": f["properties"]["riskScore"],
          "riskLevel": f["properties"]["riskLevel"], "priority": f["properties"]["priority"]}
         for f in region_features],
        key=lambda x: -x["riskScore"]
    )
}

# ---------------------------------------------------------------
# 写文件
# ---------------------------------------------------------------
import os
OUT = "data"
os.makedirs(OUT, exist_ok=True)

with open(f"{OUT}/regions.geojson", "w", encoding="utf-8") as f:
    json.dump(regions_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/pipes.geojson", "w", encoding="utf-8") as f:
    json.dump(pipes_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/outlets.geojson", "w", encoding="utf-8") as f:
    json.dump(outlets_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/defects.geojson", "w", encoding="utf-8") as f:
    json.dump(defects_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/slopes.geojson", "w", encoding="utf-8") as f:
    json.dump(slopes_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/buildings.geojson", "w", encoding="utf-8") as f:
    json.dump(buildings_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/fireaccess.geojson", "w", encoding="utf-8") as f:
    json.dump(fire_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/waterlogging.geojson", "w", encoding="utf-8") as f:
    json.dump(waterlog_geojson, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/relations.json", "w", encoding="utf-8") as f:
    json.dump(relations_json, f, ensure_ascii=False, indent=1)
with open(f"{OUT}/overview.json", "w", encoding="utf-8") as f:
    json.dump(overview, f, ensure_ascii=False, indent=1)

print("regions:", len(region_features))
print("pipes:", len(pipe_features))
print("defects:", len(defect_features))
print("relations:", len(relations))
print("overview:", json.dumps(overview, ensure_ascii=False)[:300])
