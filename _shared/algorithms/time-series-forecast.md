# 时序预测算法

## 概述

用于预测水位、渗压、GNSS位移、流量等监测指标的未来趋势。

## 1. 指数平滑 (Exponential Smoothing)

最简单实用的短期预测方法，适合水利数据的实时预测。

### 公式

```
St = α * Xt + (1-α) * St-1

其中:
  St  = t时刻的平滑值
  Xt  = t时刻的实际值
  α   = 平滑系数 (0, 1)
  St-1 = t-1时刻的平滑值
```

### 三次指数平滑 (Holt-Winters)

支持趋势+季节性：

```
水平:   Lt = α * (Xt - St-m) + (1-α) * (Lt-1 + Tt-1)
趋势:   Tt = β * (Lt - Lt-1) + (1-β) * Tt-1
季节:   St = γ * (Xt - Lt) + (1-γ) * St-m
预测:   Ft+h = Lt + h*Tt + St-m+h

参数:
  α ∈ [0.1, 0.3] — 水位变化慢，α取小值
  β ∈ [0.01, 0.1] — 趋势平滑
  γ ∈ [0.1, 0.3] — 季节性
  m = 季节周期 — 水位日变化 m=24(小时) 或 m=96(15分钟)
```

### 水利场景参数建议

| 指标 | α | β | γ | 季节周期m | 预测步长 |
|------|---|---|---|----------|---------|
| 水位 | 0.2 | 0.05 | 0.2 | 24(小时) | 1-6小时 |
| 渗压 | 0.15 | 0.03 | 0.15 | 24(小时) | 1-24小时 |
| GNSS位移 | 0.1 | 0.02 | 0.1 | 168(周) | 1-7天 |
| 流量 | 0.3 | 0.1 | 0.2 | 24(小时) | 1-6小时 |

### 伪代码

```python
def holt_winters_forecast(data, alpha, beta, gamma, m, h):
    n = len(data)
    # 初始化
    L = [mean(data[:m])]
    T = [(mean(data[m:2*m]) - mean(data[:m])) / m]
    S = [data[i] - L[0] for i in range(m)]

    # 递推
    for t in range(m, n):
        Lt = alpha * (data[t] - S[t-m]) + (1-alpha) * (L[-1] + T[-1])
        Tt = beta * (Lt - L[-1]) + (1-beta) * T[-1]
        St = gamma * (data[t] - Lt) + (1-gamma) * S[t-m]
        L.append(Lt); T.append(Tt); S.append(St)

    # 预测未来h步
    forecast = []
    for i in range(1, h+1):
        forecast.append(L[-1] + i*T[-1] + S[-m + (i-1) % m])
    return forecast
```

## 2. ARIMA (自回归积分移动平均)

适合中短期预测，能捕捉趋势和周期。

### 模型表示

```
ARIMA(p, d, q)

AR(p): 自回归 — Xt = c + φ1*Xt-1 + ... + φp*Xt-p + εt
I(d):  差分阶数 — 使序列平稳的差分次数
MA(q): 移动平均 — Xt = c + εt + θ1*εt-1 + ... + θq*εt-q
```

### 水利场景参数建议

| 指标 | p | d | q | 说明 |
|------|---|---|---|------|
| 水位 | 2-4 | 1 | 1-2 | 日变化有周期性 |
| 渗压 | 3-5 | 1 | 1-2 | 缓慢变化 |
| GNSS | 2-3 | 1-2 | 1 | 需要差分消除趋势 |
| 流量 | 3-6 | 1 | 2-3 | 波动较大 |

### 模型选择流程

```
1. 平稳性检验 (ADF检验)
   if p-value > 0.05:
     需要差分 d += 1
     重复检验

2. 确定p和q:
   - 查看ACF(自相关)图 → 确定q
   - 查看PACF(偏自相关)图 → 确定p

3. 模型拟合:
   最小化 AIC = 2k - 2ln(L)
   k=参数个数, L=似然函数

4. 残差检验:
   残差应为白噪声 (Ljung-Box检验 p > 0.05)
```

