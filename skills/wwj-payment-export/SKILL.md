---
name: wwj-payment-export
description: "从 OA 系统待办列表中导出「预计支付款项明细表」Excel 文件。当用户提到\"导出支付款项明细表\"、\"支付明细\"、\"预计支付\"、\"导出报销\"、\"资金支付明细\"、\"OA导出\"、\"待办导出\"、\"付款明细表\"、\"生成支付款项\"时使用此技能。只要用户想从 OA 系统导出报销和资金支付的汇总表，就应该触发此技能，即使用户没有明确说'明细表'。"
---

# 预计支付款项明细表导出

从 OA 系统待办列表提取「报销申请」和「资金支付」数据，生成 Excel。

## 前置条件

- `playwright-cli`、`uv` 已安装
- 环境变量中配置了 `FINANCE_OA_USERNAME`、`FINANCE_OA_PASSWORD`、`FINANCE_OA_URL`

## 执行步骤

### 1. 抓取数据

```bash
uv run python3 "$SKILL_DIR/scripts/oa_scraper.py" /tmp/payment_data.json
```

自动完成：登录（验证码 OCR）→ 导航待办列表 → 提取列表并过滤 → 逐条获取详情 → 输出 JSON。

**过滤规则：**
- 报销申请：只获取处理环节为「报销结清」的数据
- 资金支付：只获取处理节点为「支付记录」的数据

### 2. 生成 Excel

```bash
uv run python3 "$SKILL_DIR/scripts/generate_excel.py" /tmp/payment_data.json "$PROJECT_DIR/101-Whatever/预计支付款项明细表_$(date +%Y%m%d).xlsx"
```

## 字段映射

| Excel 列 | 报销申请 | 资金支付 |
|----------|---------|---------|
| 部门 | 空 | 空 |
| 项目 | 报销人 | 合作单位名称 |
| 计划付款金额 | 报销金额 | 申请支付金额 |
| 实际付款金额 | 空 | 空 |
| 备注 | "报销" | 付款标题 |
| 内容 | 空 | 空 |
