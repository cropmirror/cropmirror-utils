from osgeo import gdal, osr, ogr
import os
from shapely.geometry import Polygon, mapping
import numpy as np
import cv2
import matplotlib
import matplotlib.pyplot as plt

# 设置全局字体为支持中文的字体
matplotlib.rcParams['font.family'] = 'sans-serif'  # 使用无衬线字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # Windows 系统常用黑体
# 解决负号显示问题
matplotlib.rcParams['axes.unicode_minus'] = False

def analyze_geotiff_crs(tiff_path):
    """
    分析GeoTIFF文件的坐标参考系统(CRS)信息
    
    参数:
        tiff_path (str): GeoTIFF文件的路径
    
    返回:
        dict: 包含坐标系统信息的字典，格式如下：
            {
                'has_crs': bool,  # 是否有坐标系统
                'epsg': int,      # EPSG代码（如果没有则为None）
                'crs_type': str,  # 坐标系统类型：'geographic', 'projected', 或 'unknown'
                'crs_name': str,  # 坐标系统名称
                'units': str      # 单位（度或米）
            }
    """
    # 检查文件是否存在
    if not os.path.exists(tiff_path):
        raise FileNotFoundError(f"找不到文件: {tiff_path}")

    # 打开GeoTIFF文件
    dataset = gdal.Open(tiff_path)
    if dataset is None:
        raise ValueError(f"无法打开文件: {tiff_path}")

    # 获取空间参考信息
    proj = dataset.GetProjection()
    srs = osr.SpatialReference(wkt=proj)
    
    # 初始化返回结果
    result = {
        'has_crs': False,
        'epsg': None,
        'crs_type': 'unknown',
        'crs_name': 'undefined',
        'units': 'unknown'
    }
    
    # 检查是否有坐标系统
    if not proj:
        print(f"警告: {tiff_path} 没有定义坐标系统")
        return result
    
    result['has_crs'] = True
    
    # 获取EPSG代码
    srs.AutoIdentifyEPSG()
    epsg = srs.GetAuthorityCode(None)
    if epsg:
        result['epsg'] = int(epsg)
    
    # 判断坐标系类型
    if srs.IsGeographic():
        result['crs_type'] = 'geographic'
        result['units'] = 'degrees'
    elif srs.IsProjected():
        result['crs_type'] = 'projected'
        result['units'] = 'meters'
    
    # 获取坐标系名称
    result['crs_name'] = srs.GetAttrValue('PROJCS') if srs.IsProjected() else srs.GetAttrValue('GEOGCS')
    
    # 关闭数据集
    dataset = None
    
    return result

def test_analyze_geotiff_crs():
    """
    测试函数，用于验证coordinate_system_analyzer的功能
    """
    # 测试文件路径
    test_file = "data/DJI_0075.TIF"
    
    try:
        result = analyze_geotiff_crs(test_file)
        print("\n测试结果:")
        print("-" * 50)
        print(f"文件: {test_file}")
        print(f"是否有坐标系统: {'是' if result['has_crs'] else '否'}")
        print(f"EPSG代码: {result['epsg']}")
        print(f"坐标系类型: {result['crs_type']}")
        print(f"坐标系名称: {result['crs_name']}")
        print(f"单位: {result['units']}")
        print("-" * 50)
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")

def get_utm_epsg(lon, lat):
    """
    根据经纬度确定合适的UTM投影EPSG代码
    
    参数:
        lon (float): 经度
        lat (float): 纬度
    
    返回:
        int: UTM投影的EPSG代码
    """
    # 确定UTM带号
    zone = int((lon + 180) / 6) + 1
    
    # 确定半球
    if lat >= 0:
        # 北半球
        epsg = 32600 + zone
    else:
        # 南半球
        epsg = 32700 + zone
    
    return epsg

