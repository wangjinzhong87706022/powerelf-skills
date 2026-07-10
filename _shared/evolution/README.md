# 自我进化机制约定（跨 skill 统一）

> 每个 skill 的 `evolution/` 目录遵循本约定。本目录提供**格式模板**，各 skill 的实际参数值
> 仍各自维护（不同 skill 调参体系不同）。

## 目录结构（每个 skill 必备）

```
<skill>/evolution/
├── parameters.md      # 可调参数注册表（当前值、合理范围、调整依据）
└── feedback-log.md    # 执行反馈日志（事件、原因、改进措施）
```

## 文件格式

- **parameters.md**：见 `parameters.template.md`。表头固定为
  `参数名 | 当前值 | 合理范围 | 说明 | 最后调整`
- **feedback-log.md**：见 `feedback-log.template.md`。记录误报/漏报事件 → 归因 → 参数调整

## 进化流程

1. Agent 执行规则 → 记录判断结果
2. 用户反馈不准确 → 记录到 `feedback-log.md`
3. 分析反馈模式 → 建议参数调整
4. 更新 `parameters.md` → 下次执行使用新参数

## 现有 skill 一览

monitor / early-warning / inspection / data-governance / chatbi 均已具备 evolution/ 目录，
格式与本约定一致。新增 skill 请从模板复制起步。
