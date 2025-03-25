import logging
import unittest
import os
from cropmirror.ndvi.prescription.irrigation_prescription import IrrigationPrescription
from cropmirror.utils.polygon import generate_polygon


class TestNdvi(unittest.TestCase):
    def setUp(self):
        # 设置测试所需的参数
        self.ndvi_tif = "src/test/ndvi/ndvi.tif"  # 假设存在的测试文件
        self.values = [1, 2, 3, 4, 5]
        self.work_dirpath = "test_data/ndvi"

        # 创建 Ndvi 实例
        self.ndvi = IrrigationPrescription(
            ndvi_tif=self.ndvi_tif,
            geometry=generate_polygon(
                center_lat=36.47961816044513,
                center_lon=119.59712908911918,
                distance=1000,
                cap_style="round",
            ),
            num=5,
            workspace=self.work_dirpath,
        )

    def test_initialization(self):
        # 测试初始化
        self.assertEqual(self.ndvi._ndvi_tif, self.ndvi_tif)
        self.assertTrue(os.path.exists(self.work_dirpath))

    def test_reclassify(self):
        # 测试 reclassify 方法
        self.ndvi.run()
        reclassify_file_exists = os.path.exists(self.ndvi._files._reclassify_file)
        logging.info(self.ndvi._files._reclassify_file)
        self.assertTrue(reclassify_file_exists)

    def tearDown(self):
        pass
        # 清理测试生成的文件
        
        # if os.path.exists(self.work_dirpath):
        #     for file in os.listdir(self.work_dirpath):
        #         os.remove(os.path.join(self.work_dirpath, file))
        #     os.rmdir(self.work_dirpath)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(pathname)s %(lineno)d  %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    unittest.main()
