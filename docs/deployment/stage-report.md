# 阶段交付与验收报告

日期：2026-10-19（Asia/Shanghai）。分支：`deploy/railway-single-service`。基线：`60e673b05fe2630189f49e6dd3b275c2c8599158`。最终提交 SHA 使用 `git rev-parse HEAD` 获取（避免把提交本身 SHA 循环写入同一提交）；对话最终报告会提供实际 SHA。

## 阶段一：审计完成

目标目录原为空，已克隆指定仓库并创建部署分支；没有覆盖原工作区或数据库。审计见 [initial-audit.md](initial-audit.md)。本机 Python 3.12.10，独立 `.venv`；首次测试发现 Windows GBK 输出导致两处导入错误及 Pillow 未声明，首次共执行 99 tests / 3 errors，未记为通过。修复测试编码与依赖后，原有 170 tests 全部通过。

## 阶段二：生产适配完成并已本地验收

| 文件组 | 变更及目的 |
| --- | --- |
| main.py、src/core/config.py | PORT 优先、生产 0.0.0.0、单 worker、运行变量校验；明确 DB/初始化变量/TOML 优先级；缺安全配置失败；生产禁详细 debug 和访问日志 |
| src/core/database.py、auth.py | 迁移前读取校验既有凭据；保留 DB 配置；管理员密码兼容 bcrypt 迁移；常量时间比较；实际 SQLite 读写就绪探测 |
| src/api/admin.py、src/main.py | Secure/HttpOnly/Lax Cookie、会话 TTL/撤销、生产管理来源限制；/health 只公开状态并正确返回 503；metrics 鉴权；生产关闭 API 文档；缓存有效地址显示遵守 PUBLIC_BASE_URL 优先级 |
| src/api/routes.py、services/file_cache.py、generation_handler.py | 公开 URL 优先环境配置，统一 TMP_DIR 和静态路径；生成器仅改缓存目录一行，没有修改核心生成逻辑 |
| src/services/flow_frontend.py | 页面到 RPC/StreamChat 的调用内传递 libcurl 更新后的 Cookie 快照，保留作用域和删除；上游 401 仅附加无秘密的上下文标签 |
| Dockerfile、.dockerignore、.gitignore、服务设置快照 | 保留现有镜像启动方式；补齐状态/秘密排除；/health、单副本、不休眠和失败重试配置。云端发现旧 Config as Code 被新服务拒绝，已移除本次添加的根 railway.json，使用服务设置并读取核对 |
| requirements.txt | 补 Pillow（现有代码与测试使用） |
| README、docs/deployment/* | 更新部署入口、健康/metrics 说明；给出变量、备份、根域名方案和排障说明 |
| scripts/*、tests/test*deployment*.py | 可重跑的本地/容器/HTTP 检查、无覆盖 SQLite 快照，以及新增部署边界与真实子进程测试 |

原有 3 个 HTML、4 个 Compose、Dockerfile.headed 均未修改，已用 git diff 核对。未引入额外服务，也没有改写验证码或上游访问控制逻辑。

## 阶段三：本地自动验收

最终实际命令：

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m compileall -q main.py src scripts tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test*.py'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/check_docker.py
```

| 检查 | 结果 | 证据/范围 |
| --- | --- | --- |
| Python 编译 | PASS | main/src/scripts/tests，实际执行 |
| 全部单元与集成测试 | PASS | **196 tests，0 failures，0 errors**；同步诊断补充后最终一次 33.975 秒，原有 170 + 新增 26，并补充既有进程测试断言 |
| 依赖一致性 | PASS | pip check：No broken requirements found |
| HTTP 启动与 PORT | PASS（本地） | 独立 Uvicorn 子进程，临时端口、与源码不同 cwd，配置为 production |
| 登录/退出/改密码 | PASS（本地） | 错密码 401、正确登录、会话撤销、旧密码失效、bcrypt 存储 |
| Cookie / CORS / 来源 | PASS（本地） | 检查 Secure/HttpOnly/Lax/max-age，可信预检成功、非白名单预检和管理写请求拒绝 |
| API Key 鉴权 | PASS（本地） | 缺失/错误 401、有效 Key 获取非空 /v1/models；轮换后旧 Key 失效；拒绝弱 Key |
| 数据库持久化 | PASS（本地进程重启） | 管理设置写入后重新读取，两次完整进程重启；冲突初始化变量和缺省初始化变量均不覆盖 DB 凭据 |
| Token/配置/请求日志路由 | PASS（本地） | 有效管理员会话可读取 /api/tokens、/api/stats、/api/logs；没有上游 Token 的 UI 数据读取 |
| health | PASS（本地） | 初始化中 503、DB 写锁 503、解除后 200；错误无敏感细节；不创建丢失 DB |
| 页面/静态资源 | PASS（本地） | 根与登录页、登录后的管理/测试页、赞助图加载；未登录页面保护；/static/manage.html 不公开 |
| 缓存目录/URL | PASS（路由与 URL 构造） | TMP_DIR 实际文件可通过 /tmp 获取，PUBLIC_BASE_URL 覆盖伪造转发头；文件是测试夹具，**不是生成成功** |
| 生产缺配置失败 | PASS | 子进程退出非 0，未初始化数据库；示例凭据/不安全来源/缺 Volume 元数据测试拒绝 |
| SQLite 备份/恢复演练 | PASS（临时目录） | 在线 WAL 快照、integrity_check、新路径恢复、拒绝覆盖已有目标 |
| 日志秘密检查 | PASS（测试范围） | 子进程日志未包含随机测试密码/Key/已记录的会话；没有执行真实上游日志审计 |
| Railway 配置 | PASS（服务设置已核对） | 先前 schema 静态检查不能证明新服务支持旧 railway.json；平台明确拒绝该方式后已移除，通过连接器设置 Dockerfile/health/资源上限并读取验证 |
| Compose 文件解析 | PASS（静态） | PyYAML 解析全部 4 文件；原文件不变，**没有运行 Compose** |
| 本地 Docker build/run/重建/Volume | **BLOCKED** | `docker version` / `docker compose version` 命令不可用；check_docker.py 实际返回 2 / BLOCKED；云端 Dockerfile 构建和容器运行已另行通过，不代替本地 Compose 验收 |

本地日志 `baseline-tests.log`、`regression-tests.log`、`deployment-tests.log`、`final-tests.log` 已被 .gitignore 排除，仅作为本机执行证据。数据库测试在临时目录，不是生产数据；没有测试遗留运行服务。

仍有 Python 3.12 SQLite datetime adapter 和 Starlette/AnyIO 依赖的 DeprecationWarning，不影响本次通过结果。本地测试运行于 Windows Python 3.12；Python 3.11 Linux 镜像已在 Railway 实际构建和运行，详见下节。

## 阶段四：Railway 部署与重启持久化通过

CLI 5.26.2 的早期 OAuth 失效已通过用户完成 `railway login` 解决，当前 CLI 和连接器均可用，目录已关联正确目标。账号为 `KevinYoung`（@kevinyoungsir），workspace 为 `KevinYoung's Projects`。旧项目 `eloquent-enchantment` 中的 autowealth-ai 未被替换、修改或重启。

用户最初授权独立项目、一个应用服务和 /app/data 卷，月度上限 5 美元。CLI 恢复后核实平台拒绝 Compute 硬上限 5（最低 10，或特殊值 0）；用户随后明确同意 **最高 $10/月并继续部署**。实际读取工作区为 softLimit=5、hardLimit=10，用户接受同时影响旧项目。没有提高到超过授权金额。完整历史见 [budget.md](budget.md)。

已实际创建并读取核对：

- [独立私有项目 flow2api](https://railway.com/project/a1ad9b63-e582-46b6-9c4a-4566a682c1f1)：`a1ad9b63-e582-46b6-9c4a-4566a682c1f1`。
- production：`dcc6e47d-ac81-43a1-88d1-44695fea3bfa`；服务：`5a28a95f-7579-4595-8755-a9a1aeddb151`。
- flow2api-data：`a5f5a5fe-1b12-46af-b8e4-79be8b3cabf2`，500MB，sfo，挂载 `/app/data`。
- Dockerfile builder，python main.py，`/health`，120 秒检查，单副本，不休眠，0.5 vCPU / 0.5GB 内存上限。
- 已应用生产运行变量及用户手动设置的两个秘密变量；秘密值未回显、写入文件或提交。
- 当前源码固定为 **`5d6c401df4330b411c4f8c6aec92677455f81af3`**，分支 deploy/railway-single-service；首个可运行版本为 4e4519f，缓存地址修复版为 bb1cc904，插件来源修复版为 95b22111，会话连续性修复版为 d2053ea2。后续文档提交不会改变当前固定的运行版本。
- 正式地址 [https://socool.xin](https://socool.xin)，[Railway 地址](https://flow2api-production-d82c.up.railway.app)继续可用，均指向 8000；PUBLIC_BASE_URL 为根域，CORS 同时包含两个地址。

首个部署 `a36c4b4c-9cfa-4116-ab99-d8938c54704b` 镜像构建通过，但因 API Key 少于 32 字符而安全启动失败。用户更新 Key 后，部署 `743a372a-cd29-423a-b642-3ac7a02795b4` SUCCESS；16:36:55（Asia/Shanghai）授权重启后通过持久化检查。根域切换与显示修复分别发布为 588caffd 和 e935c3c0（SUCCESS，16:55:54）。随后插件来源修复为 ca4df022（SUCCESS，17:19:13），会话连续性修复为 104c3d82（SUCCESS，17:37:54）。当前诊断版本部署 **`d5528bcf-0012-491b-b751-43d90a78ebd9`（SUCCESS，17:53:14）**。运行日志已确认监听 `0.0.0.0:8000`、识别既有数据库、迁移完成。当前 1/1 副本在线、0 crashed，无待发布变更；控制台仍显示首个历史失败，不代表当前部署失败。Uvicorn 的 INFO 行被平台归入 stderr/error，不是应用启动异常。

| 云端检查 | 实际结果 |
| --- | --- |
| Dockerfile 构建、Linux 容器运行、Volume | PASS；SSH 确认 `/app/data/flow.db` 存在，122880 字节，数据/缓存目录可访问 |
| HTTPS 与页面 | PASS；/health 200，首页和登录页 200；HTTP 根路径 301 到同地址 HTTPS |
| 管理员及 API | PASS；正确登录、错误密码 401、Secure/HttpOnly/Lax Cookie、退出后会话撤销；manage/test/tokens/logs/stats 可读；正确 Key 返回非空模型目录，错误 Key 401 |
| 设置保存与重启 | PASS；写入 error_ban_threshold 测试标记，独立读取 PID 1 启动时间；用户明确授权后重启同一部署，确认启动时间改变、设置仍在，然后恢复原值并重新读取 |
| 重启校验反例 | PASS；未重启时运行验证，脚本明确拒绝认定重启。早先被审批拒绝重启后的标记读取已作废，不计入通过证据 |
| 云端在线备份 | PASS；`/app/data/backups/flow-20261019-post-restart.db` 已创建，integrity_check=ok；备份在同一卷，不是异地备份，未覆盖活跃数据库 |
| 静态图片与缓存 URL | PASS；实际赞助 PNG 200；本次专用空文件 /tmp URL 200，清理后 404；此项仅证明路由，不代表生成成功 |
| 资源抽样 | 空闲内存约 0.065 GB，CPU 约 0.001 vCPU，磁盘约 0.033 GB；短时样本不能推算稳定月费 |

新增 `scripts/check_railway_authenticated.py` 通过 CLI 子进程内存读取初始化凭据，不把变量值传入命令行、输出或状态文件。重启状态文件只保存原/测试整数、目标 ID 和进程启动标记，位于被忽略的 tmp。生产库初始化后在后台轮换的密码/Key 不会被旧 Variables 覆盖；以后使用该脚本需注意其使用的是初始化变量。

## 阶段五：根域名、HTTPS 和管理/API 已通过

用户在阿里云添加实际 CNAME/TXT 后，公网查询两条记录完全匹配。Railway 从 VALIDATING_OWNERSHIP 转为 ISSUING，16:48（Asia/Shanghai）确认 **verified=true、证书 VALID、路由 PROPAGATED**，HTTPS /health 实际 200；没有忽略 TLS 错误。完整记录见 [domain-dns.md](domain-dns.md)。

已仅发布 FLOW2API_PUBLIC_BASE_URL=https://socool.xin；既有 CORS 已含根域及 Railway 地址，无需改动。部署 `588caffd-9520-4252-b556-08707ab4e7ef` 为 SUCCESS、1/1 在线；根域上带真实 Origin 的登录/退出、安全 Cookie、管理与测试页、Token/日志/统计、正确/错误 API Key、模型目录均通过。发布前配置标记在新进程保留并恢复原值，额外验证了重新部署的 SQLite 持久化。

根域验收发现管理后台 GET /api/cache/config 的 effective_base_url 忽略生产环境变量而显示 127.0.0.1；生成器本身已有环境优先级。已在真实 Uvicorn 集成测试加入 DB 保留旧本机地址的场景，修复前实际失败，修复为 PUBLIC_BASE_URL 优先后重跑全套测试。未改动前端或生成逻辑。

修复提交 bb1cc904 已实际发布为 e935c3c0，根域验收脚本全部通过，包括有效缓存地址 https://socool.xin、携带根域 Origin 的登录/写配置、API 与重新部署后的 SQLite 标记保留；原测试设置已恢复。根域 HTTP → HTTPS 为 301；首页、登录页、health、实际赞助图均 200。根域 CORS 预检 200、非可信来源预检 400、非可信管理写请求 403。专用空文件 /tmp 路由返回 200，测试文件随后删除；仅证明路由，不是图片/视频生成结果。

## 阶段六：真实业务未验收

云端启动日志显示 Total tokens: 0。真实 Google Flow 账号、必要登录态、权限和额度尚未配置。**真实图片生成：NOT RUN；真实视频生成：NOT RUN；生成结果可访问：NOT RUN**。云端重启持久化已通过，测试夹具、模型目录返回和健康检查均未被当作生成成功。

用户随后授权各执行一次真实图片和视频生成。2026-10-19 17:06（Asia/Shanghai）调用前预检：正式域名与 Railway 备用域名的管理员登录均成功，GET /api/tokens 均为 HTTP 200 且返回空数组，账号总数和启用数均为 0；不是鉴权错误或两域名数据不同。未提交生成请求，以上真实生成项目继续为 NOT RUN。已请用户在正式后台保存上游账号并确认列表出现启用记录；不在聊天接收 Token/Cookie/密码。

用户随后提供 Chrome Token Updater 的 `403: Untrusted request origin`。已核对配套插件源码：后台同步通过 Authorization Bearer 独立连接令牌调用 /api/plugin/update-token。部署新增的通用管理来源保护在该专用鉴权之前拦截了扩展 Origin。修复只让 POST /api/plugin/update-token 与 POST /api/plugin/check-tokens 进入其既有独立连接令牌鉴权，不改变其他管理写接口来源校验或 HTTPS CORS 白名单。4 项新增 HTTP 回归测试在修复前真实失败，修复后全套 189 项通过；覆盖正确/错误/缺失插件令牌、管理员 Cookie 不能代替插件令牌、非插件管理写接口继续 403，受控上游校验异常与真实生成结果严格区分。

95b22111 已实际发布，云端以扩展 Origin 与独立连接令牌、完全不带管理员 Cookie 调用 POST /api/plugin/check-tokens 得到 200。两个插件端点无令牌/错误令牌均 401，其他管理写接口仍 403；管理登录/退出、Cookie、API Key、有效缓存 URL 的线上回归全部通过。独立连接令牌已存在且未重置、未回显。测试时上游账号仍为 0；已请用户在本机插件点击立即同步，尚未声称真实 Cookie 上传、上游登录或图片/视频生成成功。[核对的插件实现](https://github.com/TheSmallHanCat/Flow2API-Token-Updater/blob/main/background.js)

用户随后提供 17:22 的新错误：服务返回 400，内层 Google 登录态校验 RPC nzlxg 返回 401。云端代理记录确认修复后 17:21—17:22 有三次 POST /api/plugin/update-token 返回 400；此错误发生在独立连接令牌通过后，已不再是来源拦截。当前只能确认 Google 未接受同步的登录态，无法仅凭该状态判断过期、账号混用或客户端兼容性。已请用户确认同一 Chrome 配置中的 Flow 项目页与插件邮箱一致，并在需要时重新登录后同步；没有放宽上游校验或把失败会话保存为可用账号。真实图片/视频继续 NOT RUN。

用户确认同一 Chrome 配置中的 Flow 页面正常且账号一致后，继续审计发现 bootstrap GET 与后续 RPC/StreamChat 使用独立快照，响应更新/删除的 Cookie 丢失。4 项合成会话测试实际复现了后续请求仍使用旧值的问题。修复复用已有 Cookie jar/导出逻辑：GET 使用带作用域的 jar，读取 libcurl 完整快照（含重定向更新、删除），在同一次调用内传给后续请求；不改变生成参数、验证码或上游拒绝处理。测试覆盖轮换、删除、域/路径隔离、登录重定向拒绝；上游仍返回 401 时，只附加 page_identity=present/missing/unknown 与 cookies_changed=yes/no/unknown，不输出邮箱、Cookie、XSRF 或会话 ID。全套 193 项通过。此为已复现兼容缺陷的修复，是否解决用户真实 401 仍需插件重新同步，未把合成测试作为真实登录或生成通过。

会话兼容修复 d2053ea2 已发布为 104c3d82（SUCCESS，17:37:54）。用户重试仍得到 `rpc=nzlxg, code=401 [page_identity=missing; cookies_changed=yes]`；不能把缺少页面身份字段直接解释为匿名页面，也不能把这个已复现缺陷的修复记为真实同步通过。用户再次确认后台和插件为同一账号，页面地址不含 authuser 或 /u/ 账号序号。

17:38:28 云端管理接口 POST /api/tokens 实际 200，随后只读检查确认已有 1 个启用账号，来源不是插件的默认添加备注；该记录包含有作用域的 Cookie，没有分区、过期或非根路径记录，也未配置账号专用代理。真实 POST /api/tokens/{id}/refresh-credits 返回 200 且余额为正，证明已保存会话可完成 Google 余额 RPC；没有提交生成任务，也不能据此认定插件上传会话相同或有效。插件和管理添加路径均调用同一个 st_to_at 校验方法。

为继续定位两份会话差异，5d6c401 增加仅在插件独立鉴权通过、上游 nzlxg 返回 401 后执行的比较：对同邮箱既有记录，按项目页和 RPC URL 的实际 Cookie 范围比较，只返回 stored_session、auth_values 的 same/different 标签及 missing_auth/extra_auth 数量。没有既有记录时返回 missing，诊断读取失败返回 unknown；不会输出 Cookie 值、邮箱、连接令牌，也不会保存失败上传。3 项新增回归覆盖脱敏、不写账号、域/路径范围、JSON 格式差异和诊断异常不掩盖原拒绝；全套 196 项通过。诊断本身不修复上游拒绝，真实同步仍待用户重试结果。

5d6c401 已固定发布为 d5528bcf，平台确认 1/1 在线、无 staged/applying 变更、500 MB Volume 仍挂载 /app/data。正式域名实际回归全部通过：health、未登录管理保护、错误密码、登录、安全 Cookie、管理/测试页面、Token/日志/统计读取、缓存有效地址、正确/错误 API Key、非空模型目录、退出与会话撤销。已请用户重试一次插件以取得新标签。

生成预检确认该账号启用、图片和视频开关开启、凭据未到期且有余额；当前验证码方式 yescaptcha 的密钥仍为空。已请用户仅在后台填写已有且符合上游使用规则的配置，不要求新购或在聊天发送密钥。**真实图片生成、真实视频生成、生成媒体访问继续为 NOT RUN**，不会提交已知缺配置的任务，也未调整验证码或访问限制。

视频默认应用超时 1500 秒超过 Railway 当前 HTTP 15 分钟上限。SSE 不能突破该总时限，阶段六的较长请求验证仍是开放项；若合法业务实测超过平台窗口，需另行设计可恢复异步任务方案。

## 用户下一步

1. 后台已有 1 个可查询余额的启用账号，无需重复添加。插件同步仍被 Google 拒绝，需取得带新会话比较标签的重试结果；真实生成还需在后台补齐现有合法配置，不在聊天发送 Token/Cookie/密钥。DNS 无需重复修改。
2. 如需补齐本地容器/Compose 验收，安装并启动 Docker Desktop Linux 容器引擎后运行现有检查脚本。此项不阻止当前已通过的 Railway 容器部署。
