# 空间插值算法

## 概述

用于根据离散传感器数据推算未监测位置的值。水利场景：根据多个水位站推算库区任意点水位，根据多个渗压计推算坝体内部渗压分布。

## 1. Kriging (克里金插值)

地质统计学方法，提供最优无偏估计和估计方差。

### 原理

```
Z*(s0) = Σ λi * Z(si)

Z*(s0) = 估计点s0的值
Z(si)  = 已知点si的观测值
λi     = 权重 (通过半变异函数求解)

关键: 权重不仅考虑距离，还考虑空间相关性结构
```

### 半变异函数 (Variogram)

描述空间相关性随距离变化的函数。

```
经验半变异函数:
  γ(h) = 1/(2N(h)) * Σ [Z(si+h) - Z(si)]²

  h = 距离
  N(h) = 距离为h的点对数
```

### 常用半变异函数模型

```
1. 球状模型 (Spherical):
   γ(h) = C0 + C * [1.5*(h/a) - 0.5*(h/a)³]  if h <= a
   γ(h) = C0 + C                               if h > a

2. 指数模型 (Exponential):
   γ(h) = C0 + C * [1 - exp(-h/a)]

3. 高斯模型 (Gaussian):
   γ(h) = C0 + C * [1 - exp(-(h/a)²)]

参数:
  C0 = 块金值 (nugget) — 测量误差/微尺度变异
  C  = 基台值 (sill) — 总变异
  a  = 变程 (range) — 相关性消失的距离
```

### 水利场景参数

| 监测类型 | 推荐模型 | 块金C0 | 基台C | 变程a |
|----------|----------|--------|-------|-------|
| 水位(库区) | 球状 | 0.01m² | 0.1m² | 500m |
| 渗压(坝体) | 指数 | 0.05kPa² | 0.5kPa² | 50m |
| 雨量(流域) | 球状 | 1mm² | 25mm² | 10km |
| GNSS(坝面) | 高斯 | 0.01mm² | 0.1mm² | 100m |

### 伪代码

```python
def kriging_estimate(known_points, target_point, variogram_model, params):
    n = len(known_points)

    # 构建克里金方程组
    # [Γ  1] [λ]   [γ0]
    # [1  0] [μ] = [1 ]

    # Γ: 已知点之间的半变异函数矩阵
    Gamma = zeros((n+1, n+1))
    for i in range(n):
        for j in range(n):
            dist = distance(known_points[i], known_points[j])
            Gamma[i][j] = variogram_model(dist, params)
        Gamma[i][n] = 1  # 拉格朗日乘子约束
        Gamma[n][i] = 1

    # γ0: 已知点与目标点之间的半变异函数向量
    gamma0 = zeros(n+1)
    for i in range(n):
        dist = distance(known_points[i], target_point)
        gamma0[i] = variogram_model(dist, params)
    gamma0[n] = 1

    # 求解权重
    weights = solve(Gamma, gamma0)
    lambdas = weights[:n]

    # 估计值
    z_star = sum(lambdas[i] * known_points[i].value for i in range(n))

    # 估计方差 (Kriging方差)
    variance = sum(lambdas[i] * gamma0[i] for i in range(n)) + weights[n]

    return z_star, variance

def spherical_variogram(h, C0, C, a):
    if h <= a:
        return C0 + C * (1.5 * h/a - 0.5 * (h/a)**3)
    else:
        return C0 + C
```

## 2. 高斯过程 (Gaussian Process)

贝叶斯方法，提供预测值和不确定性估计。

### 原理

```
f(x) ~ GP(m(x), k(x, x'))

m(x)  = 均值函数 (通常为0或常数)
k(x,x') = 协方差核函数

预测:
  f* | X, y, X* ~ N(μ*, Σ*)

  μ* = K(X*, X) * [K(X, X) + σ²I]⁻¹ * y
  Σ* = K(X*, X*) - K(X*, X) * [K(X, X) + σ²I]⁻¹ * K(X, X*)
```

### 常用核函数

