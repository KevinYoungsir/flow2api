# 插件 Cookie 采集范围诊断

当前证据：后台已保存会话可查询 Google 余额；同一账号插件上传仍被 nzlxg RPC 拒绝。失败响应为 `stored_session=different; auth_values=different; missing_auth=3; extra_auth=0`。missing_auth 是按照实际 RPC URL 筛选后的标准认证 Cookie 数量差，并不包含具体名称，也不能单凭它认定过期、分区或插件故障。

插件当前上游代码仅调用 `chrome.cookies.getAll({url: 'https://flow.google.com/projects'})`。Chrome 的 Cookies API 默认使用当前执行上下文的存储区及未分区 Cookie；页面所在存储区和分区必须分别确认。这里只收集本机脱敏元数据，不向服务上传 Cookie，不修改服务端鉴权，也不改写 Cookie 范围。

## 执行步骤

1. 在安装插件的同一个 Chrome 用户配置中打开已登录的 Flow 项目页，并保持打开。
2. 在 Chrome 地址栏输入 `chrome://extensions`，打开右上角「开发者模式」。找到 **Flow2API Token Updater**，点击它的 **Service Worker / 服务工作进程** 链接。
3. 在新窗口切到 **Console / 控制台**。复制本仓库 [只读脚本](../../scripts/diagnose_token_updater.js) 的全部内容，粘贴运行。
4. 只复制以 `TOKEN_UPDATER_DIAGNOSTIC` 开头的那一行作为诊断结果；不要复制其他插件日志或自行打印完整 Cookie 对象。

脚本只输出插件版本、数量、预先固定的标准认证 Cookie 名称、布尔状态。它不读取插件连接令牌或账号配置，不发起网络请求，不修改 Cookie，不输出 Cookie 值、邮箱、页面 URL、tab ID、store ID 或分区键。Chrome 不支持分区键 API 或读取失败时只输出固定状态，不输出原异常。

`default_context` 对应上游插件现有采集方式；`flow_tabs[].unpartitioned` 对应 Flow 标签页实际存储区；`current_partition` 仅查询该页面 API 返回的实际分区。若 `flow_tabs` 为空，先保持 Flow 页打开后重试。不能把不同存储区或不匹配的分区合并成一个 Cookie header；也不能用旧的已保存会话填补失败上传后直接标记同步成功。

本机语法检查及合成 Chrome API 测试已覆盖元数据输出、页面存储区/分区选择、旧版 API 和错误脱敏；尚未在用户真实 Chrome 中执行，结果需要用户提供。

维护时可运行 `node --check scripts/diagnose_token_updater.js` 和 `node tests/test_token_updater_diagnostic.cjs` 重复上述本机检查；这些检查不连接真实 Chrome，也不代表实际插件同步成功。

参考：[插件采集实现](https://github.com/TheSmallHanCat/Flow2API-Token-Updater/blob/main/background.js)、[Chrome Cookies API](https://developer.chrome.com/docs/extensions/reference/api/cookies)、[Chromium API 返回结构](https://chromium.googlesource.com/chromium/src/+/master/chrome/common/extensions/api/cookies.json)。
