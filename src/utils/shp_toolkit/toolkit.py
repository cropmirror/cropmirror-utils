from fiona.crs import from_epsg
import geopandas as gpd

from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

class ShpToolkit():
    def __init__(self, shp_filepath):

        self._gdf = gpd.read_file(shp_filepath)
        pass

    def insert_attributes(
        self,
        colors: list = [
            "#D2DE6A",
            "#F1F143",
            "#C3E910",
            "#53E41D",
            "#1FB50D",
            "#227329",
            "#165B1B",
            "#011006",
        ],
        values: list=None,
        sorted_by: str ="value",
        desc: bool = True,
    ):
        """
        给定一个shp文件，给定三个值，将shp文件中的属性值进行分类
        参数:
        input_dpm_shp_file (str): 输入的shp文件名
        output_valued_dpm_shp_file (str): 输出的赋值后的dpm的shp文件名
        """

        # 获取value列中从大到小的五个不重复数
        sorted_values = self._gdf[sorted_by].unique()
        sorted_values.sort()  # 按值排序
    
        # 处方图 倒序
        if desc:
            sorted_values = sorted_values[::-1]  # 从大到小排序

        def level_mapper(val):
            return sorted_values.tolist().index(val) + 1

        def color_mapper(val):
            index = sorted_values.tolist().index(val)
            if index >= len(colors):
                return colors[-1]
            return colors[index]

        def value_mapper(val):
            return values[sorted_values.tolist().index(val)]

        # 将颜色信息添加到GeoDataFrame中
        self._gdf["color"] = self._gdf[sorted_by].apply(color_mapper)
        self._gdf["level"] = self._gdf[sorted_by].apply(level_mapper)

        # value 转换为指定的施肥量
        if values :
            self._gdf["value"] = self._gdf[sorted_by].apply(value_mapper)
        # gdf["color"] = np.select(conditions, choice_colors, default=colors[0])
        # Check if CRS is missing (None)
        # long.liu89@hotmail.com 2024-5-9 14:24:08
        epsg = 4326
        if self._gdf.crs is None:
            # Assign a default CRS (e.g., EPSG:4326)
            self._gdf.crs = from_epsg(epsg)  # Assign EPSG code to the CRS

            # # Generate new filename based on the original shapefile path
            # path, filename = os.path.split()
            # filename_no_ext, ext = os.path.splitext(filename)
            # new_filename = os.path.join(path, f"{filename_no_ext}_{epsg}{ext}")

            # Save the GeoDataFrame to the new shapefile path

            # 保存分类后的shp文件
        self._gdf["area"] = round(self._gdf.to_crs(32649).area / 10000, 6)
        self._gdf["area_total"] = self._gdf["area"]
        self._gdf["area_unit"] = "ha"
        # grouped_areas = round(gdf.groupby('level').area.sum(),6)
        # # for geometry_type, area in grouped_areas.items():
        # #     print(f"level: {geometry_type}, Total Area (m²): {area}")
        # for geometry_type, area in grouped_areas.items():
        #     gdf.loc[gdf['level'] == geometry_type, 'area_total'] = area

        self._gdf = self._gdf.dissolve(
            by="level",
            aggfunc={
                "color": "first",
                "value": "first",
                "area": "sum",
                "area_unit": "first",
                "area_total": "sum",
            },
        )

        # gdf.to_file(self._valued_shp_file)
        # gdf.to_file(self._geojson_file, driver="GeoJSON")

    def save(self, filename,driver=None):
        self._gdf.to_file(filename=filename,driver=driver)


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
    