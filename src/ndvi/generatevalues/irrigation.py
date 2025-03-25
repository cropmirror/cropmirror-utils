
import logging
import math

from .common import get_zone_indexes
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

