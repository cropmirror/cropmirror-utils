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


if __name__ == "__main__":
    generate_polygon(center_lat=47.287796,center_lon=132.690268,distance=805)