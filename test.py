import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

# =========================
# 1) 全局样式设置
# =========================
plt.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
    'PingFang SC', 'WenQuanYi Zen Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

# 9:16 竖版高清
fig, ax = plt.subplots(figsize=(9, 16), dpi=300)

# =========================
# 2) 构造平滑且严格命中锚点的曲线数据
#    在 log(y) 空间做 PCHIP 插值，只用于生成平滑曲线，
#    图上显示仍然使用线性 Y 轴
# =========================
anchors_x = np.array([1, 1000, 2000, 3000, 4484], dtype=float)
anchors_y = np.array([14102, 35, 13, 6, 2], dtype=float)

x = np.linspace(1, 4484, 4484)
interp = PchipInterpolator(anchors_x, np.log(anchors_y))
y = np.exp(interp(x))

# 强制指定点精确命中
exact_points = {
    1: 14102,
    1000: 35,
    2000: 13,
    3000: 6,
    4484: 2
}
for xi, yi in exact_points.items():
    idx = np.argmin(np.abs(x - xi))
    y[idx] = yi

# =========================
# 3) 区域高亮
# =========================
# 高频核心区：前500
ax.axvspan(1, 500, color='#2E8B57', alpha=0.14, zorder=0)

# 低频长尾区：后段
ax.axvspan(2700, 4484, color='#C0392B', alpha=0.10, zorder=0)
ax.text(
    3600, 2600, '低频长尾区',
    ha='center', va='center',
    fontsize=16, color='#A93226',
    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec='none', alpha=0.8),
    zorder=5
)

# =========================
# 4) 蓝色渐变填充（曲线下方）
#    线性坐标下可直接从 0 开始填充
# =========================
base_color = '#2F80ED'
n_layers = 100

for i in range(n_layers):
    y1 = y * (i / n_layers)
    y2 = y * ((i + 1) / n_layers)
    alpha = 0.01 + 0.20 * (((i + 1) / n_layers) ** 1.8)
    ax.fill_between(x, y1, y2, color=base_color, alpha=alpha, linewidth=0, zorder=1)

# 主曲线：平滑连续
ax.plot(x, y, color='#1565C0', linewidth=3.2, zorder=3)

# =========================
# 5) 精确绘制指定标注点
# =========================
points = [
    ("the", 1, 14102),
    ("black", 1000, 35),
    ("adaptation", 2000, 13),
    ("federal", 3000, 6),
]

px = [p[1] for p in points]
py = [p[2] for p in points]
ax.scatter(px, py, s=70, color='#0D47A1', edgecolor='white', linewidth=1.2, zorder=6)

# =========================
# 6) 标注（箭头精确指向点）
# =========================
annot_style = dict(
    arrowprops=dict(
        arrowstyle='->',
        color='#333333',
        lw=1.5,
        shrinkA=5,
        shrinkB=5,
        connectionstyle='arc3,rad=0.08'
    ),
    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec='#D0D7DE', alpha=0.97),
    fontsize=13,
    color='#111111',
    zorder=10
)

ax.annotate(
    'the（第1位，14102次）',
    xy=(1, 14102),
    xytext=(470, 13600),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'black（第1000位，35次）',
    xy=(1000, 35),
    xytext=(1350, 4300),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'adaptation（第2000位，13次）',
    xy=(2000, 13),
    xytext=(2300, 2200),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'federal（第3000位，6次）',
    xy=(3000, 6),
    xytext=(3180, 900),
    ha='left', va='center',
    **annot_style
)

# =========================
# 7) 坐标轴、刻度、网格
# =========================
ax.set_xlim(1, 4484)
ax.set_ylim(0, 15500)

ax.set_xlabel('频率排名', fontsize=16, labelpad=14)
ax.set_ylabel('出现次数', fontsize=16, labelpad=14)
ax.set_title('齐普夫法则：高考真题词频分布', fontsize=24, pad=22, weight='bold')

# X 轴刻度
ax.set_xticks([1, 1000, 2000, 3000, 4000, 4484])
ax.set_xticklabels(['1', '1000', '2000', '3000', '4000', '4484'], fontsize=13)

# Y 轴刻度
yticks = [1, 100, 1000, 5000, 10000, 14000]
ax.set_yticks(yticks)
ax.set_yticklabels([str(v) for v in yticks], fontsize=13)

# 网格线
ax.grid(axis='y', linestyle='--', linewidth=0.8, alpha=0.35)
ax.grid(axis='x', linestyle=':', linewidth=0.5, alpha=0.15)

# 弱化上右边框
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# =========================
# 8) 辅助说明文字
# =========================
ax.text(
    620, 10600,
    '少量高频词覆盖大量出题',
    fontsize=14, color='#1E6B43',
    bbox=dict(boxstyle='round,pad=0.28', fc='white', ec='none', alpha=0.75),
    zorder=5
)

ax.text(
    2850, 550,
    '大量低频词仅零星出现',
    fontsize=14, color='#A93226',
    bbox=dict(boxstyle='round,pad=0.28', fc='white', ec='none', alpha=0.75),
    zorder=5
)

# =========================
# 9) 布局与导出
# =========================
plt.tight_layout()

# 导出高清 PNG
plt.savefig('zipf_gaokao_wordfreq_smooth_9_16.png', dpi=300, bbox_inches='tight')

# 导出 SVG
plt.savefig('zipf_gaokao_wordfreq_smooth_9_16.svg', bbox_inches='tight')

plt.show()
