# 地震与地形 3D 可视化系统 (Seismic & Terrain 3D Visualizer)

https://img.shields.io/badge/Python-3.8%2B-blue](https://python.org)
https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B](https://streamlit.io)
https://img.shields.io/badge/License-MIT-green](LICENSE)

这是一个基于 Python 和 Streamlit 开发的交互式可视化工具，旨在同时展现地表地形（TIF/DEM）与地下地震剖面（SEGY/SGY）的空间位置关系。

https://via.placeholder.com/800x400.png?text=3D+Visualization+Demo
系统界面示意图

## 🌟 核心功能

### 多维度可视化

• 地形渲染：支持加载大尺寸 TIF/DEM 数据，内置下采样优化与异常值（NoData）自动修复

• 地震切片解析：

  • Time Slice：查看特定深度的水平地震属性

  • Inline / Crossline：自动构建垂直剖面网格，实现地下结构的"切片"展示

### 交互式控制

• 垂直夸张 (Exaggeration)：动态调整地形起伏感

• 透明度融合：调节地表透明度，透视地下地震构造

• 深度对齐：通过滑块实时修正地震数据与 DEM 之间的海拔偏差

• 高性能缓存：利用 Streamlit 缓存机制，避免重复解析大文件

## 🛠️ 技术栈

组件 用途 版本

Streamlit Web 应用框架 ≥1.28

Plotly 3D 可视化渲染 ≥5.17

Rasterio 地理数据处理 ≥1.3

Segyio 地震数据解析 ≥1.9

NumPy 数值计算 ≥1.24

## 🚀 快速上手

### 1. 环境准备

确保已安装 Python 3.8+，然后安装依赖：
### 克隆仓库
git clone https://github.com/yourusername/seismic-terrain-visualizer.git
cd seismic-terrain-visualizer

### 安装依赖
pip install streamlit segyio rasterio numpy plotly


### 2. 数据准备

将你的数据文件放置在与主程序平级目录下：

• 地形文件：.tif 或 .dem 格式

• 地震文件：.sgy 或 .segy 格式

### 3. 启动应用(在powershell中输入）
cd /your file path
conda activate web
streamlit run SgyAndTifSolution.py


应用将在浏览器中自动打开（默认为 http://localhost:8501）

## 📖 使用指南

数据加载

1. 在左侧边栏的"数据配置"部分
2. 输入或选择地形文件路径
3. 输入或选择地震文件路径
4. 点击"加载数据"按钮

3D 视图控制

控制项 功能 建议值

地形透明度 透视地下构造 0.3-0.7

垂直夸张 增强地形起伏 1.0-5.0

高度偏移 对齐地震剖面 根据数据调整

颜色映射 地震属性显示 Viridis, Plasma 等

切片浏览

1. 在"切片类型"中选择：
   • Inline：纵向剖面

   • Crossline：横向剖面

   • Timeslice：水平切片

2. 输入线号或深度值
3. 点击"更新视图"

## ⚠️ 技术说明

内存优化

对于超大 TIF 文件，默认开启 4 倍下采样。如需调整，修改 load_tif_data 函数中的 downsample_factor 参数：
# SgyAndTifSolution.py
downsample_factor = 4  # 调整为 2 或 1 以获得更高分辨率


坐标系对齐

目前通过网格拉伸（Linspace）将地震数据对齐至地形范围。如需精确地理坐标对齐，需要：

1. 读取 SGY 文件头的坐标字段（SourceX/Y）
2. 实现坐标转换函数
3. 集成投影系统支持

数据副本处理

为解决 Streamlit 缓存序列化问题，所有返回的 NumPy 数组都通过 .copy() 断开连接：
@st.cache_data
def load_data():
    return array.copy()  # 确保缓存安全


## 📁 项目结构

├── SgyAndTifSolution.py      # 主程序文件

├── README.md                 # 本文档

├── terrain.tif         

├── seismic.sgy 



## 🔧 高级配置

自定义颜色方案

修改 visualization.py 中的颜色映射：
COLORMAPS = {
    '地形': 'terrain',
    '地震': 'viridis',
    '自定义': [[0, 'blue'], [0.5, 'white'], [1, 'red']]
}

最后更新于2026.1