### 伪代码

```python
def arima_predict(data, p, d, q, steps):
    # 差分
    diff_data = data
    for _ in range(d):
        diff_data = [diff_data[i] - diff_data[i-1] for i in range(1, len(diff_data))]

    # 拟合AR系数 (Yule-Walker方程)
    ar_coeffs = fit_ar(diff_data, p)

    # 拟合MA系数 (最大似然估计)
    ma_coeffs = fit_ma(diff_data, q)

    # 预测
    forecast_diff = []
    for h in range(steps):
        pred = ar_predict(diff_data, ar_coeffs) + ma_predict(ma_coeffs)
        forecast_diff.append(pred)
        diff_data.append(pred)

    # 反差分
    forecast = inverse_diff(forecast_diff, data, d)
    return forecast
```

## 3. LSTM (长短期记忆网络)

适合长期依赖和复杂非线性模式，需要训练数据。

### 网络结构

```
输入层: [batch_size, seq_length, features]
  features = 监测指标数 (水位+流量+雨量 = 3)

LSTM层:
  hidden_size = 64 (水利数据64足够)
  num_layers = 2
  dropout = 0.2

全连接层:
  output_size = 预测步长

输出: 未来h个时间步的预测值
```

### 训练参数

```python
# 水利场景推荐参数
config = {
    'seq_length': 96,       # 输入序列长度 (24小时 * 4次/小时)
    'pred_length': 24,      # 预测长度 (6小时 * 4次/小时)
    'hidden_size': 64,      # 隐藏层大小
    'num_layers': 2,        # LSTM层数
    'dropout': 0.2,         # Dropout
    'learning_rate': 0.001, # 学习率
    'batch_size': 32,       # 批大小
    'epochs': 100,          # 训练轮数
}
```

### 特征工程

```
原始特征:
  - 监测值 (水位/渗压/位移)
  - 时间特征: hour_sin, hour_cos, day_sin, day_cos
  - 滞后特征: lag_1h, lag_6h, lag_24h
  - 滚动统计: rolling_mean_6h, rolling_std_6h

衍生特征:
  - 变化率: (xt - xt-1) / xt-1
  - 季节分量: 通过FFT提取主频
  - 外部变量: 雨量(对水位)、温度(对渗压)
```

### 伪代码

```python
class WaterLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, pred_length):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                           dropout=0.2, batch_first=True)
        self.fc = nn.Linear(hidden_size, pred_length)

    def forward(self, x):
        # x: [batch, seq_len, features]
        lstm_out, _ = self.lstm(x)
        out = self.fc(lstm_out[:, -1, :])  # 取最后时间步
        return out

# 训练
def train_lstm(train_data, config):
    model = WaterLSTM(input_size=features, hidden_size=64,
                      num_layers=2, pred_length=24)
    optimizer = Adam(model.parameters(), lr=0.001)
    criterion = MSE()

    for epoch in range(100):
        for batch_x, batch_y in dataloader:
            pred = model(batch_x)
            loss = criterion(pred, batch_y)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
```

## 算法选择指南

| 场景 | 推荐算法 | 理由 |
|------|----------|------|
| 实时预测(秒级) | 指数平滑 | 计算快，无需训练 |
| 短期预测(小时级) | ARIMA | 捕捉趋势和周期 |
| 中期预测(天级) | LSTM | 长期依赖 |
| 缺乏历史数据 | 指数平滑 | 不需要训练数据 |
| 多变量预测 | LSTM | 可处理多输入特征 |
| 需要置信区间 | ARIMA | 自带置信区间 |

## 与预警模块联动

```
预测值 → 与阈值比较 → 提前预警

示例:
  当前水位: 149.5m
  预测6小时后: 151.2m
  预警阈值: 150m
  → 提前6小时发出"预计水位将超限"预警
```
