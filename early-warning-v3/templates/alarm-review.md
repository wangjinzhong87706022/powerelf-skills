# 告警复盘模板

## 使用说明

当告警处理完成后，使用此模板进行复盘，积累经验教训。

## 复盘时机

- 告警处理完成后
- 每周告警汇总
- 每月告警分析
- 重大告警事件后

## 复盘模板

```markdown
# 告警复盘报告

## 一、告警概况
- 告警ID：{alarm_id}
- 告警名称：{alarm_name}
- 告警级别：{alarm_level}
- 测站编码：{station_code}
- 触发时间：{trigger_time}
- 恢复时间：{recover_time}
- 持续时间：{duration}

## 二、处理过程
| 时间 | 操作 | 操作人 | 结果 |
|------|------|--------|------|
| {time1} | {action1} | {operator1} | {result1} |
| {time2} | {action2} | {operator2} | {result2} |

## 三、原因分析
- 直接原因：{direct_cause}
- 根本原因：{root_cause}
- 关联因素：{related_factors}

## 四、经验教训
### 做得好的
- {good_point_1}
- {good_point_2}

### 需要改进的
- {improvement_1}
- {improvement_2}

### 避免再次发生
- {prevention_1}
- {prevention_2}

## 五、改进措施
| 措施 | 负责人 | 截止时间 | 验证方式 |
|------|--------|----------|----------|
| {measure_1} | {owner_1} | {deadline_1} | {verify_1} |
| {measure_2} | {owner_2} | {deadline_2} | {verify_2} |

## 六、知识沉淀
- 更新知识库：{knowledge_update}
- 优化规则：{rule_optimization}
- 完善流程：{process_improvement}

## 七、附件
- 告警截图：{screenshot}
- 处理记录：{process_log}
- 相关文档：{related_docs}
```

## 复盘检查清单

### 复盘前
- [ ] 收集告警详情
- [ ] 收集处理记录
- [ ] 收集相关数据
- [ ] 准备复盘环境

### 复盘中
- [ ] 分析告警原因
- [ ] 回顾处理过程
- [ ] 总结经验教训
- [ ] 制定改进措施

### 复盘后
- [ ] 更新知识库
- [ ] 优化告警规则
- [ ] 完善处理流程
- [ ] 归档复盘报告

## 复盘输出

- 复盘报告
- 知识库更新
- 流程优化建议
- 规则调整建议
