import logging
import geopandas as gpd

from .files import NdviFiles
from ...utils.geotiff_toolkit.reclassify import reclassify, raster2vector
from ...utils.shp_toolkit.toolkit import clip_shp_by_polygon, ShpToolkit
from ..generatevalues.irrigation import water_balance_calculation_base_irrigation
from .common import valued_dpm_shp_postpro


class IrrigationPrescription:
    def __init__(
        self,
        ndvi_tif,
        geometry: dict,
        num=5,
        workspace=".",
        precipitation=50,
        evapotranspiration=60,
        runoff=10,
        deep_percolation=5,
        initial_soil_moisture=280,
        target_soil_moisture=300,
    ):
        """
        ndvi_tif: ndvi geotif 文件
        precipitation = 50,  # mm precipitation (float): 降水量 (毫米)
        evapotranspiration = 60,  # mm 蒸发蒸腾量 (毫米)
        runoff = 10,  # mm 地表径流量 (毫米)
        deep_percolation = 5,  # mm 深层渗漏量 (毫米)
        initial_soil_moisture = 280,  # mm 初始土壤含水量 (毫米)
        target_soil_moisture = 300, #mm 目标土壤含水量(毫米)
        """

        self._ndvi_tif = ndvi_tif
        self._num = num
        self._geometry = geometry
        self._workspace = workspace
        self._files = NdviFiles(self._workspace)
        # 灌溉相关
        self.precipitation = precipitation  # mm precipitation (float): 降水量 (毫米)
        self.evapotranspiration = evapotranspiration  # mm 蒸发蒸腾量 (毫米)
        self.runoff = runoff  # mm 地表径流量 (毫米)
        self.deep_percolation = deep_percolation  # mm 深层渗漏量 (毫米)
        self.initial_soil_moisture = initial_soil_moisture  # mm 初始土壤含水量 (毫米)
        self.target_soil_moisture = target_soil_moisture  # 目标土壤含水量 (毫米)



    def run(self):
        # reclassify
        reclassify(self._ndvi_tif, self._files._reclassify_file, level_num=self._num)
        raster2vector(self._files._reclassify_file, self._files._dpm_shp_file)

        # 首先需要根据处方图的类型，判断调用哪种处方图的计算函数，是底肥，追肥；
        # 追肥的话，这里需要添加养分平衡方程，而且需要先对接口传过来的数据进行判断，
        # 如果接口传过来的数据中values值不是空，那么就调用这个函数，
        # 否则就调用养分平衡方程进行计算，需要知道土壤里面有多少氮、磷、钾（碱解氮、速效磷、速效钾需要进行换算），
        # 目前这种 crop_type （作物类型）处在这种生育期下应该需要多少氮、磷、钾，结合此种作物当前生育期下的吸收率；
        # 还需要考虑上次施肥剩下的氮，是速效肥还是缓释肥，考虑气象条件，目前还剩下多少氮、磷、钾。最后计算出来应该追多少肥。底肥的话，只考虑土壤及作物品种就行。

        # 氮的需求量应该还受NDVI的调控；
        # self.agri_operation_input_values = self.nutrients_balance_calculation_base_fertilization()

        # 这里选择变量灌溉量的计算方法：人工分段指定法；节水率法；水量平衡法；
        # 应该还有旱灾等级法；
        values, average_value = water_balance_calculation_base_irrigation(
            self._ndvi_tif,
            self._files._dpm_shp_file,
            self.precipitation,
            self.evapotranspiration,
            self.runoff,
            self.deep_percolation,
            self.initial_soil_moisture,
            self.target_soil_moisture,
        )
        clip_shp_by_polygon(
            self._files._dpm_shp_file, self._geometry, self._files._clipped_shp_file
        )
        shtool = ShpToolkit(self._files._clipped_shp_file)
        shtool.insert_attributes(values=values)
        shtool.save(self._files._valued_shp_file)
        shtool.save(self._files._geojson_file, driver="GeoJSON")

        # print(f"推荐灌溉量为 {recommended_irrigation} 升水每亩")

        variable_total, uniform_total, saving_rate = valued_dpm_shp_postpro(
            self._files._valued_shp_file, average_value
        )  # 依据生成的处方图，计算处方作业总施肥量、变量作业总施肥量、节肥率；

        logging.info(
            f"变量施肥总量: {variable_total} kg\n"
            f"匀量施肥总量: {uniform_total} kg\n"
            f"节肥率: {saving_rate}%"
        )