def get_geotiff_center(dataset):
    """
    获取GeoTIFF影像的中心点坐标
    
    参数:
        dataset: GDAL数据集对象
    
    返回:
        tuple: (lon, lat) 中心点的经纬度坐标
    """
    # 获取地理变换参数
    gt = dataset.GetGeoTransform()
    
    # 获取影像大小
    width = dataset.RasterXSize
    height = dataset.RasterYSize
    
    # 计算中心点像素坐标
    center_x = width / 2
    center_y = height / 2
    
    # 转换为投影坐标
    center_proj_x = gt[0] + center_x * gt[1] + center_y * gt[2]
    center_proj_y = gt[3] + center_x * gt[4] + center_y * gt[5]
    
    # 如果是投影坐标系，需要转换为地理坐标系
    srs = osr.SpatialReference(wkt=dataset.GetProjection())
    if srs.IsProjected():
        # 创建坐标转换
        target_srs = srs.CloneGeogCS()  # 获取对应的地理坐标系
        transform = osr.CoordinateTransformation(srs, target_srs)
        # 执行转换
        lon, lat, _ = transform.TransformPoint(center_proj_x, center_proj_y)
    else:
        lon, lat = center_proj_x, center_proj_y
    
    return lon, lat

def prepare_projected_geotiff(tiff_path):
    """
    准备投影坐标系的GeoTIFF文件
    如果输入是地理坐标系，则转换为适当的UTM投影
    如果已经是投影坐标系，则返回原始路径
    
    参数:
        tiff_path (str): 输入GeoTIFF文件路径
    
    返回:
        tuple: (输出文件路径, EPSG代码, 是否需要删除临时文件)
    """
    # 分析当前坐标系
    crs_info = analyze_geotiff_crs(tiff_path)
    
    # 如果已经是投影坐标系，直接返回
    if crs_info['crs_type'] == 'projected':
        return tiff_path, crs_info['epsg'], False
    
    # 打开数据集
    dataset = gdal.Open(tiff_path)
    if dataset is None:
        raise ValueError(f"无法打开文件: {tiff_path}")
    
    # 获取中心点坐标
    center_lon, center_lat = get_geotiff_center(dataset)
    
    # 确定合适的UTM投影
    target_epsg = get_utm_epsg(center_lon, center_lat)
    
    # 创建输出文件路径
    output_path = tiff_path.rsplit('.', 1)[0] + f'_utm{target_epsg}.tif'
    
    # 执行投影转换
    print(f"正在将文件从 {crs_info['crs_name']} 转换为 EPSG:{target_epsg}")
    gdal.Warp(output_path, 
              dataset, 
              dstSRS=f'EPSG:{target_epsg}',
              resampleAlg=gdal.GRA_Bilinear)
    
    # 关闭数据集
    dataset = None
    
    return output_path, target_epsg, True

def test_prepare_projected_geotiff():
    """
    测试坐标系转换功能
    """
    test_file = "data/img67.tif"
    
    try:
        output_path, target_epsg, needs_cleanup = prepare_projected_geotiff(test_file)
        print("\n转换结果:")
        print("-" * 50)
        print(f"输入文件: {test_file}")
        print(f"输出文件: {output_path}")
        print(f"目标EPSG: {target_epsg}")
        
        # 验证转换后的文件
        result = analyze_geotiff_crs(output_path)
        print("\n转换后的坐标系信息:")
        print(f"坐标系类型: {result['crs_type']}")
        print(f"EPSG代码: {result['epsg']}")
        print(f"坐标系名称: {result['crs_name']}")
        print(f"单位: {result['units']}")
        print("-" * 50)
        
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")

