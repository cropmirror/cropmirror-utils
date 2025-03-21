import geopandas as gpd
from math import sqrt
from shapely import wkt
from shapely.geometry import mapping
import geojson
import json
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection
from shapely.geometry import shape
def generate_polygon(center_lat, center_lon, distance=805, cap_style="round"):
    gs = gpd.GeoSeries(wkt.loads(f"POINT ({center_lon} {center_lat})"))
    gdf = gpd.GeoDataFrame(geometry=gs)
    gdf.crs = "EPSG:4326"
    gdf = gdf.to_crs("EPSG:3857")
    res = gdf.buffer(
        distance=distance,
        cap_style=cap_style,
    )
    geojson_string = geojson.dumps(
        mapping(wkt.loads(res.to_crs("EPSG:4326").iloc[0].wkt))
    )

    
    geojson_dict = json.loads(geojson_string)
    
    polygon = shape(geojson_dict)
    gdf = gpd.GeoDataFrame(index=[0], crs='epsg:4326', geometry=[polygon])
    area = gdf.to_crs(32649).area.iloc[0] /1000000
    print(area)
    return geojson_dict

from shapely.geometry import box
from geopy.distance import geodesic
import json

def generate_rectangle(center_lat, center_lon, width_m, height_m):
    # 计算矩形宽度和高度对应的纬度和经度变化量
    half_width_delta = geodesic(meters=width_m / 2).destination((center_lat, center_lon), bearing=90).longitude - center_lon
    half_height_delta = geodesic(meters=height_m / 2).destination((center_lat, center_lon), bearing=0).latitude - center_lat

    # 计算矩形的边界坐标
    minx = center_lon - half_width_delta
    maxx = center_lon + half_width_delta
    miny = center_lat - half_height_delta
    maxy = center_lat + half_height_delta

    # 使用 box 函数生成矩形
    rectangle = box(minx, miny, maxx, maxy)
    
    # 将 Polygon 对象转换为 GeoJSON 格式
    rectangle_geojson = {
        "type": "Polygon",
        "coordinates": [list(rectangle.exterior.coords)]
    }
    
    return rectangle_geojson

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

def clip_shp_by_polygon(input_shp, clip_polygon_json, output_shp):
    # 读取待裁剪的shp文件
    to_be_clipped = gpd.read_file(input_shp)

    # 定义裁剪用的多边形
    polygon_coords = clip_polygon_json["coordinates"][0]
    clipping_polygon = Polygon(polygon_coords)

    # 确保多边形和shp文件在同一坐标参考系统（CRS）
    # 如果CRS不同，需要进行转换
    if to_be_clipped.crs != "EPSG:4326":
        clipping_polygon = gpd.GeoSeries([clipping_polygon], crs="EPSG:4326")
        clipping_polygon = clipping_polygon.to_crs(to_be_clipped.crs).iloc[0]

    # 裁剪操作
    clipped = to_be_clipped.clip(clipping_polygon)

    # 处理不同的几何类型
    valid_geometries = []
    valid_records = []

    for idx, geom in enumerate(clipped.geometry):
        if geom.geom_type == "Polygon":
            valid_geometries.append(geom)
            valid_records.append(clipped.iloc[idx])
        elif geom.geom_type == "MultiPolygon":
            # 使用 .geoms 属性来遍历 MultiPolygon 中的每个 Polygon
            for poly in geom.geoms:
                valid_geometries.append(poly)
                valid_records.append(clipped.iloc[idx])
        elif geom.geom_type == "GeometryCollection":
            # 从 GeometryCollection 中提取多边形
            for sub_geom in geom.geoms:
                if sub_geom.geom_type == "Polygon":
                    valid_geometries.append(sub_geom)
                    valid_records.append(clipped.iloc[idx])

    # 使用有效的几何和属性构建新的 GeoDataFrame
    valid_df = gpd.GeoDataFrame(valid_records, geometry=valid_geometries, crs=to_be_clipped.crs)

    # 检查是否为空，避免保存空文件
    if valid_df.empty:
        print("The clipped result is empty. No output file will be created.")
    else:
        # 保存裁剪后的shp文件
        valid_df.to_file(output_shp)
    
def clip_shp_by_shp(input_shp, clip_shp, output_shp):
    """
    使用一个 shp 文件裁剪另一个 shp 文件

    参数:
    input_shp (str): 输入的 shp 文件路径
    clip_shp (str): 用来裁剪的 shp 文件路径
    output_shp (str): 输出的裁剪后的 shp 文件路径
    """
    # 读取输入的 shp 文件和用来裁剪的 shp 文件
    input_gdf = gpd.read_file(input_shp)

    clip_gdf = gpd.read_file(clip_shp)

    # 进行空间裁剪
    clipped_gdf = gpd.overlay(input_gdf, clip_gdf, how="intersection")

    # 将裁剪后的结果保存为新的 shp 文件
    clipped_gdf.to_file(output_shp)
    
if __name__ == "__main__":
    generate_polygon(center_lat=47.287796,center_lon=132.690268,distance=805)