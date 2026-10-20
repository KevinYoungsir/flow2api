# 当前 Flow 视频模型的公开源码诊断

当前结果：**诊断已完成，视频验收 PASS**。用户返回 7 个公开脚本，全部读取成功；实际视频模块提供 GetModels 只读接口。当前费用类别 2 可用普通 Fast 八秒，四秒/六秒不可用；按目录选择八秒后约 69 秒成功，实际 720p、8 秒。原生 720p 不发送分辨率覆盖消息，后端空值与之相符。来源和结果见 [原生模型证据](flow-native-model-evidence-20261020.json)及 [验收记录](live-acceptance-20261020.md)。

## 诊断前的问题与准备（历史）

用户已确认 flow.google.com、普通 Fast、720p。2026-10-20 11:12:37（Asia/Shanghai）插件同步实际 HTTP 200；其后余额、VideoFxService.GetUserSettings、FlowService.GetUserSettings 只读查询均成功，上游层级枚举 PAYGATE_TIER_ONE 与保存值相同。两个设置响应均未找到模型 key 字符串，本轮没有新增生成请求。

源码显示此前文本视频调用没有显式传入 resolution，构造器会传 null。Google 对空值的默认处理未知，不能据此确定 MODEL_ACCESS_DENIED 原因。此前把 _relaxed 直接解释为网页低优先级，证据不足；d54f59c 的回归仅证明标准 key 实际被提交，不证明它就是网页普通 Fast 对应的 key。需要页面实际加载的模型定义，避免继续猜测参数。

浏览器工具在本机初始化时出现进程安全环境错误 0x80070020，未能直接读取浏览器。因此准备脚本供用户在已有 Flow 页面执行，无需修改系统安全设置或额外生成视频。

## 执行

1. 在同一 Chrome 用户配置打开此前视频所在的 Flow 项目。
2. 展开视频模型选择器，让页面加载相应模块；不要点击生成。
3. 按 F12，选择 Console。
4. 复制 `D:\Flow2API\scripts\diagnose_flow_public_models.js` 全部内容并运行。
5. 仅回复以 `FLOW_PUBLIC_MODEL_DIAGNOSTIC` 开头的一整行。脚本的准备和本地测试不代表已在真实页面运行。

## 读取范围与验证

候选地址只来自页面资源记录和 script.src。脚本仅允许 https://www.gstatic.com/_/mss/boq-labs-ai-sandbox/_/js/ 下、带版本及模块路径、没有用户名/密码/查询串/片段的公开脚本；最多 12 个，GET、credentials=omit、拒绝重定向、逐项 12 秒超时。不读取 Cookie、Chrome API、localStorage 或 sessionStorage，不调用 Google RPC，不上传数据或生成。

输出包含已校验的公开脚本地址、模型/分辨率常量、公开视频 RPC 名称、计数和遮蔽无关字符串后的公开源码片段；资源列表中其他私有 URL 和失败异常文字不会输出。若跨域读取失败，可使用这些公开脚本地址继续核对，无需发送 HAR、原始请求体或 Copy as cURL。

已实际通过 `node --check scripts/diagnose_flow_public_models.js` 和 `node tests/test_flow_public_model_diagnostic.cjs`。测试覆盖公开域名白名单、拒绝私有资源/凭据/查询串/伪装域名、省略凭据的 GET、请求上限、禁止读取 Cookie/存储、无关字符串脱敏和错误隐藏。用户实际页面也已执行，7 个资源均成功读取。静态常量存在本身不等于成功请求或权限；本次结合动态目录和唯一一次可用八秒选项的真实生成完成验证。
