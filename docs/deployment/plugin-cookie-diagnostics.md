# 插件 Cookie 采集范围诊断

当前证据：2026-10-19 后台已保存会话可查询 Google 余额；同一账号插件上传仍被 nzlxg RPC 拒绝。失败响应为 `stored_session=different; auth_values=different; missing_auth=3; extra_auth=0`。missing_auth 是按照实际 RPC URL 筛选后的标准认证 Cookie 数量差，并不包含具体名称，也不能单凭它认定过期、分区或插件故障。

插件当前上游代码仅调用 `chrome.cookies.getAll({url: 'https://flow.google.com/projects'})`。Chrome 的 Cookies API 默认使用当前执行上下文的存储区及未分区 Cookie；页面所在存储区和分区必须分别确认。这里只收集本机脱敏元数据，不向服务上传 Cookie，不修改服务端鉴权，也不改写 Cookie 范围。

## 执行步骤

1. 在安装插件的同一个 Chrome 用户配置中打开已登录的 Flow 项目页，并保持打开。
2. 在 Chrome 地址栏输入 `chrome://extensions`，打开右上角「开发者模式」。找到 **Flow2API Token Updater**，点击它的 **Service Worker / 服务工作进程** 链接。
3. 在新窗口切到 **Console / 控制台**。复制本仓库 [只读脚本](../../scripts/diagnose_token_updater.js) 的全部内容，粘贴运行。
4. 只复制以 `TOKEN_UPDATER_DIAGNOSTIC` 开头的那一行作为诊断结果；不要复制其他插件日志或自行打印完整 Cookie 对象。

脚本只输出插件版本、数量、预先固定的标准认证 Cookie 名称、布尔状态。它不读取插件连接令牌或账号配置，不发起网络请求，不修改 Cookie，不输出 Cookie 值、邮箱、页面 URL、tab ID、store ID 或分区键。Chrome 不支持分区键 API 或读取失败时只输出固定状态，不输出原异常。

`default_context` 对应上游插件现有采集方式；`flow_tabs[].unpartitioned` 对应 Flow 标签页实际存储区；`current_partition` 仅查询该页面 API 返回的实际分区。若 `flow_tabs` 为空，先保持 Flow 页打开后重试。不能把不同存储区或不匹配的分区合并成一个 Cookie header；也不能用旧的已保存会话填补失败上传后直接标记同步成功。

本机语法检查及合成 Chrome API 测试已覆盖元数据输出、页面存储区/分区选择、旧版 API 和错误脱敏；用户已于 2026-10-20 返回真实 Chrome 执行结果，见下节。此结果不是插件同步成功。

维护时可运行 `node --check scripts/diagnose_token_updater.js` 和 `node tests/test_token_updater_diagnostic.cjs` 重复上述本机检查；这些检查不连接真实 Chrome，也不代表实际插件同步成功。

参考：[插件采集实现](https://github.com/TheSmallHanCat/Flow2API-Token-Updater/blob/main/background.js)、[Chrome Cookies API](https://developer.chrome.com/docs/extensions/reference/api/cookies)、[Chromium API 返回结构](https://chromium.googlesource.com/chromium/src/+/master/chrome/common/extensions/api/cookies.json)。

## 2026-10-20 真实 Chrome 结果与权限修复

用户的 1.3.1 插件报告：默认上下文和 Flow 普通标签页所在存储区均采集 16 条 Cookie，标准认证名称均为 OSID、SAPISID、SSID、__Secure-1PSID、__Secure-3PSID、__Secure-OSID；分区条数均为 0，页面实际分区查询也为 0 条。对照此前后台记录，缺少 SID、HSID、APISID。这次结果未显示存储区或分区差异导致漏采。

确认一个与上述缺失模式吻合的插件权限缺陷：上游 1.3.1 的 required host_permissions 只有 Google 的 HTTPS 模式；Chromium 对每条 Cookie 先按 Secure 属性构造权限检查 URL，再检查该源的页面访问权限。非 Secure Cookie 对应 HTTP 源，因此仅 HTTPS 的权限声明不能覆盖它们。optional_host_permissions 声明可申请 HTTP 并不等于已获得相应授权。此机制由 [当前 Chromium 权限过滤实现](https://raw.githubusercontent.com/chromium/chromium/main/extensions/browser/api/cookies/cookies_helpers.cc) 及 [HTTP/HTTPS URL 构造实现](https://raw.githubusercontent.com/chromium/chromium/main/net/cookies/cookie_util.cc) 直接确认；是否为用户本次 401 的完整原因，仍需补权限后的真实同步验证。

已从配套插件提交 `e1ed56627596209c9e77df381e3fe82e0a17c492` 准备本地修复副本 `D:\Flow2API\tmp\Flow2API-Token-Updater-permission-fix`，只在 manifest.json 增加 `http://google.com/*`、`http://*.google.com/*` 两项 Google 主机权限。13 个其他源文件逐字节哈希未变，background.js/popup.js 语法检查通过；[最小补丁](../../scripts/token-updater-google-cookie-permissions.patch) 已通过 git apply --check。Cookie 仍按原来的 HTTPS Flow URL 采集并保留作用域，上传仍使用原 HTTPS 接口；未改验证码、服务端校验或账号数据，没有重新部署 Railway。

用户随后提供原解压文件夹 `D:\Flow2API-Token-Updater-main`。2026-10-20 10:18（Asia/Shanghai）已在原目录应用上述最小修复，保留原安装路径；清单身份、版本及 worker 路径均先核对为预期值。原清单先以独占创建方式备份为 `manifest.json.before-cookie-permissions-20261020T021820Z-046ade57.bak`，字节核对一致，再使用同目录临时文件原子替换 manifest。除新增的两项 host_permissions 外所有清单字段均相同，background.js 与 popup.js 修改前后哈希相同，二者 node --check 通过。此操作没有访问 Chrome 保存的连接配置，也没有重新安装插件或修改其存储。

已请用户在 chrome://extensions 点击现有插件卡片的重新加载按钮，在出现权限提示时确认新增的 Google 权限并启用，再点立即同步。磁盘上的修复不代表已运行的 worker 自动获得新权限；目前 Chrome 重新加载、实际授权及修复后同步结果仍待用户确认，不能标记同步通过。不要直接修改 Chrome 用户数据目录中的已安装扩展文件；连接配置只在本机/后台处理，不发到聊天。
