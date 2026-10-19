# 排障

| 现象 | 检查与处理 |
| --- | --- |
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
