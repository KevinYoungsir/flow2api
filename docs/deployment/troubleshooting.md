# 排障

| 现象 | 检查与处理 |
| --- | --- |
| Config as Code is deprecated | 新服务不能使用旧 railway.json/railway.toml；本次已移除旧文件，使用服务设置及 Dockerfile。IaC 需单独经过 config pull/plan 审查，不能只因旧 schema 校验通过就假定可部署 |
| 502 / health 超时 | 构建是否使用 Dockerfile；启动命令是否 python main.py；实际监听是否 0.0.0.0:PORT；域名目标端口一致；不要增加多个 worker |
| Production requires... | 查看错误对应变量名称；新库补安全密码/API Key 与明确 HTTPS 来源；禁止用默认值或 development 掩盖生产问题 |
| 已设置新 Variables，但仍拒绝旧密码/弱 Key | 已有 DB 为设置来源；bootstrap 不覆盖 DB。先安全备份，在可信本地实例登录原库改设置，再迁移；不要删库重建 |
| Railway requires a Volume... | 给目标服务附加 /app/data Volume，确认 Railway 自动注入 RAILWAY_VOLUME_MOUNT_PATH，与 DATA_DIR 一致；不要手填该变量骗过检查 |
| /health 503 starting | 应用尚未完成初始化；查看 migration、权限、配置校验；此状态不说明上游账号异常 |
| /health 503 unavailable | SQLite 文件/目录/卷存在且可写吗，卷是否满，是否有长时间写锁；检查目录和 DB 日志；health 不公开异常细节 |
| database is locked | 一个实例一个 worker；现有业务 busy_timeout 30s，health 写探测 2s；避免外部工具长期持有写事务；先备份，不删 DB/WAL |
| 登录成功但无法打开管理页面 | 公网必须 HTTPS；生产 Cookie Secure/HttpOnly/Lax；不能用 HTTP 调试公网生产登录；检查浏览器 Cookie、Origin 白名单、会话是否过期 |
| 重启后需要重新登录 | 内存会话正常失效；DB 中管理员设置/Token 应仍保留。重启后设置也丢失才检查 Volume |
| 403 Untrusted request origin / CORS | 填精确 HTTPS origin；不要包含路径、通配或错误端口；反代应保留浏览器 Origin；同源前端无需改为独立站点 |
| Chrome Token Updater 同步报 403 Untrusted request origin | 插件使用独立连接令牌，部署修复将两个专用 POST 同步端点交给既有 Bearer 鉴权；管理接口仍校验来源。接口填 https://socool.xin/api/plugin/update-token，连接令牌从后台插件配置复制；无需放宽 CORS。升级修复版后在插件点击立即同步，401 时核对插件连接令牌，400 时查看上游登录态验证提示 |
| 插件返回 400，内层 Google Cookie 验证 rpc=nzlxg, code=401 | 插件连接鉴权已通过，Google 未接受当前登录态；仅凭该码无法判断过期、账号混用或兼容性。在同一 Chrome 用户配置打开 https://flow.google.com/projects，确认可见账号/项目且与插件邮箱一致；需要时重新登录再同步。页面正常且账号一致仍失败时继续排查客户端兼容性。服务只在上游验证成功后保存可用账号 |
| 网页正常但服务器同步仍 401 | 已修正 bootstrap GET 更新/删除的 Cookie 未传给后续 RPC 的兼容缺陷。修复版会保留作用域和同次请求的会话更新；若仍失败，记录新的错误文字及 page_identity / cookies_changed 两个标签。这些标签不包含凭据，不能单凭它们断言 Google 的具体拒绝原因 |
| 已保存账号能查询余额，但插件上传仍 401 | 新版失败响应仅在插件连接鉴权通过后比较同邮箱记录。stored_session 表示项目页/RPC 的 Cookie 对是否相同，auth_values 表示认证 Cookie 对是否相同；missing_auth/extra_auth 是按 URL 作用域过滤后的认证 Cookie 数量差。missing 表示没有可比记录，unknown 表示诊断失败；均不含 Cookie 值。保留新错误文字，不要导出凭据到聊天；Google 拒绝的会话不会写入账号 |
| 插件 1.3.1 漏采 SID、HSID、APISID，missing_auth=3 | Google 主机权限只含 HTTPS 时，Chromium 对非 Secure Cookie 的 HTTP 源权限检查会过滤这些记录。已验证的修复是在原解压目录 manifest.json 补 http://google.com/* 和 http://*.google.com/*，保留其他内容与 HTTPS 上传；备份后重新加载插件，并在出现提示时确认权限。2026-10-20 本项目真实同步已 HTTP 200，详见 [插件诊断记录](plugin-cookie-diagnostics.md)。更新插件源码后需核对权限仍保留 |
| 账号有额度但生成前失败 | 查看选中的验证码方式是否具备其要求的现有合法配置。最初 yescaptcha 密钥为空，未提交任务；10-20 用户已配置，真实图片已成功。只在后台保存密钥，不要在聊天发送 |
| Fast 视频返回 PUBLIC_ERROR_MODEL_ACCESS_DENIED，但网页普通 Fast 曾成功 | 核对实际 key、时长和分辨率。本次从 _relaxed 变更为标准 key 后仍拒绝；内部后缀是否对应网页优先级尚缺证据，不能继续仅凭后缀猜测。用户已确认 flow.google.com、普通 Fast、720p，见 [公开前端诊断](flow-public-model-diagnostics.md)。明确拒绝时仍立即停止，不自动切换模型、账号或放宽鉴权；不能仅凭余额推断模型权限 |
| 修改密码后旧会话 401 | 预期：所有管理员会话撤销，重新登录 |
| /metrics 或 /docs 未公开 | metrics 需要管理员会话，docs/openapi 在生产关闭；health 保持公开 |
| /tmp 链接 404 | 缓存启用吗、文件已过期或容器重建了吗；PUBLIC_BASE_URL 是否为实际域名；文件目录和静态挂载均用 TMP_DIR；不要返回 Windows 路径 |
| 页面缺少样式/图片 | HTML 仍依赖 Tailwind CDN；网络须能加载 CDN；项目赞助图由 /static/sponsors 提供；/static/manage.html 不公开 |
| 浏览器模式启动报错 | 标准 Railway 镜像不含 Chromium/Xvfb；本次不提供生产浏览器模式。保留现有本地 headed Compose，不以规避上游访问限制排障 |
| 上游 401/403/429 或无可用 Token | 检查有权使用的账号、登录态、服务权限、网络和额度；不等同 Railway 部署失败，不绕过上游限制 |
| 请求 5 或 15 分钟断开 | 参见部署指南的 Railway 边缘时限；SSE 无法突破总时长；真实超过上限需单独异步作业设计，不能标记长视频验收通过 |
| Railway Unauthorized / invalid_grant | 用户在本机执行 railway login；再核对 whoami/link/status；不要自动覆盖未知生产服务 |
| Docker 未找到 | 安装并启动 Docker Desktop Linux 容器引擎，再执行 scripts/check_docker.py；当前此项 BLOCKED，不是假通过 |
| Windows unittest UnicodeEncodeError | 设置 PYTHONIOENCODING=utf-8；validate_local.ps1 已设置。不要据此改浏览器上游逻辑 |
| Pillow 导入失败 | 在项目 .venv 重新 pip install -r requirements.txt；现已声明 Pillow |
| DNS 指向 Railway 仍 404 / 证书待签发 | 核对实际 domain status 的所有记录，包括 TXT；检查根域 ALIAS 能力、现有记录冲突与 CAA，保留 MX/TXT，切勿猜目标域名 |

日志不得贴出 Cookie、Authorization、完整上游请求体或环境变量。生产禁详细 debug/应用访问日志；管理请求日志仍保留业务用途，限制管理员与 Volume 访问。提交排障信息前手动确认已脱敏。
