# 多变量异常检测算法

## 概述

MAD 是单变量方法，只能逐字段检测。多变量方法能发现"单个字段正常但组合异常"的情况。

## 1. 孤立森林 (Isolation Forest)

适合高维数据的无监督异常检测，不需要标注数据。

### 原理

异常点更容易被隔离（随机分割时需要更少的分割次数）。

```
异常分数:
  s(x, n) = 2^(-E(h(x)) / c(n))

  h(x) = 样本x在树中的路径长度
  c(n) = 二叉搜索树的平均路径长度 = 2*H(n-1) - 2*(n-1)/n
  E(h(x)) = 所有树中路径长度的期望

  s → 1: 异常
  s → 0.5: 正常
  s → 0: 非常正常
```

### 水利场景应用

```
特征向量: [水位, 入库流量, 出库流量, 蓄水量, 时段雨量]

if 孤立森林分数 > 0.6:
  → 多指标联合异常
  → 可能原因: 数据采集错误、设备故障、极端天气
```

### 参数建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| n_estimators | 100 | 树的数量 |
| max_samples | 256 | 每棵树的采样数(水利数据量不大) |
| contamination | 0.05 | 预期异常比例5% |
| max_features | 1.0 | 使用全部特征 |

### 伪代码

```python
def isolation_forest(data, n_trees=100, max_samples=256):
    trees = []
    for _ in range(n_trees):
        # 随机采样
        sample = random_sample(data, max_samples)
        # 构建隔离树
        tree = build_isolation_tree(sample, depth=0, max_depth=ceil(log2(max_samples)))
        trees.append(tree)

    # 计算每个样本的异常分数
    scores = []
    for x in data:
        avg_path = mean([path_length(x, tree) for tree in trees])
        score = 2 ** (-avg_path / c(len(data)))
        scores.append(score)

    return scores  # >0.6 为异常

def build_isolation_tree(data, depth, max_depth):
    if depth >= max_depth or len(data) <= 1:
        return LeafNode(size=len(data))

    # 随机选择特征和分割点
    feature = random_feature(data)
    split_value = random.uniform(min(data[feature]), max(data[feature]))

    left = data[data[feature] < split_value]
    right = data[data[feature] >= split_value]

    return InternalNode(feature, split_value,
                       build_isolation_tree(left, depth+1, max_depth),
                       build_isolation_tree(right, depth+1, max_depth))
```

## 2. DBSCAN (密度聚类)

基于密度的聚类，噪声点即为异常。

### 原理

```
核心概念:
  ε-邻域: 距离 < ε 的点集
  核心点: ε-邻域内点数 >= minPts
  边界点: 在核心点的ε-邻域内，但自身不是核心点
  噪声点: 既不是核心点也不是边界点 → 异常
```

### 水利场景应用

```
特征: [水位偏差, 流量偏差, 雨量] (归一化后)

DBSCAN(ε=0.3, minPts=5)
  → 正常数据形成密集簇
  → 异常数据被标记为噪声(-1)

优势: 不需要预设异常比例，自动发现离群点
```

### 参数选择

```
ε 选择 (k-距离图法):
  1. 计算每个点到第k近邻的距离 (k=minPts)
  2. 按距离排序画图
  3. 拐点处即为合适的 ε

minPts 选择:
  经验值: minPts >= 维度数 + 1
  水利数据(3-5维): minPts = 5-10
```

### 伪代码

```python
def dbscan(data, eps, min_pts):
    labels = [-1] * len(data)  # -1 = 未分类
    cluster_id = 0

    for i in range(len(data)):
        if labels[i] != -1:
            continue

        neighbors = range_query(data, i, eps)

        if len(neighbors) < min_pts:
            labels[i] = -1  # 噪声(异常)
            continue

        # 新簇
        labels[i] = cluster_id
        seeds = neighbors.copy()

        while seeds:
            j = seeds.pop(0)
            if labels[j] == -1:
                labels[j] = cluster_id  # 边界点
            if labels[j] != -1:
                continue

            labels[j] = cluster_id
            j_neighbors = range_query(data, j, eps)
            if len(j_neighbors) >= min_pts:
                seeds.extend(j_neighbors)

        cluster_id += 1

    return labels  # -1 = 异常

def range_query(data, point_idx, eps):
    return [j for j in range(len(data))
            if euclidean_distance(data[point_idx], data[j]) < eps]
```

## 3. 自编码器 (Autoencoder)

深度学习方法，通过重建误差检测异常。

### 原理

```
编码器: 输入 → 压缩表示 (降维)
解码器: 压缩表示 → 重建输入

正常数据: 重建误差小
异常数据: 重建误差大 (模型没见过这种模式)
```

### 网络结构

```
输入层: N个特征 (水位+流量+雨量+渗压+GNSS = 5)
编码器:
  Dense(5, 16, ReLU)
  Dense(16, 8, ReLU)    ← 瓶颈层
解码器:
  Dense(8, 16, ReLU)
  Dense(16, 5, Linear)

损失函数: MSE(输入, 重建)
异常阈值: threshold = mean(loss) + 3 * std(loss)
```

### 伪代码

```python
class AnomalyAutoencoder(nn.Module):
    def __init__(self, input_dim=5):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(8, 16), nn.ReLU(),
            nn.Linear(16, input_dim)
        )

    def forward(self, x):
        z = self.encoder(x)
        reconstructed = self.decoder(z)
        return reconstructed

def detect_anomaly(model, data):
    model.eval()
    with torch.no_grad():
        reconstructed = model(data)
        loss = mse_per_sample(data, reconstructed)

    threshold = mean(loss) + 3 * std(loss)
    anomalies = loss > threshold
    return anomalies, loss
```

## 算法对比

| 算法 | 维度 | 训练 | 速度 | 适用场景 |
|------|------|------|------|---------|
| MAD | 单变量 | 无需 | 极快 | 逐字段快速检测 |
| 孤立森林 | 多变量 | 无需 | 快 | 通用多维异常检测 |
| DBSCAN | 多变量 | 无需 | 中 | 密度不均匀的数据 |
| 自编码器 | 多变量 | 需要 | 慢 | 复杂非线性模式 |

## 与MAD的组合使用

```
第一层: MAD 逐字段快速检测 → 标记单变量异常
第二层: 孤立森林/DBSCAN 多变量联合检测 → 标记组合异常
第三层: 自编码器(可选) → 检测复杂模式异常

综合判定:
  MAD异常 + 多变量异常 → 高置信度异常
  仅MAD异常 → 中置信度，可能是正常波动
  仅多变量异常 → 需人工确认，可能是关联性变化
```
