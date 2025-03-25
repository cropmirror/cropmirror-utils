
# 创建class Spraying
# long.liu89@hotmail.com
# 2025-2-2 10:47:34
import logging
import math
import rasterio
import geopandas as gpd
from rasterstats import zonal_stats

class Spraying:
    # 作物类型与耐药性系数（假设值，需根据实际数据调整）
    crop_resistance = {
        "wheat": 0.8,    # 小麦耐药性较高
        "maize": 0.6,    # 玉米耐药性中等
    }
    # 农药类型与推荐剂量（单位：g/ha，示例数据）
    pesticide_dose = {
        "insecticide": {"min": 200, "max": 400},  # 杀虫剂
        "fungicide": {"min": 150, "max": 300},    # 杀菌剂
        "herbicide": {"min": 100, "max": 250},    # 除草剂
    }
    # 病虫害风险等级与剂量调整系数（假设逻辑）
    risk_adjustment = {
        "low": 0.5,     # 低风险减少剂量
        "medium": 1.0,  # 中风险标准剂量
        "high": 1.5,    # 高风险增加剂量
    }

    def __init__(
        self,
        # --- 农药相关参数 ---
        pesticide_type="fungicide",  # 农药类型
        pesticide_concentration=50,    # 有效成分浓度（%）
        # recommended_dose=300,          # 推荐剂量（g/ha）
        recommended_dose = 2,       #推荐剂量 (L/mu),mu: 亩
        pest_risk_level="medium",      # 病虫害风险等级
        
        # --- 作物相关参数 ---
        crop_type="maize",
        crop_phenology="tasseling_maize",  # 作物生育期，作物生育期影响着抗性
        
        # --- 环境参数 ---
        weather_precipitation=0.0,     # 未来24小时降雨量（mm）
        weather_temperature=25.0,      # 当前温度（℃）
        
        # --- 地理数据参数 ---
        # geotiff_file=None,             # 遥感数据文件（如病虫害风险图）
        # shp_file=None,                 # 分区形状文件
    ) -> None:
        
        # --- 农药参数初始化 ---
        self.pesticide_type = pesticide_type
        self.pesticide_concentration = pesticide_concentration
        self.recommended_dose = recommended_dose
        self.pest_risk_level = pest_risk_level
        
        # --- 作物参数初始化 ---
        self.crop_type = crop_type
        self.crop_phenology = crop_phenology
        self.crop_resistance = self.crop_resistance.get(crop_type, 1.0)
        
        # --- 环境参数初始化 ---
        self.weather_precipitation = weather_precipitation
        self.weather_temperature = weather_temperature
        
        # # --- 地理数据处理 ---
        # self.geotiff_file = geotiff_file
        # self.shp_file = shp_file

    # 目前传过来的是NDVI，其实后面要改成用 raw_geotiff_file 来搞；
    def risk_based_pesticide_spraying(self, ndvi_geotiff_file, valued_shp_file, recommended_dose):

        # 读入 ndvi_geotiff_file

        # 将 zone_shp_file 和 ndvi_geotiff_file 进行匹配，得到每个 zone 的 NDVI 值
        
        # 将 NDVI 转化为 risk level

        # 根据 risk level 以及天气条件计算实际农药用量

        zone_indexes = self.get_zone_indexes(ndvi_geotiff_file,valued_shp_file)
        #
        pesticide_dose_values = []
        # for index, zone_ndvi in enumerate(self.zone_indexes):
        for (
            index,
            zone_ndvi,
        ) in zone_indexes.items():  # 使用 .items() 来获取键和值
            zone_pesticide_dose = recommended_dose * (
                1 - zone_ndvi
            )  
            # 根据 NDVI 调整施药量
            # if zone_ndvi < 0.3:
            #     zone_pesticide_dose *= 1.5
            # elif zone_ndvi >= 0.3 and zone_ndvi < 0.6:
            #     zone_pesticide_dose *= 1.0
            # elif zone_ndvi >= 0.6:
            #     zone_pesticide_dose *= 0.5

            zone_pesticide_dose = float(math.ceil(zone_pesticide_dose*100.0)/100.0)
            pesticide_dose_values.append(zone_pesticide_dose)
            logging.info(
                f"Pesticide required for zone {index + 1} (NDVI={zone_ndvi}): {zone_pesticide_dose:.2f} L/mu"
            )

        pesticide_dose_values.sort()
        return pesticide_dose_values, recommended_dose
    
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

    def calculate_pesticide_amount(self):
        """
        根据病虫害风险等级、作物耐药性和天气条件计算实际农药用量。
        返回：
        农药用量（g/ha）
        """
        # 基础剂量调整
        base_dose = self.recommended_dose * self.risk_adjustment.get(self.pest_risk_level, 1.0)
        
        # 根据作物耐药性调整
        adjusted_dose = base_dose / self.crop_resistance
        
        # 根据天气调整（降雨可能降低药效）
        if self.weather_precipitation > 10:
            adjusted_dose *= 1.2  # 降雨量大则增加10%剂量
        elif self.weather_temperature > 30:
            adjusted_dose *= 0.9  # 高温减少剂量
        
        # 确保在农药类型的安全范围内
        dose_range = self.pesticide_dose.get(self.pesticide_type, {"min": 0, "max": 0})
        final_dose = max(dose_range["min"], min(adjusted_dose, dose_range["max"]))
        
        return round(final_dose, 2)

    def generate_spraying_map(self):
        """
        根据分区地理数据生成差异化喷洒处方图。
        返回：
        各区域的农药用量字典 {zone_id: dose_g_per_ha}
        """
        if not self.geotiff_file or not self.shp_file:
            raise ValueError("GeoTIFF或SHP文件未提供")
        
        zone_risk = self.get_zone_risk_indexes(self.geotiff_file, self.shp_file)
        spraying_map = {}
        
        for zone_id, risk_value in zone_risk.items():
            # 假设risk_value是0-1的病虫害风险值
            if risk_value < 0.3:
                self.pest_risk_level = "low"
            elif risk_value < 0.7:
                self.pest_risk_level = "medium"
            else:
                self.pest_risk_level = "high"
            
            dose = self.calculate_pesticide_amount()
            spraying_map[zone_id] = dose
        
        return spraying_map

    def get_zone_risk_indexes(self, geotiff_file, shp_file):
        """
        从GeoTIFF中提取各分区的病虫害风险指数。
        """
        try:
            zones_gdf = gpd.read_file(shp_file)
            if "value" not in zones_gdf.columns:
                raise ValueError("Shapefile缺少'value'字段")
            
            with rasterio.open(geotiff_file) as src:
                raster = src.read(1)
                affine = src.transform
            
            zone_stats = zonal_stats(
                zones_gdf,
                raster,
                affine=affine,
                stats=["mean"],
                nodata=src.nodata
            )
            
            risk_indexes = {
                row["value"]: stats["mean"] if stats["mean"] else 0
                for row, stats in zip(zones_gdf.to_dict("records"), zone_stats)
            }
            
            return risk_indexes
        
        except Exception as e:
            raise Exception(f"风险指数计算失败: {e}")
