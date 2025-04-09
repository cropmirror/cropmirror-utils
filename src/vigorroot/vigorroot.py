# 1. 读入不同作物、不同生育期、不同气象条件下的长势LUT文件；LUT: lookup table；三维的辐射传输方程生成；
# 2. 依据 LUT 进行长势的定量评价分级：差、较差、一般、较好、好，结果生成 .geojson；
# 3. 对长势差的 polygon 遍历各种长势差的原因；
# 3.1 缺水或者水太多造成的抑制；
#     进行LWC的反演，结合当前该品种在当前气象环境及生育期下的需水量，进行判断是否缺水；
# 3.2 缺肥或者肥太多造成的抑制；
#     判断逻辑同上，但是需要用到的算法是 LNC、LKC、LPC;
# 3.3 病害;
#     需要结合冠层温度曲线、冠层水分曲线、田间病班进行综合判断，但是田间病斑需要结合低空无人机图像（<5米），这个不易获得；
# 3.4 虫害；
#     同上，主要还是基于冠层温湿度进行判断，以及昆虫的迁飞规律；
# 3.5 草害；
#     同上；
# 3.6 低温；
#     结合气象数据；
# 3.7 台风；
#     结合气象数据；
# 对上面的原因遍历分析后，给出造成当前长势不好的原因，在后续优化中，还可以给出主因和次因；

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon

# 读取LUT文件
def read_lut(file_path):
    lut = pd.read_csv(file_path)
    return lut

# 根据LUT进行长势的定量评价分级
def evaluate_growth(lut, growth_values):
    # 假设lut中有一个列名为'growth_value'表示预测的生长值，另一个列名为'grade'表示对应的等级
    grade = lut.loc[lut['growth_value'].idxmin(), 'grade']
    for value in growth_values:
        if value < lut.iloc[0]['growth_value']:
            grade = lut.iloc[0]['grade']
        elif value > lut.iloc[-1]['growth_value']:
            grade = lut.iloc[-1]['grade']
        else:
            idx = (lut['growth_value'] - value).abs().idxmin()
            grade = lut.iloc[idx]['grade']
    return grade

# 生成GeoJSON文件
def generate_geojson(polygons, grades):
    features = []
    for poly, grade in zip(polygons, grades):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [poly.exterior.coords.xy]},
            "properties": {"grade": grade}
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    return geojson

# 分析长势差的原因
def analyze_causes(polygon_data, meteorological_data, crop_variety, growth_stage):
    causes = []

    # 检查缺水或水太多
    water_need = get_water_need(crop_variety, growth_stage, meteorological_data)
    actual_water = meteorological_data['precipitation']
    if actual_water < water_need * 0.8:
        causes.append('缺水')
    elif actual_water > water_need * 1.2:
        causes.append('水太多')

    # 检查施肥过多或过少
    nutrient_need = get_nutrient_need(crop_variety, growth_stage, meteorological_data)
    actual_nutrient = meteorological_data['nutrient']
    if actual_nutrient < nutrient_need * 0.8:
        causes.append('缺肥')
    elif actual_nutrient > nutrient_need * 1.2:
        causes.append('肥太多')

    # 检查低温
    if meteorological_data['temperature'] < get_critical_temperature(crop_variety, growth_stage):
        causes.append('低温')

    # 检查台风
    if meteorological_data['wind_speed'] > get_tropical_storm_threshold():
        causes.append('台风')

    # 其他原因（病害、虫害、草害等）需要更多的数据支持，这里假设没有这些数据
    return causes

# 获取某个作物品种在特定生育期下的需水量
def get_water_need(variety, stage, data):
    # 这里只是一个示例函数，实际应用中可能需要更复杂的计算
    base_need = 50  # 示例基础需水量
    return base_need

# 获取某个作物品种在特定生育期下的养分需求
def get_nutrient_need(variety, stage, data):
    # 这里只是一个示例函数，实际应用中可能需要更复杂的计算
    base_need = 30  # 示例基础养分需求
    return base_need

# 获取某个作物品种在特定生育期下的临界温度
def get_critical_temperature(variety, stage):
    # 这里只是一个示例函数，实际应用中可能需要更复杂的计算
    critical_temp = 15  # 示例临界温度
    return critical_temp

# 获取热带风暴阈值
def get_tropical_storm_threshold():
    tropical_storm_threshold = 34  # 示例热带风暴阈值
    return tropical_storm_threshold

# 主程序
if __name__ == "__main__":
    # 假设有多个多边形区域的数据
    polygons = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    ]

    # 假设每个多边形区域的生长值
    growth_values = [0.6, 0.3]

    # 读取LUT文件
    lut_file_path = 'path_to_your_lut.csv'
    lut = read_lut(lut_file_path)

    # 计算每个区域的生长等级
    grades = [evaluate_growth(lut, [value]) for value in growth_values]

    # 生成GeoJSON文件
    geojson = generate_geojson(polygons, grades)
    print("Generated GeoJSON:", geojson)

    # 假设气象数据
    meteorological_data = {
        'precipitation': 40,
        'nutrient': 25,
        'temperature': 10,
        'wind_speed': 40
    }

    # 分析每个区域的长势差的原因
    for i, grade in enumerate(grades):
        if grade in ['差', '较差']:
            polygon_data = {'polygon': polygons[i], 'grade': grade}
            causes = analyze_causes(polygon_data, meteorological_data, 'crop_variety_example', 'growth_stage_example')
            print(f"Polygon {i+1} 长势差的原因: {causes}")



