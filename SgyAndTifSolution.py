import streamlit as st
import segyio
import rasterio
import numpy as np
import plotly.graph_objects as go
from rasterio.enums import Resampling
import os

# 设置页面
st.set_page_config(page_title="地震与地形 3D 可视化系统", layout="wide")

# ==========================================
# 1. 数据加载模块 (带缓存)
# ==========================================

@st.cache_data
def load_tif_data(tif_path, downsample_factor=4):
    """读取TIF数据，修复异常值"""
    if not os.path.exists(tif_path):
        return None
    try:
        with rasterio.open(tif_path) as src:
            h, w = int(src.height / downsample_factor), int(src.width / downsample_factor)
            data = src.read(1, out_shape=(h, w), resampling=Resampling.bilinear).astype(float)
            
            # 处理 NoData 和 极值 (10^38)
            if src.nodata is not None:
                data[data == src.nodata] = np.nan
            data[np.abs(data) > 1e10] = np.nan
            
            # 填充无效点
            if np.isnan(data).any():
                mean_val = np.nanmean(data) if not np.isnan(data).all() else 0
                data[np.isnan(data)] = mean_val
            return data
    except Exception as e:
        st.error(f"❌ TIF 读取错误: {e}")
        return None

@st.cache_data
def load_sgy_slice(sgy_path, slice_type, index):
    """读取SGY数据，带几何识别异常处理"""
    if not os.path.exists(sgy_path):
        return None
    try:
        with segyio.open(sgy_path, "r", ignore_geometry=False) as f:
            if slice_type == 'Inline':
                idx = f.ilines[min(max(index, 0), len(f.ilines)-1)]
                data = segyio.tools.collect(f.iline[idx])
            elif slice_type == 'Crossline':
                idx = f.xlines[min(max(index, 0), len(f.xlines)-1)]
                data = segyio.tools.collect(f.xline[idx])
            else: # Time Slice
                data = f.depth_slice[min(max(index, 0), f.samples.size-1)]
            return data.T
    except Exception as e:
        # 降级处理
        try:
            with segyio.open(sgy_path, "r", ignore_geometry=True) as f:
                return f.trace[index].reshape(-1, 1)
        except:
            return None

# ==========================================
# 2. 侧边栏交互模块 (使用 Form 实现防抖)
# ==========================================

st.sidebar.header("数据与配置")

# 文件路径放在 Form 外，因为它们通常不频繁改动
tif_file = st.sidebar.text_input("TIF 文件路径", "new_dem.tif")
sgy_file = st.sidebar.text_input("SGY 文件路径", "f3_sm.sgy")

# 使用 Form 封装所有滑块和选择框，实现“确认后才渲染”
with st.sidebar.form("visualization_settings"):
    st.subheader("显示参数")
    z_exag = st.slider("地形垂直夸张倍数", 0.1, 10.0, 2.0)
    topo_opacity = st.slider("地形透明度", 0.0, 1.0, 0.8)
    
    st.markdown("---")
    st.subheader("切片参数")
    slice_opt = st.selectbox("切片方向", ["Time Slice", "Inline", "Crossline"])
    slice_idx = st.number_input("切片索引", value=10, step=1)
    
    # 修复色彩方案名称 (全小写)
    colorscale_opt = st.selectbox(
        "地震色彩方案", 
        ["rdbu", "balance", "gray", "picnic"],
        index=0
    )
    
    contrast_limit = st.slider("地震对比度增强", 80, 100, 98, help="百分比分位数截断")

    # Form 的提交按钮
    submit_button = st.form_submit_button("更新视图")

# ==========================================
# 3. 三维绘图模块
# ==========================================

def create_3d_plot(tif_data, sgy_slice, colorscale, z_exag, opacity, contrast):
    fig = go.Figure()

    # A. 渲染地形
    ny, nx = tif_data.shape
    fig.add_trace(go.Surface(
        z=tif_data * z_exag,
        colorscale='earth',
        opacity=opacity,
        name='地形表面',
        showscale=False
    ))

    # B. 渲染地震切片
    if sgy_slice is not None:
        s_ny, s_nx = sgy_slice.shape
        x_coords = np.linspace(0, nx, s_nx)
        y_coords = np.linspace(0, ny, s_ny)
        
        # 计算切片基准面（地形底部下方）
        z_base = np.nanmin(tif_data * z_exag) - 500 
        
        # 动态计算颜色映射范围，增强对比度
        vmax = np.percentile(np.abs(sgy_slice), contrast)
        
        fig.add_trace(go.Surface(
            x=x_coords,
            y=y_coords,
            z=np.full_like(sgy_slice, z_base),
            surfacecolor=sgy_slice,
            colorscale=colorscale,
            cmin=-vmax, # 地震数据通常是对称的
            cmax=vmax,
            name='地震剖面',
            colorbar=dict(title="振幅", x=1.05)
        ))

    fig.update_layout(
        scene=dict(
            xaxis_title='X (Column)',
            yaxis_title='Y (Row)',
            zaxis_title='Z (Elevation)',
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.4),
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=800
    )
    return fig

# ==========================================
# 4. 主程序逻辑
# ==========================================

if submit_button:
    if not os.path.exists(tif_file) or not os.path.exists(sgy_file):
        st.error("❌ 文件路径无效，请检查当前目录下是否存在对应的 .tif 和 .sgy 文件。")
    else:
        with st.spinner("正在处理数据，请稍候..."):
            terrain = load_tif_data(tif_file)
            seismic = load_sgy_slice(sgy_file, slice_opt, int(slice_idx))

            if terrain is not None:
                fig = create_3d_plot(
                    terrain, seismic, colorscale_opt, 
                    z_exag, topo_opacity, contrast_limit
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("地形数据加载失败。")
else:
    # 初始提示界面
    st.info("👋 欢迎！请在左侧调整参数，点击【更新视图】按钮开始渲染。")