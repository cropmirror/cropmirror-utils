# cropmirror-utils develop environment setup

```sh
python -m venv venv
#windows
venv/scripts/activate
#macos/linux
#source venv/bin/activate

# 安装包管理器
pip install poetry

# 设置 包管理器 包上传地址
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config http-basic.testpypi __token__ <testpypi_token> # pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 本地打包测试


#打包上传

poetry publish --build -r testpypi

pip install -i https://test.pypi.org/simple/ cropmirror


# 添加项目依赖
poetry add geopandas
```

# 本地测试
```shell
poetry build
pip install ./dist/cropmirror-0.0.7.tar.gz

# import
# from cropmirror import example
```
