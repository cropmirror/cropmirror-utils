import datetime
import os


class NdviFiles(object):
    def __init__(
        self,
        work_dirpath: str = None,
    ):
        """初始化 解析ndvi_tif 文件

        Args:
            ndvi_tif (str): ndvi tif 文件路径
            values: 分级数据值
            boundary_geometry: 边界 geometry,与边界 shp文件 二选一
            boundary_shp_filepath: 边界shp文件,与边界geometry 二选一
            work_dirpath: 工作路径,生成的过程文件在此目录
        """
        if work_dirpath is None:
            work_dirpath = "./data"
        if not os.path.exists(work_dirpath):
            os.makedirs(work_dirpath, exist_ok=True)
        self._timesuffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self._reclassify_file = os.path.join(
            work_dirpath, f"reclassify-{self._timesuffix}.tif"
        )

        self._dpm_shp_file = os.path.join(
            work_dirpath, f"dpm_shp_file-{self._timesuffix}.shp"
        )

        self._valued_shp_file = os.path.join(
            work_dirpath, f"valued_dpm_shp_file-{self._timesuffix}.shp"
        )

        self._geojson_file = os.path.join(
            work_dirpath, f"prescription-{self._timesuffix}.geojson"
        )

        self._clipped_shp_file = os.path.join(
            work_dirpath, f"clipped_dpm_shp_file-{self._timesuffix}.shp"
        )

        pass



