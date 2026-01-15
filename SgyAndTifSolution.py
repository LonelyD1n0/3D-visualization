import streamlit as st
import segyio
import rasterio
import numpy as np
import plotly.graph_objects as go
from rasterio.enums import Resampling
import os
import tempfile  # 用于处理临时文件

# 设置页面
st.set_page_config(page_title="地震与地形 3D 可视化系统", layout="wide")

# ==========================================
# 1. 数据加载模块 (已适配文件对象)
# ==========================================

@st.cache_data
def load_tif_data(tif_file_obj, downsample_factor=4):
    """从上传的文件对象读取 TIF"""
    try:
        # rasterio 支持直接读取 MemoryFile
        with rasterio.open(tif_file_obj) as src:
            h, w = int(src.height / downsample_factor), int(src.width / downsample_factor)
            data = src.read(1, out_shape=(h, w), resampling=Resampling.bilinear).astype(float)
            
            if src.nodata is not None:
                data[data == src.nodata] = np.nan
            data[np.abs(data) > 1e10] = np.nan
            
            if np.isnan(data).any():
                mean_val = np.nanmean(data) if not np.isnan(data).all() else 0
                data[np.isnan(data)] = mean_val
            return data
    except Exception as e:
        st.error(f"❌ TIF 读取错误: {e}")
        return None

@st.cache_data
def load_sgy_slice(sgy_path, slice_type, index):
    """
    由于 segyio 必须读取物理路径，这里接收临时文件路径
    """
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
            
            return np.require(data.T, dtype=np.float32, requirements='C').copy()
            
    except Exception as e:
        st.warning(f"⚠️ 标准模式读取失败，尝试降级模式: {e}")
        try:
            with segyio.open(sgy_path, "r", ignore_geometry=True) as f:
                raw_data = f.trace[min(index, f.tracecount-1)].reshape(-1, 1)
                return np.repeat(raw_data, 100, axis=1).astype(np.float32).copy()
        except:
            return None

# ==========================================
# 2. 侧边栏交互模块
# ==========================================

st.sidebar.header("数据上传")
# 替换为文件上传组件
uploaded_tif = st.sidebar.file_uploader("上传地形文件 (TIF)", type=["tif", "tiff"])
uploaded_sgy = st.sidebar.file_uploader("上传地震文件 (SGY/SEGY)", type=["sgy", "segy"])

with st.sidebar.form("visualization_settings"):
    st.subheader("显示参数")
    z_exag = st.slider("地形垂直夸张倍数", 0.1, 10.0, 2.0)
    topo_opacity = st.slider("地形透明度", 0.0, 1.0, 0.5)

    st.subheader("位置微调")
    slice_z_offset = st.slider("地震剖面高度偏移", -5000, 5000, -500)
    
    st.markdown("---")
    st.subheader("切片参数")
    slice_opt = st.selectbox("切片方向", ["Time Slice", "Inline", "Crossline"])
    slice_idx = st.number_input("切片索引", value=10, step=1)
    
    colorscale_opt = st.selectbox("地震色彩方案", ["rdbu", "balance", "gray"], index=0)
    contrast_limit = st.slider("地震对比度增强", 80, 100, 98)

    submit_button = st.form_submit_button("更新三维视图")

# [create_3d_plot 函数部分保持不变，代码同你提供的一致]
def create_3d_plot(tif_data, sgy_slice, colorscale, z_exag, opacity, contrast, slice_type, z_offset):
    # ... (此处省略，代码逻辑不需要修改) ...
    fig = go.Figure()
    ny, nx = tif_data.shape
    x_grid, y_grid = np.arange(nx), np.arange(ny)
    fig.add_trace(go.Surface(z=tif_data * z_exag, x=x_grid, y=y_grid, colorscale='earth', opacity=opacity, showscale=False))
    if sgy_slice is not None:
        s_rows, s_cols = sgy_slice.shape
        vmax = np.percentile(np.abs(sgy_slice), contrast)
        z_base = np.nanmean(tif_data * z_exag) + z_offset
        if slice_type == "Time Slice":
            x_s, y_s = np.linspace(0, nx, s_cols), np.linspace(0, ny, s_rows)
            X, Y = np.meshgrid(x_s, y_s)
            Z = np.full_like(sgy_slice, z_base)
        elif slice_type == "Inline":
            y_s, z_s = np.linspace(0, ny, s_cols), np.linspace(z_base - 500, z_base + 500, s_rows)
            Y, Z = np.meshgrid(y_s, z_s)
            X = np.full_like(Z, nx // 2) 
        else:
            x_s, z_s = np.linspace(0, nx, s_cols), np.linspace(z_base - 500, z_base + 500, s_rows)
            X, Z = np.meshgrid(x_s, z_s)
            Y = np.full_like(Z, ny // 2)
        fig.add_trace(go.Surface(x=X, y=Y, z=Z, surfacecolor=sgy_slice, colorscale=colorscale, cmin=-vmax, cmax=vmax))
    fig.update_layout(scene=dict(aspectmode='data'), height=850)
    return fig

# ==========================================
# 4. 主程序逻辑 (核心修改点)
# ==========================================

if submit_button:
    if uploaded_tif is None or uploaded_sgy is None:
        st.warning("⚠️ 请先上传 TIF 和 SGY 文件。")
    else:
        with st.spinner("正在处理数据并生成 3D 场景..."):
            # 1. 处理 TIF (rasterio 可以直接读上传的文件对象)
            terrain = load_tif_data(uploaded_tif)

            # 2. 处理 SGY (必须先保存到临时文件)
            # 使用 tempfile 创建一个临时的硬盘空间
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sgy") as tmp_file:
                tmp_file.write(uploaded_sgy.getvalue())
                tmp_path = tmp_file.name
            
            try:
                seismic = load_sgy_slice(tmp_path, slice_opt, int(slice_idx))
                
                if terrain is not None:
                    fig = create_3d_plot(
                        terrain, seismic, colorscale_opt, z_exag, 
                        topo_opacity, contrast_limit, slice_opt, slice_z_offset
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("地形数据解析失败。")
            finally:
                # 3. 清理临时文件，防止占用服务器空间
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
else:
    st.info("👋 欢迎！请上传 TIF 和 SGY 数据后点击“更新三维视图”。")