def extract_valid_area_polygon(dataset):
    """
    从GeoTIFF中提取有效像元区域的边界多边形
    """
    # 读取第一个波段数据
    band = dataset.GetRasterBand(1)
    
    # 读取数据到numpy数组
    data = band.ReadAsArray()
    
    # 创建掩膜（非NoData区域）
    nodata = band.GetNoDataValue()
    print(f"\n掩膜信息:")
    print(f"NoData值: {nodata}")
    
    if nodata is None:
        # 如果没有设置NoData值，尝试检测数据范围
        unique_values = np.unique(data)
        print(f"唯一值: {unique_values}")
        if 0 in unique_values:
            mask = (data != 0)
        else:
            # 如果没有0值，假设最小值为无效值
            mask = (data != data.min())
        print(f"使用默认方法创建掩膜")
    else:
        mask = (data != nodata)
        print(f"使用NoData值创建掩膜")
    
    print(f"有效像元数量: {np.sum(mask)}")
    print(f"总像元数量: {mask.size}")
    print(f"有效区域比例: {np.sum(mask) / mask.size * 100:.2f}%")
    
    # 获取地理变换参数
    gt = dataset.GetGeoTransform()
    
    # 获取像素大小
    pixel_width = abs(gt[1])
    pixel_height = abs(gt[5])
    
    # 使用OpenCV的轮廓查找
    mask_uint8 = mask.astype(np.uint8) * 255
    
    # 查找轮廓
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        raise ValueError("未找到有效区域边界")
    
    # 选择最大的轮廓
    main_contour = max(contours, key=cv2.contourArea)
    
    # 转换为投影坐标
    coords = []
    for point in main_contour.squeeze():
        x, y = point
        # 使用地理变换参数转换坐标
        proj_x = gt[0] + x * gt[1] + y * gt[2]
        proj_y = gt[3] + x * gt[4] + y * gt[5]
        coords.append((proj_x, proj_y))
    
    # 创建多边形并简化
    polygon = Polygon(coords)
    # 简化多边形，但保持形状特征（使用像素大小的2倍作为简化容差）
    simplified_polygon = polygon.simplify(tolerance=pixel_width * 2)
    
    print(f"\n边界提取信息:")
    print(f"原始边界点数量: {len(coords)}")
    print(f"简化后顶点数: {len(simplified_polygon.exterior.coords)}")
    print(f"像素大小: {pixel_width:.3f} x {pixel_height:.3f} 米")
    
    # 可视化
    plt.figure(figsize=(15, 15))
    
    # 显示原始影像
    rgb_data = None
    for i in range(min(3, dataset.RasterCount)):
        band = dataset.GetRasterBand(i + 1)
        if rgb_data is None:
            rgb_data = np.zeros((band.YSize, band.XSize, 3))
        # 归一化到0-1范围
        band_data = band.ReadAsArray().astype(float)
        valid_min = np.min(band_data[band_data > 0])
        valid_max = np.max(band_data)
        rgb_data[:,:,i] = np.clip((band_data - valid_min) / (valid_max - valid_min), 0, 1)
    
    plt.imshow(rgb_data)
    
    # 绘制边界
    boundary_coords = np.array(simplified_polygon.exterior.coords)
    # 转换回像素坐标
    pixel_coords = []
    for x, y in boundary_coords:
        # 反向转换投影坐标到像素坐标
        px = (x - gt[0]) / gt[1]
        py = (y - gt[3]) / gt[5]
        pixel_coords.append([px, py])
    pixel_coords = np.array(pixel_coords)
    
    plt.plot(pixel_coords[:,0], pixel_coords[:,1], 'r-', linewidth=2, label='提取的边界')
    plt.legend()
    plt.title('影像与提取边界叠加图')
    plt.show()
    
    return simplified_polygon

