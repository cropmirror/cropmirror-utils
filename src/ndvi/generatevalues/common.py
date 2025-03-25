import logging
import math

import geopandas as gpd


import rasterio.sample  # 否则pyinstaller打包时会报错;
import rasterio.vrt  # 否则pyinstaller打包时会报错;
import rasterio._features  # 否则pyinstaller打包时会报错;

from rasterstats import zonal_stats

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

