import logging
import geopandas as gpd

def valued_dpm_shp_postpro(valued_shp_file,average_value):
    # 2025-2-1 07:53:52 long.liu89@hotmail.com
    # 依据赋值后的shp计算变量处方的总施肥量；
    # 1. 计算shp中每个polygon的面积以及施肥量，对其进行加和，得到变量施肥的总施量；
    # 2. 计算shp中每个polygon的面积，进行加和,再乘以单位面积上的施肥量，该值由 self.average_fertilization_value 来计算，得到匀量施肥的总施肥量；
    # 3. 基于变量施肥的总施肥量以及匀量施肥的总施肥量，得到节肥率；
    # 计算变量施肥总施量和总面积

    """直接根据属性表中的 value 字段计算施肥总量和节肥率"""
    try:
        # 1. 读取处方图 Shapefile
        gdf = gpd.read_file(valued_shp_file)

        # 2. 校验必要字段存在
        required_fields = ["value", "area"]
        for field in required_fields:
            if field not in gdf.columns:
                raise KeyError(f"Shapefile 缺少必要字段: {field}")

        # 3. 计算变量施肥总施量
        variable_total = 0.0
        total_area = 0.0

        for _, row in gdf.iterrows():
            value = row["value"]  # 单位面积施肥量（kg/ha）
            area = row["area"]  # 面积（公顷）

            # 数值有效性检查
            if not (isinstance(value, (int, float)) and isinstance(area, (int, float))):
                raise ValueError("字段 value 或 area 包含非数值类型")

            variable_total += value * area
            total_area += area

        # 4. 计算匀量施肥总施量（需确保类中已定义 self.average_fertilization_value）
        uniform_total = total_area * average_value

        # 5. 计算节肥率（避免除零错误）
        saving_rate = 0.0
        if uniform_total > 0:
            saving_rate = (1 - variable_total / uniform_total) * 100

        # 保存结果并保留两位小数
        variable_total = round(variable_total, 2)
        uniform_total = round(uniform_total, 2)
        saving_rate = round(saving_rate, 2)

        # 输出日志
        logging.info(
            f"变量施肥总量: {variable_total} kg\n"
            f"匀量施肥总量: {uniform_total} kg\n"
            f"节肥率: {saving_rate}%"
        )
        return variable_total,uniform_total,saving_rate
    except Exception as e:
        logging.error(f"计算施肥量失败: {str(e)}")
        raise
