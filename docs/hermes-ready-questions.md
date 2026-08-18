# Hermes CLI 直接可用问题集

> 生成时间：N/A
> 总计：290 题
> ✅ green（可直接判分）：241 题
> ⚠️  yellow（需人工判分）：49 题

## 使用说明

### 1. 在 Hermes CLI 中直接提问

```bash
# 基本语法
hermes chat -s <skill> -q "<问题>" -Q

# 示例：查询水位异常
hermes chat -s powerelf-data-governance -q "帮我检查一下最近24小时水库水位数据有没有异常值，用MAD算法检测一下" -Q

# 示例：巡检分析
hermes chat -s powerelf-inspection -q "渗压计416在5月20日有10kPa突变，工具是否检出？" -Q
```

### 2. 按 Skill 分类

#### powerelf-chatbi（51 题）

**✅ 可直接判分的问题**

1. **0** (mad-rsvr-all-may)
   ```bash
   hermes chat -s powerelf-chatbi -q "帮我用MAD算法检测st_rsvr_r表2026年5月的水位数据，看看有没有异常值" -Q
   ```
   *预期：Provider calls powerelf-data-governance skill to run MAD anomaly detection on st...*

2. **1** (mad-rsvr-rz-0p029)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表1月份的水位数据怎么会出现0.029米的数值？正常水位不是应该在455米左右吗？帮我检测一下异常" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze the rz=0.029 anomaly in Jan 2...*

3. **2** (mad-rsvr-rz-500-spike)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表5月15日水位突然跳到500米了，帮我看看这个是不是异常值" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze rz=500 spike on 2026-05-15 (s...*

