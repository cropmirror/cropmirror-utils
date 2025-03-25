import logging
import rasterio
from scipy.ndimage import gaussian_filter
import numpy as np
import os

from osgeo import gdal, ogr, osr

def reclassify(geotiff_filepath, reclassify_filepath, level_num: int = 5):
    """
    使用自然间断点方法，将裁剪后的geotiff进行分级, 生成reclassify file
    参数:
    geotiff_filepath: 原始geotiff 文件
    reclassify_filepath (str): 分级后的geotiff保存文件名
    num (int): 分级数目
    """

    # 读取裁剪后的geotiff文件
    with rasterio.open(geotiff_filepath) as src:
        ndvi = src.read(1)
        profile = src.profile

    gaussian_ndvi = gaussian_filter(
        ndvi, sigma=3
    )  # Apply Gaussian filter for density estimation

    logging.info(np.nanmin(gaussian_ndvi))
    logging.info(np.nanmax(gaussian_ndvi))
    # 计算自然间断点

    # todo
    breaks = np.linspace(
        np.nanmin(gaussian_ndvi), np.nanmax(gaussian_ndvi), int(level_num)
    )

    # 重新分类数据
    reclassified_data = np.digitize(gaussian_ndvi, breaks)

    # 更新profile信息
    profile.update(count=1)

    # 保存重新分类后的geotiff文件
    with rasterio.open(reclassify_filepath, "w", **profile) as dst:
        dst.write(reclassified_data, 1)

    logging.info(
        f"已成功将{geotiff_filepath}文件重新分类为 {level_num} 级: {reclassify_filepath}"
    )

def raster2vector(reclassfy_filepath,shp_filepath):

    # path_split = os.path.split(raster_path)
    # file_split = path_split[-1].split('.')
    # vector_path = path_split[0] + '/' + file_split[0] + '.shp'
    """栅格转矢量"""
    # 打开栅格数据
    raster = gdal.Open(reclassfy_filepath)
    band = raster.GetRasterBand(1)

    # 获取投影信息
    proj = raster.GetProjection()
    # geotransform = raster.GetGeoTransform()

    # 创建空间参考
    spatial_ref = osr.SpatialReference()
    spatial_ref.ImportFromWkt(proj)

    # 创建Shapefile
    driver = ogr.GetDriverByName("ESRI Shapefile")
    shp = driver.CreateDataSource(shp_filepath)
    # 使用与 dpm_shp_filepath 同名的图层名称
    layer_name = os.path.splitext(os.path.basename(shp_filepath))[0]
    # 创建图层，并设置空间参考
    layer = shp.CreateLayer(layer_name, srs=spatial_ref, geom_type=ogr.wkbPolygon)

    # 添加字段
    field_name = ogr.FieldDefn("value", ogr.OFTInteger)
    layer.CreateField(field_name)

    # 矢量化
    band.SetNoDataValue(0)
    mask_band = band.GetMaskBand()
    gdal.Polygonize(
        band, maskBand=mask_band, outLayer=layer, iPixValField=0, callback=None
    )

    # # 创建空间参考（设置 CRS）
    # spatial_ref = osr.SpatialReference()
    # spatial_ref.ImportFromWkt(proj)
    # layer_definition = layer.GetLayerDefn()
    # layer.SetSpatialRef(spatial_ref)

    # 确认 CRS 信息是否存在
    if layer.GetSpatialRef() is not None:
        print("CRS information has been successfully set.")
        print(layer.GetSpatialRef().ExportToWkt())
    else:
        print("No CRS information found in the layer.")

    # # 添加空间参考
    # spatial_ref = osr.SpatialReference(wkt=proj)
    # layer.SetSpatialFilter(spatial_ref)

    # # 添加几何变换参数
    # layer.SetGeoTransform(geotransform)

    # 关闭数据集
    raster = None
    shp = None
