# Railway Variables

生产秘密通过 Railway 服务的 Variables 界面输入，不放到 Git、Dockerfile、HTML、聊天或命令行历史中。`FLOW2API_API_KEY` 是本服务的客户端鉴权密钥，不是 OpenAI/Google 的 Key。无需 OpenAI 平台账号。

## 每次进程启动生效的运行时设置

| 名称 | 必填 | 默认 / 行为 | 要求 |
| --- | --- | --- | --- |
| `FLOW2API_ENV` | Railway 建议设 `production` | 本地 `development`；检测到 `RAILWAY_PROJECT_ID` 或 `RAILWAY_ENVIRONMENT_ID` 时始终为生产 | Railway 无法用 development 关闭生产校验 |
| `PORT` | Railway 自动提供 | 缺省读取 TOML server.port（8000） | 整数 1..65535；存在 PORT 或生产时 host 强制 0.0.0.0 |
| `FLOW2API_PUBLIC_BASE_URL` | 生产必填 | 无默认 | 对外 HTTPS origin，不带路径/查询；最终目标 `https://socool.xin`；调试域名阶段填实际 Railway HTTPS 地址 |
| `FLOW2API_CORS_ORIGINS` | 生产必填 | 本地空列表，仅同源使用 | 逗号分隔的明确 origin；生产必须 HTTPS，包含 PUBLIC_BASE_URL，禁止 `*`；同样用于管理 API 的浏览器 Origin 校验 |
| `FLOW2API_DATA_DIR` | 否 | 项目根目录/data，镜像为 `/app/data` | 放 flow.db；不要指向 tmp 或源码；需要持久卷 |
| `RAILWAY_VOLUME_MOUNT_PATH` | Railway 必须实际附加 Volume | Railway 自动注入 | 必须与 DATA_DIR 一致；不要手动伪造此变量来绕过检查 |
| `RAILWAY_PROJECT_ID` / `RAILWAY_ENVIRONMENT_ID` | Railway 自动提供 | 用于自动识别生产 | 无需手填 |
| `FLOW2API_TMP_DIR` | 否 | 项目根目录/tmp，镜像为 `/app/tmp` | 文件缓存目录，同时挂载为公开 `/tmp`；不存放秘密 |
| `FLOW2API_SESSION_TTL_SECONDS` | 否 | 43200（12 小时） | 60..604800；Cookie max-age 和服务端过期一致 |
| `PYTHONUNBUFFERED` | 镜像内已设 | 1 | 实时运行日志 |
| `PYTHONDONTWRITEBYTECODE` | 镜像内已设 | 1 | 避免生成 pyc |

## 只用于缺失数据库配置行的初始化值

优先级为 **已存在数据库行 > 初始化环境变量 > setting.toml > setting_example.toml**。不是将示例与用户 TOML 做字段级合并；有本地 setting.toml 时读取该文件。镜像排除本地配置，使用仓库示例结构加环境变量即可启动。

| 名称 | 新生产库必填 | 默认 / 行为 | 安全要求 |
| --- | --- | --- | --- |
| `FLOW2API_ADMIN_USERNAME` | 建议填 | TOML 示例为 admin | 非空；用户名不属于密码 |
| `FLOW2API_ADMIN_PASSWORD` | 是 | 本地示例 admin 在生产会拒绝 | 建议密码管理器随机生成至少 24 字符；最低 16 字符且不超过 72 UTF-8 字节；数据库保存 bcrypt 哈希 |
| `FLOW2API_API_KEY` | 是 | 本地示例 han1234 在生产会拒绝 | 随机生成至少 32 字符；客户端通过 Authorization Bearer 提供 |
| `FLOW2API_CACHE_ENABLED` | 否 | 示例 false | `true/false/1/0`；启用后结果可复制到公开 tmp |
| `FLOW2API_CACHE_TIMEOUT` | 否 | 7200 秒 | 非负整数；0 只禁用自动清理，不提供持久性保证 |
| `FLOW2API_IMAGE_TIMEOUT` | 否 | 300 秒 | 正整数；应用超时不是 Railway 边缘时限 |
| `FLOW2API_VIDEO_TIMEOUT` | 否 | 1500 秒 | 正整数；超过 Railway HTTP 上限，必须结合长请求限制评估 |

运行时设置（PORT、来源、目录、TTL、PUBLIC_BASE_URL）不写入 DB，每次运行都优先按环境变量读取。PUBLIC_BASE_URL 同时覆盖 DB 中 cache.base_url 和请求转发头，因此生产结果不会使用容器地址或伪造 Host。

管理员在网页改密码/API Key/超时/缓存/其他受支持设置后，数据库立即生效；重启不会用 Variables 的旧初始化值覆盖。已存在弱凭据库会拒绝上线，即使填了新的初始化变量也不会静默改库：先备份，在可信本地模式登录原库并更改密码/API Key，再迁移该库。

原有明文管理员密码在应用启动时兼容迁移成 bcrypt。上游 Token、Cookie、服务 API Key 仍需读回用于调用，保存在 SQLite 中，不是加密保管库；备份和 Volume 均需限制访问。切勿把含秘密的数据库或备份放进 /tmp。

上游账号、其他供应商配置通过现有管理后台保存；本次不新增绕过上游访问控制的机制，也没有为所有 TOML 字段提供任意环境映射。生产始终关闭详细 debug，管理端尝试开启会返回 400；Uvicorn 访问日志关闭以避免 key 查询参数进入应用日志。客户端优先使用 Authorization，避免 URL 传 Key。

验收脚本可选 `FLOW2API_CHECK_API_KEY` 仅供本地只读检查使用，不是服务运行变量。不要在公共流水线输出环境变量。

Chrome Token Updater 的连接地址是 `https://socool.xin/api/plugin/update-token`，连接令牌在管理后台的插件配置中单独管理。POST `/api/plugin/update-token` 与 `/api/plugin/check-tokens` 始终验证独立 Authorization 连接令牌，管理员 Cookie 不能替代；它们不依靠管理 Cookie 的 Origin 防护。其他管理写接口继续使用明确来源白名单，不为插件同步添加 CORS 通配符。
