import json
import os
import geopandas as gpd
from osgeo import gdal, ogr, osr
import tempfile
import shutil
import time
import matplotlib.pyplot as plt
import logging
import datetime
from shapely.geometry import Point
from geopy.geocoders import Nominatim
import matplotlib.font_manager as fm
import numpy as np
import matplotlib.colors as colors

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(pathname)s %(lineno)d  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


here = os.path.dirname(__file__)
# geojsonfile = os.path.join(here, "prescription.geojson")
geojsonfile = os.path.join(here, "test.geojson")


# Convert GeoJSON to SHP
def convert_shp(
    data, output_dir, suffix=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
):
    filename = "%s.shp" % (suffix)
    savepath = os.path.join(output_dir, filename)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    gdf = gpd.GeoDataFrame.from_features(data["features"])

    # 检查 GeoDataFrame 是否有 CRS 信息
    if gdf.crs is None:
        logging.info("No CRS information found, setting CRS to WGS84 (EPSG:4326).")
        gdf.set_crs(epsg=4326, inplace=True)

    # 确保 CRS 已经被正确设置
    if gdf.crs is None or gdf.crs != "EPSG:4326":
        raise ValueError("Failed to set CRS to WGS84 (EPSG:4326).")

    gdf.to_file(savepath, driver="ESRI Shapefile")

    gdf_check = gpd.read_file(savepath)
    logging.info(f"Saved Shapefile CRS: {gdf_check.crs}")


# Convert GeoJSON to TIFF, 大疆植保机；tif, tfw; tif:; .clr;
def convert_tif(
    data, output_dir, dpm_res=4, suffix=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
):
    filename = "%s.tif" % (suffix)
    savepath = os.path.join(output_dir, filename)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    gdf = gpd.GeoDataFrame.from_features(data["features"])

    # 检查GeoDataFrame是否有CRS信息
    # if gdf.crs is None:
    #     logging.info("No CRS information found, setting CRS to WGS84 (EPSG:4326).")
    #     gdf.set_crs(epsg=4326, inplace=True)

    if "crs" not in data or data["crs"] is None or gdf.crs is None:
        logging.info("No CRS information found, setting CRS to WGS84 (EPSG:4326).")
        gdf.set_crs(epsg=4326, inplace=True)

    gdf.to_crs(epsg=4326, inplace=True)  # 确保CRS正确

    if "value" not in gdf.columns:
        raise ValueError(
            "The GeoDataFrame does not contain a 'value' column, which is required for rasterization."
        )

    # gdf['value'] = 1  # 设置用于栅格化的值，level, color;
    xmin, ymin, xmax, ymax = gdf.total_bounds
    # 计算中心纬度
    center_lat = (ymin + ymax) / 2

    # 计算栅格分辨率，目标为 4 米
    row_res = dpm_res / 111320  # 4 米转换为纬度单位
    col_res = dpm_res / (111320 * np.cos(np.radians(center_lat)))  # 4 米转换为经度单位

    cols = int((xmax - xmin) / col_res)
    rows = int((ymax - ymin) / row_res)

    # 创建临时文件夹
    temp_dir = tempfile.mkdtemp()
    try:
        # 保存矢量数据为临时Shapefile
        shp_path = os.path.join(temp_dir, "temp_shp.shp")
        gdf.to_file(shp_path, driver="ESRI Shapefile")

        # 确认文件是否成功创建
        if not os.path.exists(shp_path):
            raise FileNotFoundError(f"Temporary shapefile not found: {shp_path}")

        # 创建栅格数据集
        driver = gdal.GetDriverByName("GTiff")
        out_raster = driver.Create(savepath, cols, rows, 1, gdal.GDT_Float32)
        out_raster.SetGeoTransform((xmin, col_res, 0, ymax, 0, -row_res))

        # 设置投影信息为 WGS84 (EPSG:4326)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        out_raster.SetProjection(srs.ExportToWkt())

        outband = out_raster.GetRasterBand(1)

        # 使用 NaN 作为无数据值
        outband.SetNoDataValue(np.nan)

        # 查看文件夹中的文件列表，确保 Shapefile 相关文件都存在
        logging.info(f"Temporary directory contents: {os.listdir(temp_dir)}")

        # 使用 OGR 打开 Shapefile
        shp_ds = ogr.Open(shp_path)
        if shp_ds is None:
            raise RuntimeError(f"Failed to open shapefile: {shp_path}")

        # 获取矢量图层
        layer = shp_ds.GetLayer()

        # 使用临时矢量文件进行栅格化
        gdal.RasterizeLayer(out_raster, [1], layer, options=["ATTRIBUTE=value"])

        outband.FlushCache()

        # 显式释放数据源
        shp_ds = None

        # 保存颜色映射为 .clr 文件
        clr_path = os.path.splitext(savepath)[0] + ".clr"
        unique_values = gdf["value"].unique()
        num_colors = len(unique_values)

        # 使用 matplotlib 中的 ListedColormap 来生成有序的颜色映射
        cmap = plt.get_cmap(
            "viridis", num_colors
        )  # 选择一个有序的颜色映射（例如 viridis）

        # 将颜色映射保存到 .clr 文件
        with open(clr_path, "w") as f:
            for i, value in enumerate(unique_values):
                # # 为每个唯一值生成随机颜色
                # rgb = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                # f.write(f"{value} {rgb[0]} {rgb[1]} {rgb[2]}\n")
                # 获取颜色映射中的 RGB 值（在 0-1 范围内），然后转换到 0-255 范围
                r, g, b, _ = cmap(i / (num_colors - 1))  # RGBA 其中 A 忽略
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
                f.write(f"{value} {r} {g} {b}\n")

    finally:
        # 在删除临时文件夹之前等待一会
        time.sleep(1)
        # 删除临时文件夹
        shutil.rmtree(temp_dir)


