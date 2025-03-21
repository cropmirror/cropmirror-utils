import logging
import geopandas as gpd
import json
import os

def shp2geojson(input_shp_file, output_geojson_file):
    # 检查输入文件是否存在
    if not os.path.exists(input_shp_file):
        logging.error("输入Shapefile文件不存在，请检查路径：%s", input_shp_file)
        raise

    try:
        # 读取shp文件
        gdf = gpd.read_file(input_shp_file)
    except Exception as e:
        logging.error("读取Shapefile文件失败：%s", e)
        raise

    # 显示shapefile当前的坐标系
    logging.info("当前的坐标系 (CRS)：%s", gdf.crs)

    # 将坐标系转换为WGS84
    gdf = gdf.to_crs(epsg=4326)

    gdf.to_file(output_geojson_file, driver="GeoJSON")

    logging.info("GeoJSON文件已保存：%s", output_geojson_file)

def check_shp_crs(shp_file):
    if not os.path.exists(shp_file):
        logging.error("输入Shapefile文件不存在，请检查路径：%s", shp_file)
        return None

    gdf = gpd.read_file(shp_file)
    crs = gdf.crs  # 获取CRS信息

    if crs:
        print(f"Shapefile CRS: {crs}")
    else:
        print("Shapefile不包含CRS信息。")
    return crs

def check_geojson_crs(geojson_file):
    # 检查GeoJSON文件是否存在
    if not os.path.exists(geojson_file):
        logging.error("GeoJSON文件不存在，请检查路径：%s", geojson_file)
        return

    # 读取 GeoJSON 文件
    with open(geojson_file) as f:
        data = json.load(f)

    # 检查是否有 CRS 信息
    if 'crs' in data:
        print("CRS Type:", data['crs']['type'])
        print("CRS Properties:", data['crs']['properties'])
    else:
        print("GeoJSON 文件中没有 CRS 信息。")

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(pathname)s %(lineno)d  %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")

    # 输入文件路径
    here = os.path.dirname(__file__)
    input_shp_file = os.path.join(here, "valued_dpm_shp_file.shp")
    output_geojson_file = os.path.join(here, "test.geojson")

    # 检查Shapefile的CRS
    check_shp_crs(input_shp_file)

    # 将Shapefile转换为GeoJSON
    shp2geojson(input_shp_file, output_geojson_file)

    # 检查GeoJSON文件的CRS
    check_geojson_crs(output_geojson_file)
