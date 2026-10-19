# 费用授权与部署前置条件

## 已取得的用户授权

2026-10-19：用户明确选择新建独立 `flow2api` 项目，并授权新增一个应用服务和一个挂载 `/app/data` 的持久卷。最初月度上限为 USD 5；CLI 恢复后核实平台不支持该硬上限，用户随后明确同意 **最高 USD 10/月并继续部署**。当前授权上限为 10 美元，不得擅自提高或移除。

## 早期尝试（历史记录）

- GitHub 账号权限可用，部署分支已实际推送至 `KevinYoungsir/flow2api`。
- 使用已连接 Railway 账号，在 `KevinYoung's Projects` workspace 中调用 create-project，新项目名 flow2api、默认环境 production、私有且关闭 PR deploy。
- Railway 拒绝请求，原文：`Your trial has expired. Please select a plan to continue using Railway.`
- 随后重新列举项目，仍只有 `eloquent-enchantment`。Flow2API 项目、服务、Volume、域名与部署均未创建；没有触发运行资源计费或修改现有应用。

## 早期部署复核（历史记录）

- 已再次核对 GitHub 部署分支与本地一致，提交为 `76504e5ac18dae6b9d7bc3161ef552064232ebb4`；Railway 只读项目列表仍无 flow2api。
- 尝试重新创建项目时，被自动审批拒绝，未到达实际资源创建步骤。审批理由是：先前试用已到期，尚无证据确认套餐及工作区预算限额已经激活；不得用间接方式绕过此拒绝。
- 当时执行的只读核验遇到浏览器 MXC 错误和 CLI invalid_grant，无法独立验证套餐与限额；之后 CLI 登录已恢复。
- 用户当时确认 Hobby 与所谓 5 美元硬上限，并接受影响旧应用。后续实际读取发现 5 是提醒金额，已按下节纠正并取得新的 10 美元授权；历史确认不作为当前 5 美元硬上限的证据。

## 实际费用限额与当前状态

### 当前状态（用户最新确认）

CLI 登录已恢复，`railway usage limit status` 实际返回 `softLimit=5`、`hardLimit=10`。尝试按最初授权降低硬上限到 5，平台明确拒绝：`Compute hard limit must be at least $10, or exactly $0`。没有将 0 当作安全封顶，也没有在未获新授权时启动部署。用户随后明确选择“同意最高 $10/月，继续部署”。

当前工作区设置经 CLI 实际读取为：**5 美元邮件提醒、10 美元硬上限**；用户已接受限额影响同工作区 autowealth-ai。已创建独立 flow2api 项目、服务、500MB /app/data 卷，服务上限为 0.5 vCPU / 0.5GB 内存。没有修改 autowealth-ai 配置或数据。平台的具体计费结算/存储保留规则仍以账单为准，不承诺运行资源一直低于提醒金额。

Railway Hobby 为每月 5 美元最低消费，包含首 5 美元资源用量；超过额度会继续计费。订阅 Hobby 本身不等于设置 5 美元最高账单。[官方账单说明](https://docs.railway.com/pricing/understanding-your-bill)

Compute Usage 硬上限按整个 **workspace** 设置，包含 CPU、内存、存储和出口流量；达到上限会使工作区内运行负载离线。新建一个 project 不会产生独立于工作区的费用硬上限。本工作区还包含 autowealth-ai，用户已明确接受该范围，后续不得擅自提高或移除阈值。[官方费用控制](https://docs.railway.com/pricing/cost-control)

CLI 与连接器均已恢复。Hobby 和当前限额已确认，不再要求用户重复登录或重复授权预算。首个部署 a36c4b4c-9cfa-4116-ab99-d8938c54704b 因 API Key 少于 32 字符而安全失败；用户修正后，部署 743a372a-cd29-423a-b642-3ac7a02795b4 已 SUCCESS，重启和持久化验收通过。未输出或提交秘密值。

重启验收后的再次 CLI 读取仍为 workspaceUsage.usageLimit.softLimit=5、hardLimit=10。另有独立的 Agent Usage 限额 5 美元，不能误读为 Compute 硬上限。空闲内存抽样约 0.065 GB，但没有足够运行历史估算月费；账单页面可能延迟，不能把极小的当前用量当作完整月费。

官方用量设置入口：[Workspace Usage](https://railway.com/workspace/usage)。先在账号切换器确认 `KevinYoung's Projects`。套餐入口使用 Railway 控制台当前的 Plan/Billing 界面。

## 后续费用控制

1. 保留已授权的工作区 10 美元 Compute 硬上限与 5 美元提醒，不新增服务或扩大资源限额。
2. 当前为单服务、500MB 卷、0.5 vCPU / 0.5GB 限制；资源上限不能替代费用上限，实际生成负载仍待测量。
3. DNS 方案不因本次部署自动购买阿里云付费解析；真实上游生成需先配置合法账号并确认额度消耗。