# Convert GeoJSON to ISOXML version 4
from xml.etree.ElementTree import Element, SubElement, ElementTree
import struct
import zipfile
import os


def convert_isoxml_v4(data, output_dir, suffix=datetime.datetime.now().strftime("%Y%m%d%H%M%S")):
    # 创建目标文件夹（如果不存在）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 创建 XML 文件，文件名为 TASKDATA.XML
    xml_filename = "TASKDATA.XML"
    xml_path = os.path.join(output_dir, xml_filename)
    # 创建对应的 .bin 文件
    bin_filename = "TASKDATA.BIN"
    bin_path = os.path.join(output_dir, bin_filename)

    # 创建根节点 ISO11783_TaskData
    root = Element(
        "ISO11783_TaskData",
        {
            "VersionMajor": "2",
            "VersionMinor": "0",
            "ManagementSoftwareManufacturer": "CropMirror",
            "ManagementSoftwareVersion": "1.0",
            "TaskControllerVersion": "1.0",
            "DataTransferOrigin": "1",
        },
    )

    # 创建 TSK 节点 (Task)
    tsk = SubElement(
        root,
        "TSK",
        {
            "A": "TSK1",
            "B": "20240402104938_valued_dpm",  # 可以自定义任务名称
            "G": "1",
            "H": "1",
        },
    )

    # 创建 DLT 节点
    dlt = SubElement(tsk, "DLT", {"A": "DFFF", "B": "31", "D": "1000"})

    # 创建 GRD 节点 (Grid)
    grd = SubElement(
        tsk,
        "GRD",
        {
            "A": "37.06903967",
            "B": "115.26926947",
            "C": "0.00008730",
            "D": "0.00011239",
            "E": "13",
            "F": "22",
            "G": "GRD00000",
            "I": "2",
            "J": "2",
        },
    )

    # 添加 TreatmentZone 节点
    for i, feature in enumerate(data["features"]):
        tzn = SubElement(tsk, "TZN", {"A": str(i), "B": f"Zone_{i}", "C": "0"})

        # 添加 PDV 节点 (施肥量或其他参数)
        properties = feature.get("properties", {})
        value = properties.get("value", 0)  # 如果 GeoJSON 中存在 'value' 属性，则读取它
        pdv = SubElement(
            tzn,
            "PDV",
            {"A": "0006", "B": str(int(value))},  # 使用从 GeoJSON 中获取的 'value' 值
        )

    # 保存 XML 文件
    tree = ElementTree(root)
    with open(xml_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    with open(bin_path, "wb") as bin_file:
        for feature in data["features"]:
            properties = feature.get("properties", {})
            value = properties.get(
                "value", 0
            )  # 假设 value 是需要存储的值，如果不存在则为 0

            # 假设将 value 写入 .bin 文件，以 float 格式存储
            bin_file.write(struct.pack("<f", float(value)))

    # 创建 ZIP 压缩包
    # zip_path = os.path.join(output_dir, "ISOXML_Output.zip")
    # with zipfile.ZipFile(zip_path, 'w') as zipf:
    #     zipf.write(xml_path, xml_filename)
    #     zipf.write(bin_path, bin_filename)

    # logging.info(f"ISOXML and BIN files created and zipped: {zip_path}")


# Convert GeoJSON to ISOXML version 5
def convert_isoxml_v5(data, output_dir):
    filename = "%s.xml5" % (datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    savepath = os.path.join(output_dir, filename)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(savepath, "w") as f:
        f.write('<ISO11783_TaskData Version="5">\n')
        # Convert data['features'] to ISOXML format...
        f.write("</ISO11783_TaskData>")


def show_tif(tif_path):
    # 打开 TIFF 文件
    dataset = gdal.Open(tif_path)
    if dataset is None:
        raise FileNotFoundError(f"Failed to open TIFF file: {tif_path}")

    # 获取栅格数据
    band = dataset.GetRasterBand(1)
    array = band.ReadAsArray()

    # 自动生成 clr 文件路径
    clr_path = os.path.splitext(tif_path)[0] + ".clr"

    # 读取颜色映射文件，如果提供了 .clr 文件
    if os.path.exists(clr_path):
        # 创建颜色字典来保存栅格值与对应的 RGB 颜色
        value_to_color = {}
        with open(clr_path, "r") as clr_file:
            for line in clr_file:
                if line.strip():
                    parts = line.split()
                    value = float(parts[0])
                    rgb = tuple(map(int, parts[1:4]))
                    value_to_color[value] = rgb

        # 创建一个与栅格大小相同的 RGB 图像数组
        rgb_image = np.zeros((array.shape[0], array.shape[1], 3), dtype=np.uint8)

        # 将每个栅格值映射到对应的 RGB 颜色
        for value, color in value_to_color.items():
            mask = array == value
            rgb_image[mask] = color

        # 显示 RGB 图像
        plt.imshow(rgb_image)
    else:
        # 使用默认的 viridis 颜色映射进行显示
        plt.imshow(array, cmap="viridis")

    plt.title("TIFF Visualization")
    plt.colorbar()
    plt.show()
    logging.info("TIFF visualization completed.")


def get_administrative_area(lat, lon):
    geolocator = Nominatim(user_agent="geo_shapefile_viewer")
    location = geolocator.reverse((lat, lon), language="zh")
    if location and location.raw.get("address"):
        address = location.raw["address"]
        admin_area = f"{address.get('state', '')} {address.get('county', '')} {address.get('town', '')}"
        return admin_area.strip()
    else:
        return "Unknown Location"


def show_shp(shp_path):
    # 读取 Shapefile
    gdf = gpd.read_file(shp_path)

    # 获取 Shapefile 的几何中心点
    centroid = gdf.geometry.centroid.unary_union.centroid
    if isinstance(centroid, Point):
        lon, lat = centroid.x, centroid.y
        # 使用逆地理编码查找行政区名称
        admin_area = get_administrative_area(lat, lon)
    else:
        admin_area = "Unknown Location"

    # 检查是否存在 'value' 列
    if "value" not in gdf.columns:
        logging.warning("'value' column not found in Shapefile. Using default colors.")
        gdf.plot()
    else:
        # 显示 Shapefile，根据 'value' 列设置不同的颜色
        gdf.plot(column="value", legend=True, cmap="viridis")

    # 设置中文字体
    plt.rcParams["font.sans-serif"] = ["SimHei"]  # 用黑体显示中文
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号

    plt.title(f"Shapefile Visualization - {admin_area}")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.show()
    logging.info("Shapefile visualization completed.")


if __name__ == "__main__":

    current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    shp_path = os.path.join(here, f"{current_timestamp}_shp")
    tif_path = os.path.join(here, f"{current_timestamp}_tif")
    # xml_v4_path = os.path.join(here, f"{current_timestamp}_tmp_v4.xml")
    xml_v4_path = os.path.join(here, f"{current_timestamp}_xml_v4")
    # xml_v5_path = os.path.join(here, f"{current_timestamp}_tmp_v5.xml")
    xml_v5_path = os.path.join(here, f"{current_timestamp}_xml_v5")

    # Read GeoJSON file
    with open(geojsonfile) as f:
        data = json.load(f)  # Load file content into data

    # Check if CRS information is available
    if "crs" in data:
        logging.info("CRS Type: %s", data["crs"]["type"])
        logging.info("CRS Properties: %s", data["crs"]["properties"])
    else:
        logging.info("No CRS information available in this GeoJSON.")

    logging.info(data["type"])

    # Convert to SHP
    convert_shp(data, shp_path)

    # 添加 shp 可视化的代码

    # 显示 Shapefile
    # show_shp(shp_path)

    # # Convert to TIFF
    convert_tif(data, tif_path, dpm_res=4)

    # # 添加显示 tmp.tif 的代码；
    # show_tif(tif_path)

    # # Convert to ISOXML v4
    convert_isoxml_v4(
        data, xml_v4_path
    )  # 这传入的应该是个文件夹路径，然后在这个文件夹下面生成 TASKDATA.xml 和 TASKDATA.bin

    # # Convert to ISOXML v5
    # convert_isoxml_v5(data, xml_v5_path)
