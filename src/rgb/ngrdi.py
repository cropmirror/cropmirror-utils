import cv2
import numpy as np
import matplotlib.pyplot as plt
# from skimage.feature import graycomatrix, graycoprops
from osgeo import gdal
# import os
# import subprocess

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

def process_ngrdi(image_path):
    """处理叶片图像并提取掩码
    
    Args:
        image_path: 图像路径
        show_visualization: 是否显示可视化结果
    
    Returns:
        tuple: (处理后的图像, 叶片掩码, 原始图像)
    """

    # 切割为小图片，逐个处理。因为不确定工作目录的情况，所以暂时注释掉
    '''
    # 把大的tif切割成多个4000*3500的小块，这样内存足够处理
    tmp_dir = os.path.dirname(image_path) + '/tmp/'
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    command = f"gdal_retile.py -ps 4000 3500 -targetDir {tmp_dir} {image_path}"

    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Subprocess failed with code {e.returncode}")
    
    sub_images = os.listdir(tmp_dir)
    for sub_image in sub_images:
        print (sub_image)
    '''

    # 读取图像
    img = cv2.imread(image_path)
    ## 读取图像
    #nparr = np.frombuffer(image_bytes, np.uint8)
    ## Decode image
    #img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    height, width = img.shape[:2]

    dataset1 = gdal.Open(image_path)
    projection = dataset1.GetProjection()
    geotransform = dataset1.GetGeoTransform()

    return img, projection, geotransform
    

def get_display_region(mask):
    """获取有效显示区域的边界框"""
    rows = np.any(mask > 0, axis=1)
    cols = np.any(mask > 0, axis=0)
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    
    # 添加边距
    padding = 10
    ymin = max(0, ymin - padding)
    ymax = min(mask.shape[0], ymax + padding)
    xmin = max(0, xmin - padding)
    xmax = min(mask.shape[1], xmax + padding)
    
    return ymin, ymax, xmin, xmax

def calculate_ngrdi(image):
    """计算NDVI指数"""
    b, g, r = cv2.split(image)
    #mask_bool = mask > 0
    
    # 创建带NaN的数组
    pseudo_ndvi = np.full_like(g, np.nan, dtype=float)
    
    # 只在mask区域内计算
    denominator = (g.astype(float) + r.astype(float))
    #valid = (denominator != 0) & mask_bool
    #pseudo_ndvi[valid] = (g[valid].astype(float) - r[valid].astype(float)) / denominator[valid]
    pseudo_ndvi = (g.astype(float) - r.astype(float)) / denominator
    
    return pseudo_ndvi

#def analyze_leaf(image_path, show_visualization=True):
def gen_ngrdi(in_tif, out_tif):
    """综合分析叶片特征"""
    # 处理图像
    #result, mask, original = process_leaf_image(image_path, show_visualization=False)
    original, projection, geotransform = process_ngrdi(in_tif)
    
    # 计算各项指标
    ngrdi = calculate_ngrdi(original)
    result = cv2.imwrite(out_tif, ngrdi)
    dataset = gdal.Open(out_tif, gdal.GA_Update)
    dataset.SetGeoTransform( geotransform )
    dataset.SetProjection( projection )
    
    
    return True

if __name__ == "__main__":
    # image_path = '/Users/baoyonghui/Downloads/cropmirror-utils-test/rgb_orthophoto_2025_03_27_110432.tif'
    image_path = 'D://cropmirror//cropmirror-utils//src//rgb//rgb_orthophoto_2025_01_09_222535.tif'
    try:
        # results = gen_ngrdi(image_path, '/Users/baoyonghui/Downloads/cropmirror-utils-test/result.tif')
        results = gen_ngrdi(image_path, 'D://cropmirror//cropmirror-utils//src//rgb//rgb_orthophoto_2025_01_09_222535_result.tif')
        print (results)
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}") 