4. **3** (pressure-800-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pressure_r表5月20日water_pressure达到800，比平均值443高出一大截，这是数据异常吗？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze water_pressure=800 anomaly vs...*

5. **4** (rainfall-120mm-extreme)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pptn_r表5月18日下了120mm的雨，这个雨量数据正常吗？帮我检测一下" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze extreme rainfall 120mm on 202...*

6. **5** (inq-300-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表6月30日入库流量(inq)达到300，平均值才1.22，这个数据有没有问题？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze inq=300 anomaly vs avg 1.22*

7. **0** (mad-rsvr-all-may)
   ```bash
   hermes chat -s powerelf-chatbi -q "帮我用MAD算法检测st_rsvr_r表2026年5月的水位数据，看看有没有异常值" -Q
   ```
   *预期：Provider calls powerelf-data-governance skill to run MAD anomaly detection on st...*

8. **1** (mad-rsvr-rz-0p029)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表1月份的水位数据怎么会出现0.029米的数值？正常水位不是应该在455米左右吗？帮我检测一下异常" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze the rz=0.029 anomaly in Jan 2...*

9. **2** (mad-rsvr-rz-500-spike)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表5月15日水位突然跳到500米了，帮我看看这个是不是异常值" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze rz=500 spike on 2026-05-15 (s...*

10. **3** (pressure-800-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pressure_r表5月20日water_pressure达到800，比平均值443高出一大截，这是数据异常吗？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze water_pressure=800 anomaly vs...*

11. **4** (rainfall-120mm-extreme)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pptn_r表5月18日下了120mm的雨，这个雨量数据正常吗？帮我检测一下" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze extreme rainfall 120mm on 202...*

12. **5** (inq-300-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表6月30日入库流量(inq)达到300，平均值才1.22，这个数据有没有问题？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze inq=300 anomaly vs avg 1.22*

13. **6** (missing-pressure-table)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pressure_r表5月份的数据有没有缺失？我怀疑有些时段没采到数据" -Q
   ```
   *预期：Provider calls powerelf-data-governance to check missing data pattern in st_pres...*

14. **7** (missing-rsvr-station-128)
   ```bash
   hermes chat -s powerelf-chatbi -q "检查一下st_rsvr_r表的606K2153号站在5月份有没有数据缺失" -Q
   ```
   *预期：Provider calls powerelf-data-governance to check missing data for station 606K21...*

15. **8** (missing-pptn-june-drop)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pptn_r表6月份的数据量从5月的4万7千条骤降到880条，是不是有大量缺失？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to investigate massive data volume drop ...*

16. **9** (river-table-empty)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_river_r表怎么一条记录都没有？河道水位监测是不是出问题了？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to flag st_river_r empty table as data c...*

17. **10** (offline-max-907h)
   ```bash
   hermes chat -s powerelf-chatbi -q "有哪些设备离线超过30天了？帮我查一下离线最严重的设备" -Q
   ```
   *预期：Provider calls powerelf-data-governance to find devices offline >720h (equipment...*

18. **11** (offline-equipment-104)
   ```bash
   hermes chat -s powerelf-chatbi -q "西坝咀雨量计(设备104)当前是否在线？离线多久了？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to check online status of equipment 104 ...*

19. **12** (offline-equipment-239)
   ```bash
   hermes chat -s powerelf-chatbi -q "设备239已经离线900多个小时了，这正常吗？什么级别的告警？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze equipment 239 offline 907h → ...*

20. **13** (offline-mttr-calculation)
   ```bash
   hermes chat -s powerelf-chatbi -q "计算最近30天所有设备的平均修复时间MTTR" -Q
   ```
   *预期：Provider calls powerelf-data-governance to calculate MTTR from eq_equip_offline_...*

21. **14** (offline-duration-grading)
   ```bash
   hermes chat -s powerelf-chatbi -q "对当前离线的设备按离线时长做分级，哪些是CRITICAL级别的？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to classify offline devices by duration ...*

22. **15** (quality-score-equipment-139)
   ```bash
   hermes chat -s powerelf-chatbi -q "给振弦渗压计E01(设备139)做一下5月份的数据质量评分" -Q
   ```
   *预期：Provider calls powerelf-data-governance to score equipment 139 (振弦渗压计E01) for Ma...*

23. **16** (quality-compare-139-140)
   ```bash
   hermes chat -s powerelf-chatbi -q "对比设备139(状态正常)和设备140(状态异常)的5月份数据质量评分" -Q
   ```
   *预期：Provider calls powerelf-data-governance to compare quality scores between equipm...*

24. **17** (quality-ranking-low-scores)
   ```bash
   hermes chat -s powerelf-chatbi -q "哪些设备的5月份质量评分低于60分？列出需要重点关注的设备" -Q
   ```
   *预期：Provider calls powerelf-data-governance to filter devices with quality score <60*

25. **18** (quality-trend-weekly)
   ```bash
   hermes chat -s powerelf-chatbi -q "本周的数据质量趋势怎么样？和上周比是变好了还是变差了？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to compare weekly quality trends*

26. **19** (stagnation-pressure-e01)
   ```bash
   hermes chat -s powerelf-chatbi -q "振弦渗压计E01(设备139)最近几天的数值一直没变过，是不是卡滞了？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to detect stagnation on equipment 139*

27. **20** (stagnation-all-may)
   ```bash
   hermes chat -s powerelf-chatbi -q "检测5月份所有传感器有没有数据卡滞的异常" -Q
   ```
   *预期：Provider calls powerelf-data-governance to batch detect stagnation across all se...*

28. **21** (rsvr-june-data-stoppage)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表6月份只有351条记录，7月份才9条，之前每个月都是2-5万条，数据采集是不是停了？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to investigate catastrophic data volume ...*

29. **22** (gnss-june-drop)
   ```bash
   hermes chat -s powerelf-chatbi -q "dsm_dfr_srvrds_srhrds表6月份数据从3001条骤降到272条，这个采集异常是什么原因？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze GNSS data collection drop in ...*

30. **23** (interpolation-rsvr-missing)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_rsvr_r表中606K2153站水位数据有缺失，帮我用插值补全" -Q
   ```
   *预期：Provider calls powerelf-data-governance to interpolate missing water level data ...*

31. **24** (interpolation-pressure-linear)
   ```bash
   hermes chat -s powerelf-chatbi -q "【假设场景·无需查库】st_pressure_r表5月1日到10日连续缺失了240条数据，用线性插值补上" -Q
   ```
   *预期：Provider calls powerelf-data-governance to linearly interpolate 240 missing pres...*

32. **25** (correlation-pressure-percolation)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_pressure_r的water_pressure上升了但st_percolation_r的渗流却下降了，这个物理矛盾怎么解释？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to detect pressure-percolation correlati...*

33. **26** (correlation-rainfall-waterlevel)
   ```bash
   hermes chat -s powerelf-chatbi -q "5月18日下了120mm的暴雨，但水位没怎么涨，数据是不是有问题？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze rainfall-waterlevel correlati...*

34. **27** (extreme-event-vs-anomaly-may15)
   ```bash
   hermes chat -s powerelf-chatbi -q "5月15日水位从440突然跳到500，是真实事件还是传感器故障？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to distinguish extreme event vs sensor a...*

35. **28** (extreme-event-jan-0p029)
   ```bash
   hermes chat -s powerelf-chatbi -q "1月份水位出现0.029米的极端低值，是传感器坏了还是真实的水位下降？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to classify rz=0.029 as equipment anomal...*

36. **29** (flood-data-stale)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_flood_r表的最新数据还是2025年11月的，已经过期7个多月了，这个数据时效性问题严重吗？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to flag st_flood_r data staleness (last ...*

37. **30** (report-daily-quality)
   ```bash
   hermes chat -s powerelf-chatbi -q "生成昨天的数据质量日报" -Q
   ```
   *预期：Provider calls powerelf-data-governance to generate daily data quality report*

38. **31** (report-monthly-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "出一份5月份的异常分析报告，汇总所有表的数据质量问题" -Q
   ```
   *预期：Provider calls powerelf-data-governance to generate monthly anomaly report for M...*

39. **32** (report-score-all-devices)
   ```bash
   hermes chat -s powerelf-chatbi -q "生成所有设备的5月份评分报告" -Q
   ```
   *预期：Provider calls powerelf-data-governance to generate score report for all devices...*

40. **33** (writeback-fix-anomaly)
   ```bash
   hermes chat -s powerelf-chatbi -q "把st_rsvr_r表中检测到的水位异常值修复后写回数据库" -Q
   ```
   *预期：Provider calls powerelf-data-governance to write back fixed anomaly data to eq_d...*

41. **34** (writeback-fill-missing)
   ```bash
   hermes chat -s powerelf-chatbi -q "把st_pressure_r表缺失的数据插值补全后写回eq_data_missing_record" -Q
   ```
   *预期：Provider calls powerelf-data-governance to write back filled missing data*

42. **35** (writeback-offline-status)
   ```bash
   hermes chat -s powerelf-chatbi -q "设备104(西坝咀雨量计)确认已离线，更新设备状态并创建离线记录" -Q
   ```
   *预期：Provider calls powerelf-data-governance to mark equipment 104 offline and create...*

43. **36** (device-context-equipment-140)
   ```bash
   hermes chat -s powerelf-chatbi -q "设备140(振弦渗压计E02)状态异常，查一下它的历史记录和运维建议" -Q
   ```
   *预期：Provider calls powerelf-data-governance to retrieve context for equipment 140 an...*

44. **37** (device-context-offline-239)
   ```bash
   hermes chat -s powerelf-chatbi -q "设备239已经离线900多小时了，查一下这个设备的详细信息，给出处理建议" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze equipment 239 (907h offline) ...*

45. **38** (missing-pressure-134-10days)
   ```bash
   hermes chat -s powerelf-chatbi -q "设备134(st_pressure_r)从5月1日到10日连续10天没有数据，共缺失240条，这是怎么回事？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to investigate continuous 10-day data ga...*

46. **39** (anomaly-stats-overview)
   ```bash
   hermes chat -s powerelf-chatbi -q "帮我看看stats_data_anomaly_daily表，哪个表的异常最多？整体趋势怎么样？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze anomaly stats across tables f...*

47. **40** (quality-scoring-by-manufacturer)
   ```bash
   hermes chat -s powerelf-chatbi -q "按设备厂商分组，生成5月份的厂商数据质量排名" -Q
   ```
   *预期：Provider calls powerelf-data-governance to rank manufacturers by data quality sc...*

48. **41** (stagnation-critical-level)
   ```bash
   hermes chat -s powerelf-chatbi -q "检测到渗压计连续24小时输出相同值，这个卡滞级别严重吗？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to assess stagnation severity (continuou...*

49. **42** (missing-pattern-recognition)
   ```bash
   hermes chat -s powerelf-chatbi -q "分析st_pressure_r表的数据缺失模式，是周期性的还是随机的？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to identify missing data pattern (period...*

50. **43** (interpolation-confidence)
   ```bash
   hermes chat -s powerelf-chatbi -q "插值补全后的数据置信度怎么样？能直接用吗？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to assess interpolation confidence level*

51. **44** (percolation-extreme-31)
   ```bash
   hermes chat -s powerelf-chatbi -q "st_percolation_r表的渗流值最大达到31.67，但平均值才0.57，这个极端值怎么判断？" -Q
   ```
   *预期：Provider calls powerelf-data-governance to analyze percolation=31.67 extreme val...*

#### powerelf-data-governance（79 题）

**✅ 可直接判分的问题**

1. **DG-P01** (可问-MAD 异常检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "XX 水库最近 7 天的水位数据有没有异常？" -Q
   ```
   *预期：MAD 异常检测*

2. **DG-P02** (可问-分指标阈值检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "帮我检测一下渗压数据的异常值" -Q
   ```
   *预期：分指标阈值检测*

3. **DG-P03** (可问-MAD + 变化率综合判定)
   ```bash
   hermes chat -s powerelf-data-governance -q "这些水位数据里有异常值吗？用 MAD 算法跑一下" -Q
   ```
   *预期：MAD + 变化率综合判定*

4. **DG-P04** (可问-指定时间窗口检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查一下 2026-06-01 到 2026-06-07 的雨量数据是否有异常" -Q
   ```
   *预期：指定时间窗口检测*

5. **DG-P05** (可问-变化率检测 + 综合判定)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个异常值是传感器故障还是真实的数据波动？" -Q
   ```
   *预期：变化率检测 + 综合判定*

6. **DG-P06** (可问-期望周期数比较)
   ```bash
   hermes chat -s powerelf-data-governance -q "XX 设备昨天的数据有没有缺失？" -Q
   ```
   *预期：期望周期数比较*

7. **DG-P07** (可问-指定表和测站)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查一下 st_rsvr_r 表 128 号测站最近一天的数据完整性" -Q
   ```
   *预期：指定表和测站*

8. **DG-P08** (可问-缺失模式识别)
   ```bash
   hermes chat -s powerelf-data-governance -q "分析这段时间的缺失模式，是周期性的还是随机的？" -Q
   ```
   *预期：缺失模式识别*

9. **DG-P09** (可问-INFO/WARNING/ERROR/CRITICAL 分级)
   ```bash
   hermes chat -s powerelf-data-governance -q "连续缺失达到哪个级别了？" -Q
   ```
   *预期：INFO/WARNING/ERROR/CRITICAL 分级*

10. **DG-P10** (可问-环比趋势分析)
   ```bash
   hermes chat -s powerelf-data-governance -q "最近一周缺失率趋势怎么样？" -Q
   ```
   *预期：环比趋势分析*

11. **DG-P11** (可问-四策略自适应插值)
   ```bash
   hermes chat -s powerelf-data-governance -q "帮我填补一下这段缺失的水位数据" -Q
   ```
   *预期：四策略自适应插值*

12. **DG-P12** (可问-指定插值策略)
   ```bash
   hermes chat -s powerelf-data-governance -q "用线性插值把昨天缺失的 3 个点补上" -Q
   ```
   *预期：指定插值策略*

13. **DG-P13** (可问-置信度评估（高/中/低）)
   ```bash
   hermes chat -s powerelf-data-governance -q "插值结果的置信度有多高？" -Q
   ```
   *预期：置信度评估（高/中/低）*

14. **DG-P14** (可问-置信度 >= 0.8 可直接使用)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个插值结果可以直接用吗？" -Q
   ```
   *预期：置信度 >= 0.8 可直接使用*

15. **DG-P15** (可问-样条插值推荐)
   ```bash
   hermes chat -s powerelf-data-governance -q "这种周期性的水位数据适合用什么插值方法？" -Q
   ```
   *预期：样条插值推荐*

16. **DG-P16** (可问-三态判定（ONLINE/OFFLINE/ERROR）)
   ```bash
   hermes chat -s powerelf-data-governance -q "XX 设备当前是否在线？" -Q
   ```
   *预期：三态判定（ONLINE/OFFLINE/ERROR）*

17. **DG-P17** (可问-离线时长分级)
   ```bash
   hermes chat -s powerelf-data-governance -q "哪些设备离线超过 24 小时了？" -Q
   ```
   *预期：离线时长分级*

18. **DG-P18** (可问-MTTR 计算)
   ```bash
   hermes chat -s powerelf-data-governance -q "最近一个月设备的平均修复时间（MTTR）是多少？" -Q
   ```
   *预期：MTTR 计算*

19. **DG-P19** (可问-批量检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查一下各设备的在线状态" -Q
   ```
   *预期：批量检测*

20. **DG-P20** (可问-时长计算 + 分级告警)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个设备离线多久了？" -Q
   ```
   *预期：时长计算 + 分级告警*

21. **DG-P21** (可问-四维度加权评分)
   ```bash
   hermes chat -s powerelf-data-governance -q "XX 设备的数据质量评分是多少？" -Q
   ```
   *预期：四维度加权评分*

22. **DG-P22** (可问-厂商排名)
   ```bash
   hermes chat -s powerelf-data-governance -q "本周数据质量排名怎么样？哪些厂商表现好？" -Q
   ```
   *预期：厂商排名*

23. **DG-P23** (可问-趋势分析（改善/恶化/稳定）)
   ```bash
   hermes chat -s powerelf-data-governance -q "和上周比，数据质量是变好了还是变差了？" -Q
   ```
   *预期：趋势分析（改善/恶化/稳定）*

24. **DG-P24** (可问-较差等级设备筛选)
   ```bash
   hermes chat -s powerelf-data-governance -q "哪些设备评分低于 60 分需要重点关注？" -Q
   ```
   *预期：较差等级设备筛选*

25. **DG-P25** (可问-日报生成)
   ```bash
   hermes chat -s powerelf-data-governance -q "数据质量日报是什么情况？" -Q
   ```
   *预期：日报生成*

26. **DG-P26** (可问-连续相同值检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个传感器的数值连续好几天没变了，是不是卡住了？" -Q
   ```
   *预期：连续相同值检测*

27. **DG-P27** (可问-批量检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检测一下所有传感器有没有卡滞异常" -Q
   ```
   *预期：批量检测*

28. **DG-P28** (可问-INFO/WARNING/ERROR/CRITICAL 分级)
   ```bash
   hermes chat -s powerelf-data-governance -q "卡滞级别严重吗？" -Q
   ```
   *预期：INFO/WARNING/ERROR/CRITICAL 分级*

29. **DG-P29** (可问-极端事件 vs 异常区分)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个高水位是汛期的正常现象还是数据异常？" -Q
   ```
   *预期：极端事件 vs 异常区分*

30. **DG-P30** (可问-多维度判断)
   ```bash
   hermes chat -s powerelf-data-governance -q "现在是汛期，这个水位骤升合理吗？有没有降雨数据支撑？" -Q
   ```
   *预期：多维度判断*

31. **DG-P31** (可问-维护窗口识别)
   ```bash
   hermes chat -s powerelf-data-governance -q "凌晨 2-4 点的异常值是不是维护窗口导致的？" -Q
   ```
   *预期：维护窗口识别*

32. **DG-P32** (可问-物理矛盾检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "渗压上升了但渗流下降了，这合理吗？" -Q
   ```
   *预期：物理矛盾检测*

33. **DG-P33** (可问-水位-渗流矛盾规则)
   ```bash
   hermes chat -s powerelf-data-governance -q "水位涨了 1 米但渗流反而减少了，是不是传感器有问题？" -Q
   ```
   *预期：水位-渗流矛盾规则*

34. **DG-P34** (可问-降雨-水位矛盾规则)
   ```bash
   hermes chat -s powerelf-data-governance -q "降雨 50mm 但水位没涨反降，数据有问题吗？" -Q
   ```
   *预期：降雨-水位矛盾规则*

35. **DG-P35** (可问-历史缺陷查询)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个设备之前有没有类似的故障记录？" -Q
   ```
   *预期：历史缺陷查询*

36. **DG-P36** (可问-维保周期检查)
   ```bash
   hermes chat -s powerelf-data-governance -q "设备上次维护是什么时候？是不是该保养了？" -Q
   ```
   *预期：维保周期检查*

37. **DG-P37** (可问-P0/P1/P2/P3 优先级建议)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个异常需要什么级别的响应？" -Q
   ```
   *预期：P0/P1/P2/P3 优先级建议*

38. **DG-P38** (可问-智能运维建议生成)
   ```bash
   hermes chat -s powerelf-data-governance -q "结合设备信息和知识库，这个异常该怎么处理？" -Q
   ```
   *预期：智能运维建议生成*

39. **DG-P39** (可问-`generate_daily_report()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "生成昨天的数据质量日报" -Q
   ```
   *预期：`generate_daily_report()`*

40. **DG-P40** (可问-`generate_anomaly_report()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "出一份本月的异常分析报告" -Q
   ```
   *预期：`generate_anomaly_report()`*

41. **DG-P41** (可问-`to_pdf()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "导出为 PDF 格式存档" -Q
   ```
   *预期：`to_pdf()`*

42. **DG-P42** (可问-`generate_score_report()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "生成一份所有设备的评分报告" -Q
   ```
   *预期：`generate_score_report()`*

43. **DG-P43** (可问-`fix_anomaly()` / `fill_missing()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "把插值修复的结果写回数据库" -Q
   ```
   *预期：`fix_anomaly()` / `fill_missing()`*

44. **DG-P44** (可问-`update_device_status(0)`)
   ```bash
   hermes chat -s powerelf-data-governance -q "标记这个设备为离线状态" -Q
   ```
   *预期：`update_device_status(0)`*

45. **DG-P45** (可问-`create_offline_record()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "自动创建一条离线记录" -Q
   ```
   *预期：`create_offline_record()`*

46. **DG-P46** (可问-`batch_fix_anomalies()`)
   ```bash
   hermes chat -s powerelf-data-governance -q "批量修复多个异常点" -Q
   ```
   *预期：`batch_fix_anomalies()`*

47. **DG-N01** (不可问-XX 水库当前水位是多少？)
   ```bash
   hermes chat -s powerelf-data-governance -q "XX 水库当前水位是多少？" -Q
   ```
   *预期：应路由到 `water-situation` / `powerelf-chatbi`；原因：查实时水位值不是查数据质量*

48. **DG-N02** (不可问-展示一下最近一周的水位变化曲线)
   ```bash
   hermes chat -s powerelf-data-governance -q "展示一下最近一周的水位变化曲线" -Q
   ```
   *预期：应路由到 `water-situation` / `powerelf-chatbi` / `powerelf-monitor`；原因：水位趋势可视化（非质量检测...*

49. **DG-N03** (不可问-这个水位超过警戒线了吗？)
   ```bash
   hermes chat -s powerelf-data-governance -q "这个水位超过警戒线了吗？" -Q
   ```
   *预期：应路由到 `water-warning` / `powerelf-early-warning`；原因：预警规则判断*

50. **DG-N04** (不可问-今天雨量站降雨量多少？)
   ```bash
   hermes chat -s powerelf-data-governance -q "今天雨量站降雨量多少？" -Q
   ```
   *预期：应路由到 `water-situation` / `powerelf-chatbi`；原因：实时数据查询*

51. **DG-N05** (不可问-闸门当前开度是多少？泵站是否在运行？)
   ```bash
   hermes chat -s powerelf-data-governance -q "闸门当前开度是多少？泵站是否在运行？" -Q
   ```
   *预期：应路由到 `gate-pump-operation` / `powerelf-monitor`；原因：设备运行状态查询*

52. **DG-N06** (不可问-查一下 XX 表的数据)
   ```bash
   hermes chat -s powerelf-data-governance -q "查一下 XX 表的数据" -Q
   ```
   *预期：应路由到 `powerelf-chatbi`；原因：纯数据查询，不涉及质量分析*

53. **DG-N07** (不可问-帮我发一个预警通知)
   ```bash
   hermes chat -s powerelf-data-governance -q "帮我发一个预警通知" -Q
   ```
   *预期：应路由到 `powerelf-early-warning`；原因：预警分发，非质量检测*

54. **T9.1** (T9.1 数据质量日报)
   ```bash
   hermes chat -s powerelf-data-governance -q "生成2026年5月15日的数据质量日报。" -Q
   ```
   *预期：*

55. **T9.2** (T9.2 异常分析报告)
   ```bash
   hermes chat -s powerelf-data-governance -q "生成5月份的异常分析报告。" -Q
   ```
   *预期：*

56. **T9.3** (T9.3 设备评分报告（PDF）)
   ```bash
   hermes chat -s powerelf-data-governance -q "输出所有设备的评分报告PDF版本。" -Q
   ```
   *预期：*

57. **T10.1** (T10.1 异常修复回写)
   ```bash
   hermes chat -s powerelf-data-governance -q "对T1.1检出的水位异常，用插值修复后写回eq_data_anomaly_record。" -Q
   ```
   *预期：*

58. **T10.2** (T10.2 缺失填补回写)
   ```bash
   hermes chat -s powerelf-data-governance -q "对T2.1检出的缺失，用插值填补后写回eq_data_missing_record。" -Q
   ```
   *预期：*

59. **T10.3** (T10.3 设备状态更新)
   ```bash
   hermes chat -s powerelf-data-governance -q "将离线设备104(西坝咀雨量计)的状态标记为离线。" -Q
   ```
   *预期：*

**⚠️  需人工判分的问题**

1. **T1.1** (T1.1 128号测站水位异常检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "请检测128号测站(st_rsvr_r)最近1周的水位(rz)数据是否有异常。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

2. **T1.2** (T1.2 416号测站渗压异常检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检测416号测站(st_pressure_r)渗压数据最近7天的异常值。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

3. **T1.3** (T1.3 全量水位MAD检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "对st_rsvr_r表的rz字段做全量MAD异常检测（5月份）。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

4. **T1.4** (T1.4 雨量异常检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检测雨量数据(st_pptn_r)最近7天是否有异常。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

5. **T2.1** (T2.1 128号测站缺失检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查128号测站2026年5月的st_rsvr_r数据是否有缺失。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

6. **T2.2** (T2.2 渗压表缺失模式分析)
   ```bash
   hermes chat -s powerelf-data-governance -q "分析st_pressure_r表416号测站2026年5月的缺失模式。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

7. **T2.3** (T2.3 缺失率趋势)
   ```bash
   hermes chat -s powerelf-data-governance -q "分析最近一周(stats_data_missing_daily)的缺失率趋势。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

8. **T3.1** (T3.1 单设备离线判定)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查设备104(西坝咀雨量计)当前是否离线。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

9. **T3.2** (T3.2 批量离线检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "哪些设备离线超过24小时了？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

10. **T3.3** (T3.3 MTTR 计算)
   ```bash
   hermes chat -s powerelf-data-governance -q "计算最近30天的平均修复时间(MTTR)。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

11. **T3.4** (T3.4 离线时长分级)
   ```bash
   hermes chat -s powerelf-data-governance -q "对当前离线的设备按离线时长分级。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

12. **T4.1** (T4.1 单设备评分)
   ```bash
   hermes chat -s powerelf-data-governance -q "对设备139(振弦渗压计E01)做2026年5月的质量评分。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

13. **T4.2** (T4.2 设备评分对比)
   ```bash
   hermes chat -s powerelf-data-governance -q "对比设备140(振弦渗压计E02, status=2异常)和139(同批次, status=0正常)的评分。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

14. **T4.3** (T4.3 厂商质量排名)
   ```bash
   hermes chat -s powerelf-data-governance -q "生成2026年5月的厂商质量排名。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

15. **T5.1** (T5.1 自适应插值)
   ```bash
   hermes chat -s powerelf-data-governance -q "2026年5月st_pressure_r表416号测站在water_pressure字段上有缺失值，
请用自适应策略填补。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

16. **T5.2** (T5.2 水位突变判定与修复建议)
   ```bash
   hermes chat -s powerelf-data-governance -q "对128号测站5月15日水位突变点(500→440)，
判断是需要修复的异常还是真实事件。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

17. **T6.1** (T6.1 传感器卡滞检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检测5月下旬是否有传感器卡滞——多台渗压计连续输出相同值。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

18. **T7.1** (T7.1 渗压-渗流矛盾检测)
   ```bash
   hermes chat -s powerelf-data-governance -q "检查416号测站5月29日渗压数据是否存在物理矛盾。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

19. **T8.1** (T8.1 汛期 vs 异常区分)
   ```bash
   hermes chat -s powerelf-data-governance -q "416号测站5/29渗压450 vs 5/28的430.5，区分是极端事件还是传感器异常。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

20. **T11.1** (T11.1 智能运维建议)
   ```bash
   hermes chat -s powerelf-data-governance -q "设备140(振弦渗压计E02, status=2)出现异常，查询设备上下文并给出运维建议。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

#### powerelf-early-warning（103 题）

**✅ 可直接判分的问题**

1. **Q001** (Q1: 未确认告警数量)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，未确认告警数量。（4条未确认告警）" -Q
   ```
   *预期：场景：场景1；数据要求：4条未确认告警*

2. **Q002** (Q2: 各级别告警分布)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，各级别告警分布。（4条不同级别告警）" -Q
   ```
   *预期：场景：场景1；数据要求：4条不同级别告警*

3. **Q003** (Q3: 最近3天告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，最近3天告警。（3条最近告警）" -Q
   ```
   *预期：场景：场景1；数据要求：3条最近告警*

4. **Q004** (Q4: 特定测站告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，特定测站告警。（使用TEST_ST001）" -Q
   ```
   *预期：场景：场景1；数据要求：使用TEST_ST001*

5. **Q005** (Q5: 红色告警查询)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，红色告警查询。（1条红色告警）" -Q
   ```
   *预期：场景：场景1；数据要求：1条红色告警*

6. **Q006** (Q6: 告警趋势)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，告警趋势。（分布在不同日期）" -Q
   ```
   *预期：场景：场景1；数据要求：分布在不同日期*

7. **Q007** (Q7: 告警规则)
   ```bash
   hermes chat -s powerelf-early-warning -q "在-场景下，告警规则。（使用现有规则）" -Q
   ```
   *预期：场景：-；数据要求：使用现有规则*

8. **Q008** (Q8: 规则详情)
   ```bash
   hermes chat -s powerelf-early-warning -q "在-场景下，规则详情。（使用现有规则）" -Q
   ```
   *预期：场景：-；数据要求：使用现有规则*

9. **Q009** (Q9: 测站排名)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，测站排名。（多个测站）" -Q
   ```
   *预期：场景：场景1；数据要求：多个测站*

10. **Q010** (Q10: 小时分布)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，小时分布。（分布在不同时段）" -Q
   ```
   *预期：场景：场景1；数据要求：分布在不同时段*

11. **Q011** (Q11: 设备离线)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景6场景下，设备离线。（3条离线告警）" -Q
   ```
   *预期：场景：场景6；数据要求：3条离线告警*

12. **Q012** (Q12: 确认率)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，确认率。（已确认+未确认）" -Q
   ```
   *预期：场景：场景1；数据要求：已确认+未确认*

13. **Q013** (Q13: 告警原因分析)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,8场景下，告警原因分析。（告警+水位数据）" -Q
   ```
   *预期：场景：场景1,8；数据要求：告警+水位数据*

14. **Q014** (Q14: 水位变化趋势)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，水位变化趋势。（24小时水位数据）" -Q
   ```
   *预期：场景：场景8；数据要求：24小时水位数据*

15. **Q015** (Q15: 降雨关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景9场景下，降雨关联。（降雨数据）" -Q
   ```
   *预期：场景：场景9；数据要求：降雨数据*

16. **Q016** (Q16: 渗流异常)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景10,11场景下，渗流异常。（渗压+渗流数据）" -Q
   ```
   *预期：场景：场景10,11；数据要求：渗压+渗流数据*

17. **Q017** (Q17: 设备故障)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景6场景下，设备故障。（设备离线告警）" -Q
   ```
   *预期：场景：场景6；数据要求：设备离线告警*

18. **Q018** (Q18: 规则触发)
   ```bash
   hermes chat -s powerelf-early-warning -q "在-场景下，规则触发。（使用现有规则）" -Q
   ```
   *预期：场景：-；数据要求：使用现有规则*

19. **Q019** (Q19: 历史对比)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，历史对比。（历史告警数据）" -Q
   ```
   *预期：场景：场景1；数据要求：历史告警数据*

20. **Q020** (Q20: 综合诊断)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,8,9场景下，综合诊断。（多源数据）" -Q
   ```
   *预期：场景：场景1,8,9；数据要求：多源数据*

21. **Q021** (Q21: 处理建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，处理建议。（告警数据）" -Q
   ```
   *预期：场景：场景1；数据要求：告警数据*

22. **Q022** (Q22: 水位降雨关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8,9场景下，水位降雨关联。（水位+降雨）" -Q
   ```
   *预期：场景：场景8,9；数据要求：水位+降雨*

23. **Q023** (Q23: 多测站关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，多测站关联。（多测站告警）" -Q
   ```
   *预期：场景：场景1；数据要求：多测站告警*

24. **Q024** (Q24: 水位渗流关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8,10,11场景下，水位渗流关联。（水位+渗压+渗流）" -Q
   ```
   *预期：场景：场景8,10,11；数据要求：水位+渗压+渗流*

25. **Q025** (Q25: 设备数据关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景6场景下，设备数据关联。（设备离线）" -Q
   ```
   *预期：场景：场景6；数据要求：设备离线*

26. **Q026** (Q26: 时间规律)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，时间规律。（时间序列）" -Q
   ```
   *预期：场景：场景1；数据要求：时间序列*

27. **Q027** (Q27: 测站关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，测站关联。（多测站）" -Q
   ```
   *预期：场景：场景1；数据要求：多测站*

28. **Q028** (Q28: 三域关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2场景下，三域关联。（水位+降雨+渗流）" -Q
   ```
   *预期：场景：场景2；数据要求：水位+降雨+渗流*

29. **Q029** (Q29: 水位预测)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，水位预测。（水位趋势）" -Q
   ```
   *预期：场景：场景8；数据要求：水位趋势*

30. **Q030** (Q30: 预警升级)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景5场景下，预警升级。（升级告警）" -Q
   ```
   *预期：场景：场景5；数据要求：升级告警*

31. **Q031** (Q31: 未来告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8,9场景下，未来告警。（水位+降雨）" -Q
   ```
   *预期：场景：场景8,9；数据要求：水位+降雨*

32. **Q032** (Q32: 告警解除)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景4场景下，告警解除。（持续告警）" -Q
   ```
   *预期：场景：场景4；数据要求：持续告警*

33. **Q033** (Q33: 告警升级)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景5场景下，告警升级。（升级告警）" -Q
   ```
   *预期：场景：场景5；数据要求：升级告警*

34. **Q034** (Q34: 趋势预测)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，趋势预测。（水位数据）" -Q
   ```
   *预期：场景：场景8；数据要求：水位数据*

35. **Q035** (Q35: 水位正常性)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，水位正常性。（水位数据）" -Q
   ```
   *预期：场景：场景8；数据要求：水位数据*

36. **Q062** (Q62: 整体风险)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2场景下，整体风险。（所有告警）" -Q
   ```
   *预期：场景：场景1,2；数据要求：所有告警*

37. **Q063** (Q63: 安全状态)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2,6场景下，安全状态。（所有告警）" -Q
   ```
   *预期：场景：场景1,2,6；数据要求：所有告警*

38. **Q064** (Q64: 大坝安全)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2,8,9,10,11场景下，大坝安全。（三域数据）" -Q
   ```
   *预期：场景：场景2,8,9,10,11；数据要求：三域数据*

39. **Q065** (Q65: 告警原因)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景4场景下，告警原因。（持续告警）" -Q
   ```
   *预期：场景：场景4；数据要求：持续告警*

40. **Q066** (Q66: 水位预测)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，水位预测。（水位数据）" -Q
   ```
   *预期：场景：场景8；数据要求：水位数据*

41. **Q067** (Q67: 预案触发)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2场景下，预案触发。（高风险数据）" -Q
   ```
   *预期：场景：场景2；数据要求：高风险数据*

42. **Q068** (Q68: 测站排名)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，测站排名。（多测站）" -Q
   ```
   *预期：场景：场景1；数据要求：多测站*

43. **Q069** (Q69: 值班关注)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2场景下，值班关注。（所有告警）" -Q
   ```
   *预期：场景：场景1,2；数据要求：所有告警*

44. **Q070** (Q70: 测站分布)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，测站分布。（多测站）" -Q
   ```
   *预期：场景：场景1；数据要求：多测站*

45. **Q071** (Q71: 类型分布)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，类型分布。（多类型）" -Q
   ```
   *预期：场景：场景1；数据要求：多类型*

46. **Q072** (Q72: 最近告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1场景下，最近告警。（最近告警）" -Q
   ```
   *预期：场景：场景1；数据要求：最近告警*

47. **Q073** (Q73: 告警风暴)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景3场景下，告警风暴。（60条告警）" -Q
   ```
   *预期：场景：场景3；数据要求：60条告警*

48. **Q074** (Q74: 水位降雨关联)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8,9场景下，水位降雨关联。（水位+降雨）" -Q
   ```
   *预期：场景：场景8,9；数据要求：水位+降雨*

49. **Q075** (Q75: 大坝综合风险)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2,8,9,10,11场景下，大坝综合风险。（三域数据）" -Q
   ```
   *预期：场景：场景2,8,9,10,11；数据要求：三域数据*

50. **Q076** (Q76: 设备可靠性)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景6场景下，设备可靠性。（设备离线）" -Q
   ```
   *预期：场景：场景6；数据要求：设备离线*

51. **Q077** (Q77: 气象洪水)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景12场景下，气象洪水。（气象预警）" -Q
   ```
   *预期：场景：场景12；数据要求：气象预警*

52. **Q078** (Q78: 整体风险)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2场景下，整体风险。（所有告警）" -Q
   ```
   *预期：场景：场景1,2；数据要求：所有告警*

53. **Q079** (Q79: 评估依据)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2场景下，评估依据。（风险因素）" -Q
   ```
   *预期：场景：场景1,2；数据要求：风险因素*

54. **Q080** (Q80: 风险升级)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景5场景下，风险升级。（升级告警）" -Q
   ```
   *预期：场景：场景5；数据要求：升级告警*

55. **Q081** (Q81: 降低风险)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景1,2场景下，降低风险。（风险建议）" -Q
   ```
   *预期：场景：场景1,2；数据要求：风险建议*

56. **Q082** (Q82: 水位预测)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8场景下，水位预测。（水位数据）" -Q
   ```
   *预期：场景：场景8；数据要求：水位数据*

57. **Q083** (Q83: 告警解除)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景4场景下，告警解除。（持续告警）" -Q
   ```
   *预期：场景：场景4；数据要求：持续告警*

58. **Q084** (Q84: 未来24小时)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景8,9场景下，未来24小时。（水位+降雨）" -Q
   ```
   *预期：场景：场景8,9；数据要求：水位+降雨*

59. **Q085** (Q85: 启动预案)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2场景下，启动预案。（高风险数据）" -Q
   ```
   *预期：场景：场景2；数据要求：高风险数据*

60. **Q086** (Q86: 预案选择)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2场景下，预案选择。（高风险数据）" -Q
   ```
   *预期：场景：场景2；数据要求：高风险数据*

61. **Q087** (Q87: 执行步骤)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景2场景下，执行步骤。（高风险数据）" -Q
   ```
   *预期：场景：场景2；数据要求：高风险数据*

62. **Q088** (Q88: 无告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在-场景下，无告警。（清理后测试）" -Q
   ```
   *预期：场景：-；数据要求：清理后测试*

63. **Q089** (Q89: 不存在测站)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景13场景下，不存在测站。（无数据）" -Q
   ```
   *预期：场景：场景13；数据要求：无数据*

64. **Q090** (Q90: 数据缺失)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景14场景下，数据缺失。（告警无水位）" -Q
   ```
   *预期：场景：场景14；数据要求：告警无水位*

65. **Q091** (Q91: 告警过多)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景3场景下，告警过多。（60条告警）" -Q
   ```
   *预期：场景：场景3；数据要求：60条告警*

66. **Q092** (Q92: 查询超时)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景3场景下，查询超时。（大量数据）" -Q
   ```
   *预期：场景：场景3；数据要求：大量数据*

67. **Q093** (Q93: 气象不可用)
   ```bash
   hermes chat -s powerelf-early-warning -q "在-场景下，气象不可用。（跳过测试）" -Q
   ```
   *预期：场景：-；数据要求：跳过测试*

68. **Q094** (Q94: 蓝色告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景7场景下，蓝色告警。（3条蓝色）" -Q
   ```
   *预期：场景：场景7；数据要求：3条蓝色*

69. **Q095** (Q95: 单条红色)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景7场景下，单条红色。（1条红色）" -Q
   ```
   *预期：场景：场景7；数据要求：1条红色*

70. **Q096** (Q96: 边界值)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景7场景下，边界值。（边界评分）" -Q
   ```
   *预期：场景：场景7；数据要求：边界评分*

71. **Q097** (Q97: 已确认告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景7场景下，已确认告警。（3条已确认）" -Q
   ```
   *预期：场景：场景7；数据要求：3条已确认*

72. **Q098** (Q98: 跨日告警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景15场景下，跨日告警。（跨日数据）" -Q
   ```
   *预期：场景：场景15；数据要求：跨日数据*

73. **Q102** (Q102: 暴雨预警)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景12场景下，暴雨预警。（气象预警）" -Q
   ```
   *预期：场景：场景12；数据要求：气象预警*

74. **Q103** (Q103: 天气影响)
   ```bash
   hermes chat -s powerelf-early-warning -q "在场景12场景下，天气影响。（气象+水位）" -Q
   ```
   *预期：场景：场景12；数据要求：气象+水位*

**⚠️  需人工判分的问题**

1. **Q036** (Q36: 告警处置建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "当前最紧急的未确认告警是哪些？给出优先处置建议。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

2. **Q037** (Q37: 处置优先级排序)
   ```bash
   hermes chat -s powerelf-early-warning -q "结合告警级别、持续时间和影响范围，对当前告警做处置优先级排序。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

3. **Q038** (Q38: 值班关注清单)
   ```bash
   hermes chat -s powerelf-early-warning -q "今天值班需要重点关注的告警有哪些？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

4. **Q039** (Q39: 处置动作建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "对 I 级红色告警给出初步处置动作建议（人工核实/转派/忽略）。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

5. **Q040** (Q40: 处置验证)
   ```bash
   hermes chat -s powerelf-early-warning -q "告警处置后如何验证已解除？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

6. **Q041** (Q41: 重复告警检测)
   ```bash
   hermes chat -s powerelf-early-warning -q "最近 7 天有哪些重复告警（同测站/同类型/短时间窗）？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

7. **Q042** (Q42: 告警合并建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "这些相似告警是否可以合并？给出合并建议。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

8. **Q043** (Q43: 高频告警分析)
   ```bash
   hermes chat -s powerelf-early-warning -q "哪个告警触发最频繁？TOP 10 高频告警是哪些？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

9. **Q044** (Q44: 告警风暴检测)
   ```bash
   hermes chat -s powerelf-early-warning -q "当前是否处于告警风暴状态？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

10. **Q045** (Q45: 合并策略建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "针对当前告警模式，建议怎样的合并/去重策略？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

11. **Q046** (Q46: 升级决策建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "这条告警是否满足升级条件？是否需要升级？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

12. **Q047** (Q47: 升级通知生成)
   ```bash
   hermes chat -s powerelf-early-warning -q "为这条升级告警生成升级通知模板。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

13. **Q048** (Q48: 升级策略分析)
   ```bash
   hermes chat -s powerelf-early-warning -q "当前升级规则是否合理？给出优化建议。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

14. **Q049** (Q49: 升级历史查询)
   ```bash
   hermes chat -s powerelf-early-warning -q "最近 30 天有哪些告警被升级过？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

15. **Q050** (Q50: 升级级别建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "该告警应升级到哪一级、通知哪些人？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

16. **Q051** (Q51: 告警恢复判定)
   ```bash
   hermes chat -s powerelf-early-warning -q "这条告警当前是否已恢复？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

17. **Q052** (Q52: 恢复处置建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "告警恢复后还需要做什么？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

18. **Q053** (Q53: 状态机查询)
   ```bash
   hermes chat -s powerelf-early-warning -q "该告警当前处于状态机的哪个状态？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

19. **Q054** (Q54: 状态流转建议)
   ```bash
   hermes chat -s powerelf-early-warning -q "该告警下一步应流转到哪个状态？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

20. **Q055** (Q55: 恢复率统计)
   ```bash
   hermes chat -s powerelf-early-warning -q "最近一个月告警恢复成功率是多少？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

21. **Q056** (Q56: 生命周期分析)
   ```bash
   hermes chat -s powerelf-early-warning -q "这条告警从产生到恢复的完整轨迹是怎样的？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

22. **Q057** (Q57: 操作历史查询)
   ```bash
   hermes chat -s powerelf-early-warning -q "最近一周谁处理了哪些告警？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

23. **Q058** (Q58: 处理效率分析)
   ```bash
   hermes chat -s powerelf-early-warning -q "告警平均处理时长是多少？有没有超时未处理的？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

24. **Q059** (Q59: 操作人员绩效)
   ```bash
   hermes chat -s powerelf-early-warning -q "哪个操作人员处理告警最多/最快？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

25. **Q060** (Q60: 异常操作检测)
   ```bash
   hermes chat -s powerelf-early-warning -q "最近有没有异常操作记录（越权/非工作时间操作）？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

26. **Q061** (Q61: 审计汇总)
   ```bash
   hermes chat -s powerelf-early-warning -q "汇总本周告警处理情况（处理量/时效/升级/恢复）。" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

27. **Q099** (Q99: 组合边界判定)
   ```bash
   hermes chat -s powerelf-early-warning -q "多条边界条件同时满足（如水位恰好到警戒线且雨量临界）时如何判定？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

28. **Q100** (Q100: 跨域边界叠加)
   ```bash
   hermes chat -s powerelf-early-warning -q "水位边界 + 降雨边界叠加时，级别如何计算？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

29. **Q101** (Q101: 气象关联边界)
   ```bash
   hermes chat -s powerelf-early-warning -q "气象预警与本地告警在边界状态下如何联动？" -Q
   ```
   *注意：expected_output 为占位符，需人工核对*

#### powerelf-inspection（57 题）

**✅ 可直接判分的问题**

1. **EVAL1** (EVAL1: 渗压突变检出)
   ```bash
   hermes chat -s powerelf-inspection -q "渗压计416在5月20日有10kPa突变，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"渗压突变"和"kPa" | Fail: 输出不包含"突变"关键词*

2. **EVAL2** (EVAL2: 闸门异常检出)
   ```bash
   hermes chat -s powerelf-inspection -q "闸门站131在5月8日开度突变2.5m，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"闸门"和"突变" | Fail: 输出不包含闸门异常*

3. **EVAL3** (EVAL3: 泵站三相不平衡检出)
   ```bash
   hermes chat -s powerelf-inspection -q "泵站217在5月20日三相电流不平衡29%，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"不平衡"和百分比 | Fail: 输出不包含三相不平衡*

4. **EVAL4** (EVAL4: 水质超标检出)
   ```bash
   hermes chat -s powerelf-inspection -q "水质数据中氨氮2.0超标(标准<1.5)，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"氨氮"和"偏高"或"超标" | Fail: 输出不包含水质异常*

5. **EVAL5** (EVAL5: 白蚁重度危害检出)
   ```bash
   hermes chat -s powerelf-inspection -q "白蚁监测中有重度危害记录，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"重度"和CRITICAL级别 | Fail: 输出不包含重度危害*

6. **EVAL6** (EVAL6: 告警分析检出)
   ```bash
   hermes chat -s powerelf-inspection -q "I级告警167条，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"I级"和"167" | Fail: 输出不包含告警统计*

7. **EVAL7** (EVAL7: 漏检率检出)
   ```bash
   hermes chat -s powerelf-inspection -q "巡检完成率仅7.7%，漏检率超过20%，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"完成率"和"漏检" | Fail: 输出不包含巡检质量异常*

8. **EVAL8** (EVAL8: 设备离线率检出)
   ```bash
   hermes chat -s powerelf-inspection -q "设备离线率43%(55/128)，工具是否检出？" -Q
   ```
   *预期：Pass: 输出包含"离线率"和百分比 | Fail: 输出不包含设备状态异常*

9. **EVAL9** (EVAL9: 无误报)
   ```bash
   hermes chat -s powerelf-inspection -q "水库水情、位移监测、MAD统计、关联异常这4个维度是否正确报告OK？" -Q
   ```
   *预期：Pass: 输出包含"OK"和"CRITICAL"——水库水情/MAD统计/关联异常3个维度报OK无WARNING，位移维度报CRITICAL（GNSS测站97...*

10. **EVAL10** (EVAL10: 边界规则完整性)
   ```bash
   hermes chat -s powerelf-inspection -q "SKILL.md是否列出至少5条"必须人工确认"的场景和至少3条反例？" -Q
   ```
   *预期：Pass: 边界规则章节有5+场景和3+反例 | Fail: 不足5个场景或3个反例*

11. **WL-POS-1** (水库水情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9001, rz 序列 100.0→100.1→100.2→100.3→100.4→100.5（6点5次连续上升）" -Q
   ```
   *预期：min_level=WARNING; message_contains=连续上升 | 理由: 6 点窗口 5 次连续上升，达 consecutive_monot...*

12. **WL-NEG-1** (水库水情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9001, rz 序列 100.0→100.1→100.2→100.3→100.4→100.4（末点持平）" -Q
   ```
   *预期：no_finding_contains=连续上升 | 理由: 仅 4 次连续上升，阈值 5 次，差 1 不应触发*

13. **WL-POS-2** (水库水情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9001, 末条 inq=21.0, otq=10.0（比值 2.1）" -Q
   ```
   *预期：min_level=WARNING; message_contains=入库流量 | 理由: 入库/出库比 2.1 > 2，蓄水过快*

14. **WL-NEG-2** (水库水情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9001, 末条 inq=20.0, otq=10.0（比值恰 2.0）" -Q
   ```
   *预期：no_finding_contains=入库流量 | 理由: 比值恰等于阈值 2，判定为严格大于，不应触发*

15. **RAIN-POS-1** (雨量监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9002, 单时段 p=100.1mm" -Q
   ```
   *预期：min_level=CRITICAL; message_contains=红色预警 | 理由: 100.1mm > 红色阈值 100mm（ew_info_rul...*

16. **RAIN-NEG-1** (雨量监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9002, 单时段 p=29.9mm" -Q
   ```
   *预期：no_finding_contains=预警 | 理由: 29.9mm，蓝色阈值 30mm，差 0.1 不应触发任何预警级*

17. **PRES-POS-1** (渗压监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9003, water_pressure 序列 [50.0×9, 55.1]（末对上跳5.1kPa未回落→非spike）" -Q
   ```
   *预期：min_level=WARNING; message_contains=突变 | 理由: 5.1kPa > 突变阈值5kPa；末点未回落→非spike(不降级)...*

18. **PRES-NEG-1** (渗压监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9003, water_pressure 相邻两点 50.0→54.9（变化 4.9kPa）" -Q
   ```
   *预期：no_finding_contains=突变 | 理由: 变化 4.9kPa，阈值 5kPa，差 0.1 不应触发*

19. **PRES-SPIKE-1** (渗压监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9003, water_pressure 序列 [50.0×5, 85.0, 50.0×4]（中间单点85尖峰，末点50已回落=spike；35kPa远超5阈值）" -Q
   ```
   *预期：max_level=INFO; message_contains=突变; pattern=spike; no_diagnosis=True | 理由: 单点尖峰...*

20. **PERC-POS-1** (渗流监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9004, percolation 相邻 1.000→1.201（+20.1%）" -Q
   ```
   *预期：min_level=WARNING; message_contains=突变 | 理由: 20.1% > 突变阈值 20%*

21. **PERC-NEG-1** (渗流监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9004, percolation 相邻 1.000→1.199（+19.9%）" -Q
   ```
   *预期：no_finding_contains=突变 | 理由: 19.9%，阈值 20%，差 0.1pct 不应触发*

22. **GNSS-POS-1** (位移监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9005, speed_gh 5 点 4 次连续加速" -Q
   ```
   *预期：min_level=WARNING; message_contains=加速 | 理由: GNSS 5 点窗口 4 次连续加速，达趋势阈值*

23. **GNSS-NEG-1** (位移监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9005, speed_gh 5 点仅 3 次连续加速" -Q
   ```
   *预期：no_finding_contains=加速 | 理由: 仅 3 次连续加速，阈值 4 次，差 1 不应触发*

24. **GATE-POS-1** (闸门工情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9006, gtophgt 相邻两点 1.00→2.01（突变 1.01m）" -Q
   ```
   *预期：min_level=WARNING; message_contains=突变 | 理由: 1.01m > 单步开度突变阈值 1.0m（gate_opening_...*

25. **GATE-NEG-1** (闸门工情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9006, gtophgt 相邻两点 1.00→2.00（突变恰 1.00m）" -Q
   ```
   *预期：no_finding_contains=突变 | 理由: 变化恰等于阈值 1.0m，判定为严格大于，不应触发*

26. **GATE-POS-2** (闸门工情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9006, 单条 gtophgt=2.5, gtq=0" -Q
   ```
   *预期：min_level=WARNING; message_contains=流量为0 | 理由: 开度 2.5m>0 且流量为 0，疑似卡阻或流量计故障*

27. **GATE-NEG-2** (闸门工情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9006, 全窗口 gtophgt=0, gtq=0（闸门全关）" -Q
   ```
   *预期：no_finding_contains=流量为0; not_no_data=True | 理由: 输出纪律 #5：开度 0/流量 0 是合法观测（闸门关闭），不...*

28. **PUMP-POS-1** (泵站工情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9007, 单条 freq=44.9" -Q
   ```
   *预期：min_level=WARNING; message_contains=频率 | 理由: 44.9Hz < 下界 45Hz（工频 50Hz -10%）*

29. **PUMP-NEG-1** (泵站工情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9007, 单条 freq=45.0" -Q
   ```
   *预期：no_finding_contains=频率 | 理由: 恰等于下界 45Hz，判定为严格小于，不应触发*

30. **PUMP-POS-2** (泵站工情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9007, 单条 uab=400, ubc=400, uca=464（不平衡 10.1%）" -Q
   ```
   *预期：min_level=WARNING; message_contains=三相不平衡 | 理由: max_dev/avg = 42.67/421.33 ≈ 10....*

31. **WQ-POS-1** (水质监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】stcd=9008, 最新一条 ph=5.99" -Q
   ```
   *预期：min_level=WARNING; message_contains=pH偏低 | 理由: 5.99 < 标准下限 6（注意：检测只取最新一条读数）*

32. **WQ-NEG-1** (水质监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】stcd=9008, 最新一条 ph=6.00" -Q
   ```
   *预期：no_finding_contains=pH | 理由: 恰等于下限 6，判定为严格小于，不应触发*

33. **SOIL-POS-1** (土壤墒情-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9009, soil_moist_evaluation='重度干旱'" -Q
   ```
   *预期：min_level=WARNING; message_contains=墒情评价 | 理由: 评价文本命中关键词（干旱/不足/重度）*

34. **SOIL-NEG-1** (土壤墒情-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9009, soil_moist_evaluation='适宜', soil_water100cm=25.0" -Q
   ```
   *预期：no_finding_contains=墒情评价 | 理由: 评价不含干旱/不足/重度关键词，且 100cm 含水量 25% ≥ 10% 下限*

35. **TERM-POS-1** (白蚁监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9010, damage_level='重度' 1 条" -Q
   ```
   *预期：min_level=CRITICAL; message_contains=危害等级 | 理由: 重度危害 → CRITICAL（中度仅 WARNING）*

36. **TERM-POS-2** (白蚁监测-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9010, pest_density=3, check_result='未发现', damage_level=NULL" -Q
   ```
   *预期：min_level=WARNING; message_contains=虫口密度 | 理由: 密度恰达阈值 3（判定 ≥3 含边界，与多数严格比较不同）*

37. **TERM-NEG-1** (白蚁监测-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9010, pest_density=2, check_result='未发现', damage_level=NULL" -Q
   ```
   *预期：no_finding_contains=白蚁 | 理由: 密度 2 < 3，未发现白蚁，无危害等级，差 1 级不应触发*

38. **INSP-POS-1** (巡检结果-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "100 条任务，69 条 status='3'（完成率 69%），无超时" -Q
   ```
   *预期：min_level=WARNING; message_contains=完成率偏低 | 理由: 69% < 考核线 70%（completion_rate_mi...*

39. **INSP-NEG-1** (巡检结果-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "100 条任务，70 条 status='3'（完成率恰 70%），无超时" -Q
   ```
   *预期：no_finding_contains=完成率 | 理由: 恰等于考核线 70%，判定为严格小于，不应触发*

40. **EQUIP-POS-1** (设备状态-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "100 台设备，31 台 status=0（离线率 31%），0 台 status=2" -Q
   ```
   *预期：min_level=WARNING; message_contains=离线率偏高 | 理由: 31% > 阈值 30%（equip_offline_rate_...*

41. **EQUIP-NEG-1** (设备状态-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "100 台设备，30 台 status=0（离线率恰 30%），0 台 status=2（异常必须为 0，否则另一分支触发）" -Q
   ```
   *预期：no_finding_contains=离线率 | 理由: 恰等于阈值 30%，判定为严格大于，不应触发*

42. **ALERT-POS-1** (告警分析-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "1 条 level_r='1' 未确认告警" -Q
   ```
   *预期：min_level=CRITICAL; message_contains=I级告警 | 理由: I 级告警 ≥1 条即 CRITICAL*

43. **ALERT-NEG-1** (告警分析-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "10 条 level_r='4' 未确认告警（无 I/II 级）" -Q
   ```
   *预期：no_finding_contains=告警 | 理由: 无 I/II 级；未确认恰 10 条，积压阈值为严格 >10，不应触发*

44. **MAD-POS-1** (MAD统计异常-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9011, water_pressure 30 点稳定 50.00±0.05，末点 60.0" -Q
   ```
   *预期：min_level=WARNING; message_contains=MAD统计异常 | 理由: 末点偏离中位数，z 远超渗压 MAD 阈值 4.0，样本 3...*

45. **MAD-NEG-1** (MAD统计异常-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9011, 同形态离群序列但总共仅 19 点" -Q
   ```
   *预期：no_finding_contains=MAD统计异常 | 理由: 样本 19 < min_samples 20，统计不可靠不应触发（样本量下限护栏）*

46. **CORR-POS-1** (关联异常-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "累计雨量 60mm，同期 rz 变化 0.04m（正常波动非平线）" -Q
   ```
   *预期：min_level=INFO; message_contains=累计 | 理由: 雨量 >50mm 且水位变化 <0.05m，且水位序列 CV≥idle_cv...*

47. **CORR-NEG-1** (关联异常-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "累计雨量 60mm，同期 rz 全程恒等 100.000（死值平线）" -Q
   ```
   *预期：no_finding_contains=累计 | 理由: 水位序列为死值平线（CV<0.001），idle 护栏应抑制伪相关——该报的是数据质量问题不是关联异常*

48. **CORR-POS-2** (关联异常-should_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】渗压计9003 wp 6点严格递增 50→52→54→56→58→60；同期水位 rz 在 100.0~100.05 波动（变化<0.1m 且 CV≥idle_cv_min 非平线）" -Q
   ```
   *预期：min_level=WARNING; message_contains=渗压 | 理由: 渗压持续上升 + 水位稳定(非死值平线) → 关联2 应报（防渗体损坏...*

49. **CORR-NEG-2** (关联异常-should_not_report)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】渗压计9003 wp 6点严格递增；同期水位 rz 全程恒等 100.000（死值平线）" -Q
   ```
   *预期：no_finding_contains=水位稳定 | 理由: 水位死值平线（CV<0.001）→ idle 护栏抑制关联2（'稳定'可能是水位计卡滞而非真稳定）...*

50. **QG-RED-1** (水库水情（质量闸）-quality_gate)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9012, 30 天窗口仅注入 3 天数据（完整性 <80% 红档）" -Q
   ```
   *预期：dimension_status=INCONCLUSIVE; envelope_status=inconclusive; exit_code=4; next_s...*

51. **QG-PLACEHOLDER-1** (水库水情（质量闸）-quality_gate)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9012, rz 序列混入 -99 与 999 各若干，另含合法 0.00 读数" -Q
   ```
   *预期：quality_issues_contains=占位; zero_not_counted_as_placeholder=True | 理由: -99/999 属...*

52. **SEASON-GUARD-1** (水库水情（季节护栏）-guardrail)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9013, 7 月汛期注入 MAD 离群高水位（历史同期水位普涨）" -Q
   ```
   *预期：max_level=INFO; message_contains=MAD统计异常 | 理由: 汛期 in_season 命中 → 水位普涨降级 INFO 而非 ...*

53. **DIAG-HIT-1** (渗压监测（诊断链）-diagnosis)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9014 渗压突变 5.5kPa（WARNING 命中 R1 路由）；同期 -2h 窗口内 rz 上升 0.25m（≥0.2m）" -Q
   ```
   *预期：finding_has=diagnosis_root_cause; detail_contains=证据链; envelope_category=root_ca...*

54. **DIAG-MISS-1** (渗压监测（诊断链）-diagnosis)
   ```bash
   hermes chat -s powerelf-inspection -q "【假设测试数据·无需查库，直接判断】st_id=9014 渗压突变 5.5kPa；同期水位平稳（Δ<0.2m）、无降雨、闸门无动作" -Q
   ```
   *预期：finding_not_has=diagnosis_root_cause; detail_contains=已查 | 理由: 三层候选与横向 fallback ...*

55. **EMPTY-NA-1** (河道水情（借 st_river_r 天然空表）-empty_data)
   ```bash
   hermes chat -s powerelf-inspection -q "不注入任何数据（表历史即空）" -Q
   ```
   *预期：status_code=NOT_APPLICABLE; no_fabricated_values=True | 理由: MAX(tm) 探针为 NULL → 本...*

56. **EMPTY-ND-1** (渗流监测-empty_data)
   ```bash
   hermes chat -s powerelf-inspection -q "仅注入 30 天前的历史行，窗口 7 天内为空" -Q
   ```
   *预期：status_code=NO_DATA; note_contains=采集; no_fabricated_values=True | 理由: 有历史 MAX(t...*

57. **EMPTY-QF-1** (任一维度-empty_data)
   ```bash
   hermes chat -s powerelf-inspection -q "查询抛异常" -Q
   ```
   *预期：status_code=QUERY_FAILED; no_fabricated_values=True | 理由: 查询失败 ≠ 无数据，严禁以 0 或空充数*