def calculate_valid_area(tiff_path):
    """
    计算GeoTIFF中有效像元区域的面积
    """
    # 分析原始文件的坐标系统
    print("\n原始文件坐标系统信息:")
    crs_info = analyze_geotiff_crs(tiff_path)
    print(f"坐标系类型: {crs_info['crs_type']}")
    print(f"EPSG代码: {crs_info['epsg']}")
    print(f"坐标系名称: {crs_info['crs_name']}")
    
    # 确保使用投影坐标系
    projected_path, epsg, needs_cleanup = prepare_projected_geotiff(tiff_path)
    
    try:
        # 打开投影后的文件
        dataset = gdal.Open(projected_path)
        if dataset is None:
            raise ValueError(f"无法打开文件: {projected_path}")
        
        print("\n投影后文件信息:")
        print(f"投影字符串:")
        print(dataset.GetProjection())
        
        # 提取有效区域多边形
        polygon = extract_valid_area_polygon(dataset)
        
        # 计算面积（平方米）
        area_m2 = polygon.area
        
        # 准备返回结果
        result = {
            'area_m2': area_m2,
            'area_ha': area_m2 / 10000,
            'area_km2': area_m2 / 1000000,
            'perimeter_m': polygon.length,
            'epsg': epsg,
            'polygon_wkt': polygon.wkt
        }
        
        # 关闭数据集
        dataset = None
        
        return result
        
    finally:
        if needs_cleanup and projected_path != tiff_path:
            try:
                os.remove(projected_path)
                print(f"\n已删除临时文件: {projected_path}")
            except Exception as e:
                print(f"清理临时文件时出错: {e}")

def save_boundary_vector(polygon_wkt, epsg, output_path, format='GeoJSON'):
    """
    保存边界多边形为矢量文件（GeoJSON或Shapefile）
    
    参数:
        polygon_wkt (str): 多边形的WKT表示
        epsg (int): 坐标系统的EPSG代码
        output_path (str): 输出文件路径
        format (str): 输出格式，'GeoJSON'或'ESRI Shapefile'
    """
    # 创建几何对象
    polygon = ogr.CreateGeometryFromWkt(polygon_wkt)
    
    # 创建空间参考系统
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    
    # 创建驱动
    driver = ogr.GetDriverByName(format)
    if driver is None:
        raise ValueError(f"不支持的格式: {format}")
    
    # 创建数据源
    ds = driver.CreateDataSource(output_path)
    if ds is None:
        raise ValueError(f"无法创建文件: {output_path}")
    
    # 创建图层
    layer = ds.CreateLayer('boundary', srs, geom_type=ogr.wkbPolygon)
    
    # 创建要素
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(polygon)
    layer.CreateFeature(feature)
    
    # 清理
    feature = None
    ds = None

def test_calculate_valid_area():
    """
    测试面积计算功能
    """
    # test_file = "data/img67.tif"
    # test_file = "data/rgb_orthophoto_2025_01_09_233741.tif"
    test_file = "data/rgb_orthophoto_2025_03_23_141925.tif"
    
    try:
        print(f"\n计算文件 {test_file} 的有效区域面积...")
        result = calculate_valid_area(test_file)
        
        print("\n计算结果:")
        print("-" * 50)
        print(f"面积: {result['area_m2']:.2f} 平方米")
        print(f"     {result['area_ha']:.2f} 公顷")
        print(f"     {result['area_km2']:.2f} 平方公里")
        print(f"周长: {result['perimeter_m']:.2f} 米")
        print(f"坐标系统: EPSG:{result['epsg']}")
        print("-" * 50)
        
        # 保存边界为GeoJSON
        geojson_path = test_file.rsplit('.', 1)[0] + '_boundary.geojson'
        save_boundary_vector(result['polygon_wkt'], 
                           result['epsg'], 
                           geojson_path, 
                           'GeoJSON')
        print(f"\n边界多边形已保存为GeoJSON: {geojson_path}")
        
        # 保存边界为Shapefile
        shp_path = test_file.rsplit('.', 1)[0] + '_boundary.shp'
        save_boundary_vector(result['polygon_wkt'], 
                           result['epsg'], 
                           shp_path, 
                           'ESRI Shapefile')
        print(f"边界多边形已保存为Shapefile: {shp_path}")
        
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")

if __name__ == "__main__":
    test_calculate_valid_area() 