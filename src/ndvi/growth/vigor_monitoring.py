from ndvi.preprocess.ndvi import Ndvi


class VigorMonitoring(Ndvi):
    def __init__(self, ndvi_tif: str):
        """初始化 解析ndvi_tif 文件

        Args:
            ndvi_tif (str): ndvi tif 文件路径
        """
        super().__init__(ndvi_tif=ndvi_tif)
        
        pass

    def vigor_monitoring(self,boundary_file: str, savepath: str):
        """长势分析

        Args:
            boundary_file (str): 边界文件,根据后缀shp/geojson 自动识别
            savepath (str): 结果存储路径, 文件名vigor_20250322_1407,格式包含shp/geojson
        """
        print("vigor monitoring")
        pass
    
    def biomass_estimation(self,boundary_file: str, savepath: str):
        """生物量估算

        Args:
            boundary_file (str): 边界文件,根据后缀shp/geojson 自动识别
            savepath (str): 结果存储路径, 文件名vigor_20250322_1407,格式包含shp/geojson
        """
        print("biomass estimation")
        pass
