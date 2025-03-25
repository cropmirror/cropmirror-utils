import datetime
import logging
import fiona
import os
import pyproj
from osgeo import gdal, ogr
import math
import numpy as np
import pandas as pd
import json
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pathlib import Path



from tqdm import tqdm, trange
import rasterio as rio
import rasterio.sample  # 否则pyinstaller打包时会报错;
import rasterio.vrt  # 否则pyinstaller打包时会报错;
import rasterio._features  # 否则pyinstaller打包时会报错;
from rasterio.plot import show
from rasterio.windows import Window
from rasterio.enums import Resampling
import os
from fiona.crs import from_epsg
from typing import List
from rasterstats import zonal_stats
import sys

class Fertilization:
    # 根据作物类型设置每千克产量的氮磷钾需求量
    crop_demand_g_per_kg={
        "wheat":{
            "nitrogen": 25.0,
            "porphorus": 12.0,
            "kassium": 20.0
        },
        "maize":{
            "nitrogen": 25.0,
            "porphorus": 12.0,
            "kassium": 20.0
        },
    }
    # 根据作物类型和生育期设置氮需求量比例
    nitrogen_demand_ratio={
            "wheat": {
                "seeding_wheat": 0.15,  # 苗期
                "tillering_wheat": 0.35,  # 分蘖期
                "jointing_wheat": 0.25,  # 拔节期
                "booting_wheat": 0.15,  # 抽穗期
                "grain_filling_wheat": 0.10,  # 灌浆期
            },
            "maize": {
                "emergence_maize": 0.10,  # 出苗期
                "vegetative_maize": 0.40,  # 营养生长期
                "tasseling_maize": 0.30,  # 抽雄期
                "grain_filling_maize": 0.20,  # 灌浆期
            },
        }
    # 根据作物类型和生育期设置钾需求量比例
    kassium_demand_ratio={
            "wheat": {
                "seeding_wheat": 0.15,  # 苗期
                "tillering_wheat": 0.35,  # 分蘖期
                "jointing_wheat": 0.25,  # 拔节期
                "booting_wheat": 0.15,  # 抽穗期
                "grain_filling_wheat": 0.10,  # 灌浆期
            },
            "maize": {
                "emergence_maize": 0.10,  # 出苗期
                "vegetative_maize": 0.40,  # 营养生长期
                "tasseling_maize": 0.30,  # 抽雄期
                "grain_filling_maize": 0.20,  # 灌浆期
            },
        }
    # 根据作物类型和生育期设置磷需求量比例
    porphorus_demand_ratio={
            "wheat": {
                "seeding_wheat": 0.15,  # 苗期
                "tillering_wheat": 0.35,  # 分蘖期
                "jointing_wheat": 0.25,  # 拔节期
                "booting_wheat": 0.15,  # 抽穗期
                "grain_filling_wheat": 0.10,  # 灌浆期
            },
            "maize": {
                "emergence_maize": 0.10,  # 出苗期
                "vegetative_maize": 0.40,  # 营养生长期
                "tasseling_maize": 0.30,  # 抽雄期
                "grain_filling_maize": 0.20,  # 灌浆期
            },
        }
    def __init__(
        self,
        fertilizer_type="base",  # 基肥
        fertilizer_form="mixed",  # 混合肥 or 单质肥
        fertilizer_npk_ratio=[15, 15, 15],  # NPK 比例
        fertilizer_average_value_manual = 375, # kg/ha 人工输入的平均施肥量

        # --- crop related variables ---
        crop_type="maize",
        crop_phenology="tasseling_maize",  #'tillering',
        
        # 未用
        crop_variaties="明科玉77",  #'鲁单9088', 未用
        
        crop_target_yield_kg_per_ha=10000,  # kg/ha, ex: 10000 kg/ha = 10 t/ha
        
        crop_nitrogen_use_efficiency=0.3, # 土壤有关?
        # --- crop porphorus related variables ---
        crop_porphorus_use_efficiency=0.3,
        # --- crop kassium related variables ---
        crop_kassium_use_efficiency=0.3,

        # 未用 追肥
        # --- weather related variables ---
        weather_station_id="CN101010100",
        weather_station_latitude=48.908995,
        weather_station_longitude=125.207581,
        weather_station_elevation=0.0,
        # weather_station_timezone = 'Asia/Shanghai',
        # weather_station_timezone_offset = 8.0,
        # weather_station_timezone_dst = 0.0,
        # weather_station_timezone_dst_start = '2023-03-08',
        # weather_station_timezone_dst_end = '2023-11-01',
        # weather_station_timezone_dst_start_offset = 0.0,
        # weather_station_timezone_dst_end_offset = 0.0,
        # weather_cumulative_rainfall = 0.0,
        # weather_cumulative_snowfall = 0.0,
        weather_cumulative_temperature=0.0,
        # weather_cumulative_windspeed = 0.0,
        # weather_cumulative_humidity = 0.0,
        weather_cumulative_precipitation=0.0,
        # weather_cumulative_snowdepth = 0.0,
        # weather_cumulative_snowmelt = 0.0,
        # --- soil related variables ---

        soil_alkali_hydrolyzable_n_mg_per_kg=191.32,  # mg/kg
        soil_available_p_mg_per_kg=34.251,  # mg/kg
        soil_available_k_mg_per_kg=250.177,  # mg/kg
        soil_bulk_density_kg_per_m3=1300,  # kg/m^3
        soil_layer_depth_cm=20,  # cm; 只考虑20cm耕层的土壤养分
        
        # 未用  基肥
        soil_type="sandy loam",
        soil_pH=6.0,
        soil_sampling_latitude=48.908995,
        soil_sampling_longitude=125.207581,
        soil_sampling_date="2023-05-01T08:00:00Z",
        # soil_sampling_time="08:00:00",
        soil_sampling_method="sampling",
        soil_sampling_depth_cm=0.0,  # cm
        soil_sampling_temperature=0.0,
        soil_sampling_temperature_depth=0.0,
        soil_sampling_humidity=0.0,
        soil_sampling_humidity_depth=0.0,
        # --- fertilizer related variables ---
        fertilizer_npk_type="Nitrogen",
        fertilizer_amount=0.0,
        fertilizer_application_date="2023-05-01T08:00:00Z",
        # fertilizer_application_time="08:00:00",
        fertilizer_application_method="spraying",
        fertilizer_application_machine="T60",
    ) -> None:
        
        # --- dpm related variables ---

        self.fertilizer_type = fertilizer_type # base;follow
        self.fertilizer_form = fertilizer_form # single;mixed
        self.fertilizer_npk_ratio = fertilizer_npk_ratio # for mixed
        self.fertilizer_average_value_manual = fertilizer_average_value_manual
        # --- crop related variables ---
        self.crop_type = crop_type
        self.crop_phenology = crop_phenology  #'tillering',
        self.crop_variaties = crop_variaties  #'鲁单9088',
        self.crop_target_yield_kg_per_ha = crop_target_yield_kg_per_ha  # kg/ha, ex: 10000 kg/ha = 10 t/ha

        # --- crop nitrogen related variables ---
        self.crop_nitrogen_demand_g_per_kg = self.crop_demand_g_per_kg[crop_type]["nitrogen"]  # pure N, 纯氮
        self.crop_nitrogen_use_efficiency = crop_nitrogen_use_efficiency


        # --- crop porphorus related variables ---
        self.crop_porphorus_demand_g_per_kg = self.crop_demand_g_per_kg[crop_type]["porphorus"]
        self.crop_porphorus_use_efficiency = crop_porphorus_use_efficiency

        # --- crop kassium related variables ---
        self.crop_kassium_demand_g_per_kg = self.crop_demand_g_per_kg[crop_type]["kassium"]  # K2O
        self.crop_kassium_use_efficiency = crop_kassium_use_efficiency

        # 从字典中获取当前作物类型及当前生育期对应的氮肥比例
        self.ratio_nitrogen = self.nitrogen_demand_ratio[crop_type][crop_phenology]
        # 从字典中获取当前作物类型及当前生育期对应的磷肥比例
        self.ratio_porphorus = self.porphorus_demand_ratio[crop_type][crop_phenology]
         # 从字典中获取当前作物类型及当前生育期对应的钾肥比例
        self.ratio_kassium = self.kassium_demand_ratio[crop_type][crop_phenology]

        # --- weather related variables ---
        self.weather_station_id = weather_station_id
        self.weather_station_latitude = weather_station_latitude
        self.weather_station_longitude = weather_station_longitude
        self.weather_station_elevation = weather_station_elevation
        # self.weather_station_timezone = 'Asia/Shanghai'
        # self.weather_station_timezone_offset = 8.0
        # self.weather_station_timezone_dst = 0.0
        # self.weather_station_timezone_dst_start = '2023-03-08'
        # self.weather_station_timezone_dst_end = '2023-11-01'
        # self.weather_station_timezone_dst_start_offset = 0.0
        # self.weather_station_timezone_dst_end_offset = 0.0
        # self.weather_cumulative_rainfall = 0.0
        # self.weather_cumulative_snowfall = 0.0
        self.weather_cumulative_temperature = weather_cumulative_temperature
        # self.weather_cumulative_windspeed = 0.0
        # self.weather_cumulative_humidity = 0.0
        self.weather_cumulative_precipitation = weather_cumulative_precipitation
        # self.weather_cumulative_snowdepth = 0.0
        # self.weather_cumulative_snowmelt = 0.0

        # --- soil related variables ---
        self.soil_type = soil_type
        self.soil_pH = soil_pH
        self.soil_alkali_hydrolyzable_n_mg_per_kg = soil_alkali_hydrolyzable_n_mg_per_kg  # mg/kg
        self.soil_available_p_mg_per_kg = soil_available_p_mg_per_kg  # mg/kg
        self.soil_available_k_mg_per_kg = soil_available_k_mg_per_kg  # mg/kg
        self.soil_bulk_density_kg_per_m3 = soil_bulk_density_kg_per_m3  # kg/m^3
        self.soil_layer_depth_cm = soil_layer_depth_cm  # cm; 只考虑20cm耕层的土壤养分
        self.soil_sampling_latitude = soil_sampling_latitude
        self.soil_sampling_longitude = soil_sampling_longitude
        self.soil_sampling_date = soil_sampling_date

        self.soil_sampling_method = soil_sampling_method
        self.soil_sampling_depth_cm = soil_sampling_depth_cm  # cm
        self.soil_sampling_temperature = soil_sampling_temperature
        self.soil_sampling_temperature_depth = soil_sampling_temperature_depth
        self.soil_sampling_humidity = soil_sampling_humidity
        self.soil_sampling_humidity_depth = soil_sampling_humidity_depth

        # --- fertilizer related variables ---
        self.fertilizer_npk_type = fertilizer_npk_type
        self.fertilizer_amount = fertilizer_amount
        self.fertilizer_application_date = fertilizer_application_date
        self.fertilizer_application_method = fertilizer_application_method
        self.fertilizer_application_machine = fertilizer_application_machine

    def calculate_fertilizer_amount(
        self, required_n, required_p, required_k, fertilizer_npk_ratio
    ):
        """
        根据氮、磷、钾的需求量计算混合肥的用量。

        参数:
        required_n: 需求氮量 (kg/ha)
        required_p: 需求磷量 (kg/ha)
        required_k: 需求钾量 (kg/ha)
        fertilizer_npk_ratio: 混合肥中 N-P-K 的比例 (例如 [15, 15, 15])

        返回:
        需要施用的混合肥量 (kg/ha)
        """
        n_ratio, p_ratio, k_ratio = fertilizer_npk_ratio

        # 分别计算满足每种养分需求所需的肥料量
        fertilizer_amount_n = required_n / (n_ratio / 100.0)
        fertilizer_amount_p = required_p / (p_ratio / 100.0)
        fertilizer_amount_k = required_k / (k_ratio / 100.0)

        # 返回满足所有养分需求所需的最大肥料量
        return max(fertilizer_amount_n, fertilizer_amount_p, fertilizer_amount_k)

    # 依据养分平衡方程，判断基肥的施肥量
    def nutrients_balance_calculation_base_fertilization(self,geotiff_file,valued_shp_file):
        """
        Calculate the fertilizer requirements based on soil nutrient content, crop requirements, and residual nutrients.
        This function should be updated according to the specific crop type and growth stage.
        """

        # Example inputs: these would be fetched or calculated based on the crop and soil data
        # crop_type = "maize"  # Example crop type, could be passed as a parameter or part of the class
        # crop_phenology = "tillering"  # Example growth stage
        
        zone_indexes = self.get_zone_indexes(geotiff_file,valued_shp_file)
        
        crop_type = self.crop_type
        crop_phenology = self.crop_phenology

        # 计算总氮需求量
        crop_total_nitrogen_demand = (
            self.crop_target_yield_kg_per_ha * self.crop_nitrogen_demand_g_per_kg / 1000
        )  # kg 纯氮, 这几行代码上面应该添加针对氮需求量的描述；
        crop_total_porphorus_demand = (
            self.crop_target_yield_kg_per_ha * self.crop_porphorus_demand_g_per_kg / 1000
        )  # kg P2O5
        crop_total_kassium_demand = (
            self.crop_target_yield_kg_per_ha * self.crop_kassium_demand_g_per_kg / 1000
        )  # kg K2O

        # Soil nutrient levels (could be fetched from a database or input as parameters)
        # soil_n = 50  # Available Nitrogen (kg/ha)
        # soil_p = 20  # Available Phosphorus (kg/ha)
        # soil_k = 30  # Available Potassium (kg/ha)

        soil_n = (
            self.soil_alkali_hydrolyzable_n_mg_per_kg
            / 1000.0
            / 1000.0
            * 10000
            * self.soil_layer_depth_cm
            / 100.0
            / 2
            * self.soil_bulk_density_kg_per_m3
            * self.crop_nitrogen_use_efficiency
        )  # convert mg/kg to kg/ha
        # mg/kg            => k/kg => kg/kg => kg/kg*ha => kg/kg*10000m3 => kg/kg*10000m3 *kg/m3 => kg/ha
        soil_p = (
            self.soil_available_p_mg_per_kg
            / 1000.0
            / 1000.0
            * 10000
            * self.soil_layer_depth_cm
            / 100.0
            / 2
            * self.soil_bulk_density_kg_per_m3
            * self.crop_porphorus_use_efficiency
        )
        soil_k = (
            self.soil_available_k_mg_per_kg
            / 1000.0
            / 1000.0
            * 10000
            * self.soil_layer_depth_cm
            / 100.0
            / 2
            * self.soil_bulk_density_kg_per_m3
            * self.crop_kassium_use_efficiency
        )

        # # Crop nutrient requirements per growth stage (hypothetical values)
        # nutrient_requirements = {
        #     "wheat": {
        #         "tillering": {"N": 60, "P": 30, "K": 40},
        #         "flowering": {"N": 80, "P": 40, "K": 60},
        #         # Add more stages as needed
        #     },
        #     # Add more crops as needed
        # }

        nutrient_requirements_nitrogen = crop_total_nitrogen_demand * self.ratio_nitrogen
        nutrient_requirements_porphorus = crop_total_porphorus_demand * self.ratio_porphorus
        nutrient_requirements_kassium = crop_total_kassium_demand * self.ratio_kassium

        # Residual nutrients from previous applications (hypothetical)
        # 基肥的话，残差肥料都是 0 ;
        residual_n = 0  # Residual Nitrogen
        residual_p = 0  # Residual Phosphorus
        residual_k = 0  # Residual Potassium

        # Calculate required fertilizers
        # required_n = nutrient_requirements[crop_type][crop_phenology]["N"] - (soil_n + residual_n)
        # required_p = nutrient_requirements[crop_type][crop_phenology]["P"] - (soil_p + residual_p)
        # required_k = nutrient_requirements[crop_type][crop_phenology]["K"] - (soil_k + residual_k)
        required_n = nutrient_requirements_nitrogen - (soil_n + residual_n)
        required_p = nutrient_requirements_porphorus - (soil_p + residual_p)
        required_k = nutrient_requirements_kassium - (soil_k + residual_k)

        # Ensure no negative values (i.e., no need to apply more than required)
        required_n = max(required_n, 0)
        required_p = max(required_p, 0)
        required_k = max(required_k, 0)

        # Log the required fertilizer amounts
        # logging.info(f"Fertilizer required: N={required_n} kg/ha, P={required_p} kg/ha, K={required_k} kg/ha")
        logging.info(
            f"Fertilizer required: N={required_n:.2f} kg/ha, P={required_p:.2f} kg/ha, K={required_k:.2f} kg/ha"
        )

        # 如果是混合肥，根据 NPK 比例计算施肥量
        if self.fertilizer_form == "mixed":
            ratio_n, ratio_p, ratio_k = self.fertilizer_npk_ratio

            # 计算最小的混合肥用量（基于三者的比例）
            required_fertilizer_n = required_n / (ratio_n / 100)
            required_fertilizer_p = required_p / (ratio_p / 100)
            required_fertilizer_k = required_k / (ratio_k / 100)

            # 所需的混合肥总量是确保所有需求得到满足的最小量
            min_fertilizer_amount = max(
                required_fertilizer_n, required_fertilizer_p, required_fertilizer_k
            )

            # 根据 zone_indexes 计算施肥量
            # 假设 NDVI 越高，肥料需求越少，使用 (1 - NDVI) 调节施肥量
            fertilizer_values = []
            # for index, zone_ndvi in enumerate(self.zone_indexes):
            for (
                index,
                zone_ndvi,
            ) in zone_indexes.items():  # 使用 .items() 来获取键和值
                zone_fertilizer_amount = min_fertilizer_amount * (
                    1 - zone_ndvi
                )  # 根据 NDVI 调整施肥量
                zone_fertilizer_amount = float(math.ceil(zone_fertilizer_amount))
                fertilizer_values.append(zone_fertilizer_amount)
                logging.info(
                    f"Fertilizer required for zone {index + 1} (NDVI={zone_ndvi}): {zone_fertilizer_amount:.2f} kg/ha"
                )
            fertilizer_values.sort()
            return fertilizer_values

        else:
            raise ValueError("Currently only mixed fertilizer is supported.")

        # if fertilizer_form == "mixed_fertilizer":
        #     # 如果是混合肥，根据NPK比例计算所需混合肥的最小量
        #     fertilizer_npk_ratio = self.dpm_settings.get("fertilizer_npk_ratio", [15, 15, 15])
        #     ratio_n, ratio_p, ratio_k = fertilizer_npk_ratio

        #     # 计算最小的混合肥用量（基于三者的比例）
        #     required_fertilizer_n = required_n / (ratio_n / 100)
        #     required_fertilizer_p = required_p / (ratio_p / 100)
        #     required_fertilizer_k = required_k / (ratio_k / 100)

        #     # 所需的混合肥总量是确保所有需求得到满足的最小量
        #     min_fertilizer_amount = max(required_fertilizer_n, required_fertilizer_p, required_fertilizer_k)

        #     # 输出施肥量
        #     logging.info(f"Mixed fertilizer required: {min_fertilizer_amount:.2f} kg/ha")
        #     return {"Mixed Fertilizer": min_fertilizer_amount}

        # elif fertilizer_form == "single_fertilizer":
        #     # 如果是单质肥，返回每种单质肥的量
        #     logging.info(f"Single fertilizers required: N={required_n:.2f} kg/ha, P={required_p:.2f} kg/ha, K={required_k:.2f} kg/ha")
        #     return {"N": required_n, "P": required_p, "K": required_k}

        # else:
        #     raise ValueError("Unknown fertilizer form specified in dpm_settings")

    # 依据养分平衡方程，判断追肥的施肥量
    # def nutrients_balance_calculation_follow_fertilization(self):

    def get_zone_indexes(self, geotiff_file, shp_file):
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


# # 示例使用
# if __name__ == "__main__":
#     spray = Spraying(
#         pesticide_type="insecticide",
#         pest_risk_level="high",
#         geotiff_file="pest_risk.tif",
#         shp_file="zones.shp"
#     )
#     prescription = spray.generate_spraying_map()
#     print("灌溉处方图:", Irrigation)