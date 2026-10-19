# 费用授权与部署前置条件

## 已取得的用户授权

2026-10-19：用户明确选择新建独立 `flow2api` 项目，并授权新增一个应用服务和一个挂载 `/app/data` 的持久卷，月度费用上限 **USD 5**。无需再次询问这些已确认事项；不得把这个上限解释为可自动超额。

## 本次实际执行结果

- GitHub 账号权限可用，部署分支已实际推送至 `KevinYoungsir/flow2api`。
- 使用已连接 Railway 账号，在 `KevinYoung's Projects` workspace 中调用 create-project，新项目名 flow2api、默认环境 production、私有且关闭 PR deploy。
- Railway 拒绝请求，原文：`Your trial has expired. Please select a plan to continue using Railway.`
- 随后重新列举项目，仍只有 `eloquent-enchantment`。Flow2API 项目、服务、Volume、域名与部署均未创建；没有触发运行资源计费或修改现有应用。

## 用户要求继续部署后的复核

- 已再次核对 GitHub 部署分支与本地一致，提交为 `76504e5ac18dae6b9d7bc3161ef552064232ebb4`；Railway 只读项目列表仍无 flow2api。
- 尝试重新创建项目时，被自动审批拒绝，未到达实际资源创建步骤。审批理由是：先前试用已到期，尚无证据确认套餐及工作区预算限额已经激活；不得用间接方式绕过此拒绝。
- 已执行不修改资源的安全核验：浏览器读取工具遇到 MXC 启动器错误；Railway CLI whoami 和 usage limit status 均返回 OAuth invalid_grant / Unauthorized。因此当前无法独立验证套餐与硬限额。
- 已请用户确认当前套餐、Compute 硬上限及其对同工作区 autowealth-ai 的影响。原有新建项目/服务/卷与 5 美元上限授权继续有效，无需重复授权这些既定事项；当前缺的是账单前置条件的核实。

## 5 美元上限的实际含义

### 当前状态（用户最新确认）

用户已明确确认 **Hobby 已激活，硬上限尚未设置**。套餐激活应视为已确认，不再反复要求确认激活；当前唯一的账单前置条件是落实并核实 USD 5 的 Compute 硬上限，同时明确接受对同工作区其他项目的影响。

已复核连接器仍没有费用限额设置工具，CLI 仍返回 Unauthorized；浏览器工具重置后依然因 MXC 启动器错误无法读取页面。因此需要用户在 [Workspace Usage](https://railway.com/workspace/usage) → Set Usage Limits → Compute Usage → Hard limit 手动填 5 并保存，然后告知结果。在限额未生效时，不重试此前已被自动审批拒绝的项目创建。

Railway Hobby 为每月 5 美元最低消费，包含首 5 美元资源用量；超过额度会继续计费。订阅 Hobby 本身不等于设置 5 美元最高账单。[官方账单说明](https://docs.railway.com/pricing/understanding-your-bill)

Compute Usage 硬上限按整个 **workspace** 设置，包含 CPU、内存、存储和出口流量；达到上限会使工作区内运行负载离线。新建一个 project 不会产生独立于工作区的费用硬上限。本工作区还包含 autowealth-ai，因此不能依据仅针对 Flow2API 的授权，擅自设置一个会影响该旧应用的工作区停机阈值。[官方费用控制](https://docs.railway.com/pricing/cost-control)

当前 Railway 连接器没有订阅/支付或工作区费用限额管理工具，本机 CLI 登录又已失效。需要用户在控制台完成套餐激活，并明确确认工作区预算安排及对其他项目的影响；不索取银行卡或支付凭据，不代为接受高于 5 美元的计划。

官方用量设置入口：[Workspace Usage](https://railway.com/workspace/usage)。先在账号切换器确认 `KevinYoung's Projects`。套餐入口使用 Railway 控制台当前的 Plan/Billing 界面。

## 激活后继续执行

1. 复核目标账号、套餐和已有硬限额；仅按用户已经确认的预算继续。
2. 新建独立 flow2api 项目、production 环境和单个服务，配置仓库部署分支。
3. 附加 `/app/data` 卷。首期拟用小容量卷（例如 500MB，需平台允许），不增加其他服务；内存和 CPU 限制在验证应用需求后设置，不能把资源上限当作完整的账单上限。
4. 通过 Railway Variables 由用户设置管理员密码与本服务 API Key；不在聊天、Git、命令行历史或镜像中写真实秘密。
5. 实际构建、启动、健康检查、重启持久化和资源用量验收后，记录是否满足 5 美元预算。未测量前不得承诺月费一定低于上限。
6. 域名 DNS、真实上游权限与生成验收继续按既有阶段要求执行。
