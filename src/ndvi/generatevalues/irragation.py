
import logging
import math

import geopandas as gpd


import rasterio.sample  # 否则pyinstaller打包时会报错;
import rasterio.vrt  # 否则pyinstaller打包时会报错;
import rasterio._features  # 否则pyinstaller打包时会报错;

from rasterstats import zonal_stats


# 创建 class Irrigation
# long.liu89@hotmail.com
# 2025-2-2 10:48:10

# 依据水量平衡方程，判断灌溉的需水量
def water_balance_calculation_base_irrigation( ndvi_geotiff_file, valued_shp_file, 
                                                precipitation, evapotranspiration, 
                                                runoff, deep_percolation, 
                                                initial_soil_moisture, target_soil_moisture):
    """
    计算基于水量平衡方程的基本灌溉需求。
    
    参数:
    precipitation (float): 降水量 (毫米)
    evapotranspiration (float): 蒸发蒸腾量 (毫米)
    runoff (float): 地表径流量 (毫米)
    deep_percolation (float): 深层渗漏量 (毫米)
    initial_soil_moisture (float): 初始土壤含水量 (毫米)
    target_soil_moisture = 300  # 假设目标土壤含水量为300毫米
    
    返回:
    float: 推荐灌溉量 (立方米/亩) 1升 = 1000立方米
    """
    # 计算土壤储水量的变化
    delta_s = precipitation - evapotranspiration - runoff - deep_percolation
    
    # 根据实际需要调整土壤含水量到目标值所需的灌溉量（这里简化处理）
    
    irrigation_needed = max(0, target_soil_moisture - (initial_soil_moisture + delta_s))
    
    # 假设每亩面积为667平方米，转换为立方米水
    # irrigation_volume_liters_per_mu = irrigation_needed * 667
    irrigation_volume_m3_per_mu = irrigation_needed * 667

    zone_indexes = get_zone_indexes(ndvi_geotiff_file,valued_shp_file)
    #
    irrigation_volume_m3_values = []
    # for index, zone_ndvi in enumerate(self.zone_indexes):
    for (
        index,
        zone_ndvi,
    ) in zone_indexes.items():  # 使用 .items() 来获取键和值
        zone_irrigation_volume = irrigation_volume_m3_per_mu * (zone_ndvi)  
        # 根据 NDVI 调整施药量
        # if zone_ndvi < 0.3:
        #     zone_pesticide_dose *= 1.5
        # elif zone_ndvi >= 0.3 and zone_ndvi < 0.6:
        #     zone_pesticide_dose *= 1.0
        # elif zone_ndvi >= 0.6:
        #     zone_pesticide_dose *= 0.5

        zone_irrigation_volume = float(math.ceil(zone_irrigation_volume*100.0)/100.0)
        irrigation_volume_m3_values.append(zone_irrigation_volume)
        logging.info(
            f"Irrigation required for zone {index + 1} (NDVI={zone_ndvi}): {zone_irrigation_volume:.2f} L/mu"
        )

    irrigation_volume_m3_values.sort()

    return irrigation_volume_m3_values, irrigation_volume_m3_per_mu
    
    # return irrigation_volume_m3_per_mu

def get_zone_indexes( geotiff_file, shp_file):
    """
    Calculate the average NDVI or other pixel values for each unique value in the shapefile,
    based on the GeoTIFF raster data.

    :param geotiff_file: Path to the GeoTIFF file (e.g., NDVI data).
    :param shp_file: Path to the shapefile that defines zones with 'value' attribute.
    :return: A dictionary where keys are unique 'value' attributes and values are the average NDVI for each.
    """
    try:
        # 读取形状文件 (Shapefile)
        zones_gdf = gpd.read_file(shp_file)

        # 确保 'value' 字段存在
        if "value" not in zones_gdf.columns:
            raise ValueError("'value' column not found in the Shapefile")

        # 读取 GeoTIFF 文件
        with rasterio.open(geotiff_file) as src:
            affine = src.transform  # 获取地理变换信息
            raster = src.read(1)  # 读取第一波段数据，假设 NDVI 或其他指数在第一波段

        # 获取唯一的 value 属性
        unique_values = zones_gdf["value"].unique()

        # 存储每个 'value' 的平均值
        value_mean_dict = {}

        # 对每个 'value' 进行 zonal_stats 计算
        for val in unique_values:
            # 提取 Shapefile 中与当前 'value' 对应的多边形
            value_zones = zones_gdf[zones_gdf["value"] == val]

            # 计算该 'value' 区域的栅格平均值
            zone_stats = zonal_stats(
                value_zones,
                raster,
                affine=affine,
                stats=["mean"],
                nodata=src.nodata,
            )

            # 提取统计结果的平均值
            value_mean = sum(
                [stat["mean"] for stat in zone_stats if stat["mean"] is not None]
            ) / len(zone_stats)

            # 将平均值存入字典
            value_mean_dict[val] = value_mean

        # 输出每个 'value' 的平均值（NDVI 等）
        for value, mean_value in value_mean_dict.items():
            logging.info(f"Value {value} average NDVI: {mean_value}")

        return value_mean_dict

    except Exception as e:
        raise Exception(f"Error calculating zone indexes: {e}")