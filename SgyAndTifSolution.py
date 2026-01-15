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
# 1. 数据加载模块
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
    读取SGY数据。
    修复：使用 .copy() 确保返回的是独立的 numpy 数组，解决序列化报错。
    """
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
            
            # 关键修复点：转置并 copy，断开与文件句柄的内存映射连接
            return np.require(data.T, dtype=np.float32, requirements='C').copy()
            
    except Exception as e:
        try:
            with segyio.open(sgy_path, "r", ignore_geometry=True) as f:
                # 降级处理：读取单条道并扩展
                raw_data = f.trace[index].reshape(-1, 1)
                return np.repeat(raw_data, 100, axis=1).astype(np.float32).copy()
        except:
            return None

# ==========================================
# 2. 侧边栏交互模块
# ==========================================

st.sidebar.header("数据与配置")
tif_file = st.sidebar.text_input("TIF 文件路径", "new_dem.tif")
sgy_file = st.sidebar.text_input("SGY 文件路径", "f3_sm.sgy")

with st.sidebar.form("visualization_settings"):
    st.subheader("显示参数")
    z_exag = st.slider("地形垂直夸张倍数", 0.1, 10.0, 2.0)
    topo_opacity = st.slider("地形透明度", 0.0, 1.0, 0.5) # 默认设为 0.5 以便看地下

    st.subheader("位置微调")
    # 地震切片通常在 DEM 之下，所以默认偏移给负值
    slice_z_offset = st.slider("地震剖面高度偏移", -5000, 5000, -500)
    
    st.markdown("---")
    st.subheader("切片参数")
    slice_opt = st.selectbox("切片方向", ["Time Slice", "Inline", "Crossline"])
    slice_idx = st.number_input("切片索引", value=10, step=1)
    
    colorscale_opt = st.selectbox("地震色彩方案", ["rdbu", "balance", "gray"], index=0)
    contrast_limit = st.slider("地震对比度增强", 80, 100, 98)

    submit_button = st.form_submit_button("更新视图")

# ==========================================
# 3. 三维绘图模块
# ==========================================

def create_3d_plot(tif_data, sgy_slice, colorscale, z_exag, opacity, contrast, slice_type, z_offset):
    fig = go.Figure()

    # A. 渲染地形
    ny, nx = tif_data.shape
    x_grid = np.arange(nx)
    y_grid = np.arange(ny)
    
    fig.add_trace(go.Surface(
        z=tif_data * z_exag,
        x=x_grid,
        y=y_grid,
        colorscale='earth',
        opacity=opacity,
        name='地形表面',
        showscale=False
    ))

    # B. 渲染地震切片
    if sgy_slice is not None:
        s_rows, s_cols = sgy_slice.shape
        vmax = np.percentile(np.abs(sgy_slice), contrast)
        
        # 计算基准高度（地形平均值 + 偏移）
        z_base = np.nanmean(tif_data * z_exag) + z_offset
        
        if slice_type == "Time Slice":
            x_s = np.linspace(0, nx, s_cols)
            y_s = np.linspace(0, ny, s_rows)
            X, Y = np.meshgrid(x_s, y_s)
            Z = np.full_like(sgy_slice, z_base)
            
        elif slice_type == "Inline":
            # 垂直剖面：固定 X，展开 Y 和 Z
            y_s = np.linspace(0, ny, s_cols)
            # 假设地震数据垂直跨度为 1000 个单位
            z_s = np.linspace(z_base - 500, z_base + 500, s_rows)
            Y, Z = np.meshgrid(y_s, z_s)
            X = np.full_like(Z, nx // 2) 
            
        else: # Crossline
            # 垂直剖面：固定 Y，展开 X 和 Z
            x_s = np.linspace(0, nx, s_cols)
            z_s = np.linspace(z_base - 500, z_base + 500, s_rows)
            X, Z = np.meshgrid(x_s, z_s)
            Y = np.full_like(Z, ny // 2)

        fig.add_trace(go.Surface(
            x=X, y=Y, z=Z,
            surfacecolor=sgy_slice,
            colorscale=colorscale,
            cmin=-vmax, cmax=vmax,
            name='地震切片',
            colorbar=dict(title="振幅", x=1.1)
        ))

    fig.update_layout(
        scene=dict(
            xaxis_title='X', yaxis_title='Y', zaxis_title='Z (Elevation)',
            aspectmode='data' # 保持比例
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=850
    )
    return fig

# ==========================================
# 4. 主程序逻辑
# ==========================================

if submit_button:
    if not os.path.exists(tif_file) or not os.path.exists(sgy_file):
        st.error("❌ 文件不存在，请检查路径。")
    else:
        with st.spinner("正在努力加载 3D 场景..."):
            terrain = load_tif_data(tif_file)
            seismic = load_sgy_slice(sgy_file, slice_opt, int(slice_idx))

            if terrain is not None:
                # 核心修复点：传入全部 8 个参数
                fig = create_3d_plot(
                    terrain, 
                    seismic, 
                    colorscale_opt, 
                    z_exag, 
                    topo_opacity, 
                    contrast_limit,
                    slice_opt,
                    slice_z_offset
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("地形数据加载失败。")
else:
    st.info("💡 请在左侧配置参数后点击“更新视图”。建议调低“地形透明度”以观察地下结构。")