```
1. RBF核 (径向基):
   k(x, x') = σ² * exp(-||x-x'||² / (2l²))
   适合: 平滑的空间变化

2. Matérn核:
   k(x, x') = σ² * (1 + √(2ν||x-x'||/l)) * exp(-√(2ν||x-x'||/l)) / Γ(ν)2^(ν-1)
   适合: 不完全平滑的自然现象

3. 复合核:
   k = k_RBF + k_Periodic + k_Noise
   适合: 有周期性+噪声的水利数据
```

### 水利场景参数

```python
# 水位空间插值
kernel = C(1.0) * RBF(length_scale=500) + WhiteKernel(noise_level=0.01)
# length_scale=500m: 水位空间相关距离
# noise_level=0.01: 测量噪声

# 渗压空间插值
kernel = C(1.0) * Matérn(length_scale=50, nu=1.5) + WhiteKernel(noise_level=0.05)
# length_scale=50m: 渗压相关距离更短
# nu=1.5: 一次可微 (渗压变化比水位更不平滑)
```

### 伪代码

```python
def gaussian_process_predict(X_train, y_train, X_test, kernel):
    n = len(X_train)
    m = len(X_test)

    # 构建协方差矩阵
    K = kernel(X_train, X_train)  # n×n
    K_star = kernel(X_test, X_train)  # m×n
    K_star_star = kernel(X_test, X_test)  # m×m

    # 加入噪声
    sigma = 0.01
    K_with_noise = K + sigma**2 * eye(n)

    # 预测均值
    K_inv = inv(K_with_noise)
    mu = K_star @ K_inv @ y_train

    # 预测方差
    Sigma = K_star_star - K_star @ K_inv @ K_star.T
    std = sqrt(diag(Sigma))

    return mu, std  # 均值和标准差
```

## 3. 反距离加权 (IDW)

最简单的空间插值方法，作为基线对比。

### 公式

```
Z*(s0) = Σ [Z(si) / di^p] / Σ [1/di^p]

di = 目标点到已知点si的距离
p  = 幂参数 (通常p=2)
```

### 参数

```
p = 1: 线性衰减
p = 2: 平方反比 (最常用)
p = 3: 立方反比 (更强调近距离)
```

### 伪代码

```python
def idw(known_points, target_point, p=2):
    numerator = 0
    denominator = 0

    for point in known_points:
        d = distance(point, target_point)
        if d < 1e-10:  # 重合点
            return point.value

        w = 1 / d**p
        numerator += w * point.value
        denominator += w

    return numerator / denominator
```

## 算法对比

| 算法 | 精度 | 速度 | 不确定性 | 适用场景 |
|------|------|------|----------|---------|
| IDW | 一般 | 极快 | 无 | 快速估算、数据密集 |
| Kriging | 高 | 中 | 有(方差) | 最优估计、需要置信区间 |
| 高斯过程 | 高 | 慢 | 有(完整分布) | 需要不确定性量化 |

## 与缺失检测/插值的配合

```
空间插值 vs 时间插值:

时间插值(interpolation.md):
  同一传感器的缺失时间点填补
  输入: 该传感器的历史时间序列
  输出: 缺失时刻的估计值

空间插值(本文件):
  未安装传感器的位置估算
  输入: 周围多个传感器的当前值
  输出: 目标位置的估计值

组合使用:
  if 传感器时间缺失 → 时间插值 (linear/quadratic/spline)
  if 传感器空间覆盖不足 → 空间插值 (kriging/gp)
  if 两者都有 → 先时间插值填补缺失，再空间插值扩展覆盖
```

## 实际应用场景

### 水库水位空间分布

```
已知: 库区5个水位站的当前水位
求解: 库区任意点的水位

步骤:
  1. 用5个站点拟合半变异函数
  2. 用Kriging估计网格点水位
  3. 绘制等水位线图
```

### 坝体渗压场

```
已知: 坝体20个渗压计的当前读数
求解: 坝体内部任意点的渗压

步骤:
  1. 渗压空间相关距离约50m
  2. 用高斯过程估计3D渗压场
  3. 识别渗压异常区域 (高方差区域)
```
