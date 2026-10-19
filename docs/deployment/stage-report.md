# 阶段交付与验收报告

日期：2026-10-19（Asia/Shanghai）。分支：`deploy/railway-single-service`。基线：`60e673b05fe2630189f49e6dd3b275c2c8599158`。最终提交 SHA 使用 `git rev-parse HEAD` 获取（避免把提交本身 SHA 循环写入同一提交）；对话最终报告会提供实际 SHA。

## 阶段一：审计完成

目标目录原为空，已克隆指定仓库并创建部署分支；没有覆盖原工作区或数据库。审计见 [initial-audit.md](initial-audit.md)。本机 Python 3.12.10，独立 `.venv`；首次测试发现 Windows GBK 输出导致两处导入错误及 Pillow 未声明，首次共执行 99 tests / 3 errors，未记为通过。修复测试编码与依赖后，原有 170 tests 全部通过。

## 阶段二：生产适配完成并已本地验收

| 文件组 | 变更及目的 |
| --- | --- |
| main.py、src/core/config.py | PORT 优先、生产 0.0.0.0、单 worker、运行变量校验；明确 DB/初始化变量/TOML 优先级；缺安全配置失败；生产禁详细 debug 和访问日志 |
| src/core/database.py、auth.py | 迁移前读取校验既有凭据；保留 DB 配置；管理员密码兼容 bcrypt 迁移；常量时间比较；实际 SQLite 读写就绪探测 |
| src/api/admin.py、src/main.py | Secure/HttpOnly/Lax Cookie、会话 TTL/撤销、生产管理来源限制；/health 只公开状态并正确返回 503；metrics 鉴权；生产关闭 API 文档 |
| src/api/routes.py、services/file_cache.py、generation_handler.py | 公开 URL 优先环境配置，统一 TMP_DIR 和静态路径；生成器仅改缓存目录一行，没有修改核心生成逻辑 |
| Dockerfile、.dockerignore、.gitignore、railway.json | 保留现有镜像启动方式；补齐状态/秘密排除；/health、单副本、不休眠和失败重试配置 |
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
| 全部单元与集成测试 | PASS | **185 tests，0 failures，0 errors**；最终一次 28.030 秒，原有 170 + 新增 15 |
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
| Railway 配置字段 | PASS（静态） | 读取实时官方 railway.schema.json，检查所用字段和构建器取值；不等于云端部署 |
| Compose 文件解析 | PASS（静态） | PyYAML 解析全部 4 文件；原文件不变，**没有运行 Compose** |
| Docker build/run/重建/Volume | **BLOCKED** | `docker version` / `docker compose version` 命令不可用；check_docker.py 实际返回 2 / BLOCKED；没有镜像或容器验收成功记录 |

本地日志 `baseline-tests.log`、`regression-tests.log`、`deployment-tests.log`、`final-tests.log` 已被 .gitignore 排除，仅作为本机执行证据。数据库测试在临时目录，不是生产数据；没有测试遗留运行服务。

仍有 Python 3.12 SQLite datetime adapter 和 Starlette/AnyIO 依赖的 DeprecationWarning，不影响本次通过结果。容器基于 Python 3.11，当前只能在 Windows Python 3.12 实测；Linux 镜像构建与运行必须补验。

## 阶段四：分支已推送，Railway 套餐阻塞

已安装 CLI，首次版本输出 5.26.2。`railway whoami` 返回 OAuth invalid_grant / Unauthorized，status 无关联项目；只读查看过 up/domain/volume/login 实际帮助。

随后 Railway 连接器变为可用并成功授权：账号 `KevinYoung`（@kevinyoungsir），workspace `KevinYoung's Projects`；现有唯一项目 `eloquent-enchantment`（83e87226-36ca-497e-b230-f1d3cc676bec），production 环境（e0607769-04f8-47f9-9ab2-60bfe4fc16ac）。已只读盘点：其中只有连接 `KevinYoungsir/autowealth-ai@main` 的 autowealth-ai 服务、sfo 单副本、500MB 卷挂载 `/data/research_runs`，没有待发布变更。不是当前 Flow2API 仓库，不能替换它来部署本次代码。

用户随后明确授权**新建独立 flow2api 项目、一个应用服务和 /app/data 持久卷，月度上限 5 美元**。已将通过测试的部署分支实际推送到 GitHub，最初代码提交 `330c7b258947528db9eea21a086b1458b0083d1f` 在远端可验证。

已实际尝试创建私有 flow2api 项目，Railway 返回：`Your trial has expired. Please select a plan to continue using Railway.` 随后重新列举项目确认没有新建成功。没有创建服务/卷、触发构建部署或设置真实 Variables，无法确认 Flow2API 云端端口、挂载、运行日志或健康检查。

用户最新已确认 **Hobby 已激活，硬上限尚未设置**，因此套餐激活问题已由用户确认解决。当前阻塞只剩 **5 美元硬预算的工作区限额安排及生效核实**。Hobby 每月 5 美元是最低消费而非封顶，硬限额影响整个工作区（含现有 autowealth-ai）。连接器无费用限额工具，CLI 未登录，浏览器读取受 MXC 启动器错误阻塞；已提供用户手动设置入口和步骤。没有擅自改变工作区限额或影响旧项目。详见 [预算与授权记录](budget.md)。

## 阶段五：域名与 HTTPS 未验收

没有添加 Railway 自定义域名，未取得路由/验证记录，没有改动阿里云 DNS。只读本地查询显示 NS 为 dns31/dns32.hichina.com，本机 A 查询得到 198.18.2.137（代理/合成解析环境的可能性，不能作为公网实际源站地址）。curl 对 HTTPS /health 返回状态 000/TLS handshake failed，HTTP 也没有获得有效响应；这只说明本机探测未成功，不能据此断言全球 DNS 或证书状态。

具体根域 ALIAS、MX/TXT 保留及验证步骤见 [domain-dns.md](domain-dns.md)。实际 Railway 记录、域名归属和证书状态仍待取得。

## 阶段六：真实业务未验收

真实 Google Flow 账号、必要登录态、权限和额度尚未配置。**真实图片生成：NOT RUN；真实视频生成：NOT RUN；生成结果可访问：NOT RUN；云端重启持久化：NOT RUN**。测试夹具、模型目录返回和健康检查均未被当作生成成功。

视频默认应用超时 1500 秒超过 Railway 当前 HTTP 15 分钟上限。SSE 不能突破该总时限，阶段六的较长请求验证仍是开放项；若合法业务实测超过平台窗口，需另行设计可恢复异步任务方案。

## 用户下一步

1. 安装/启动可用 Docker Desktop Linux 容器引擎，以便真实补跑容器与 Compose 验收。
2. 部署目标和 5 美元月度上限已经确认；在 Railway 控制台激活适合该预算的套餐，并确认工作区限额及对旧项目的影响。使用 CLI 时才需要另行 railway login。
3. 通过 Railway Variables 设置新库管理员密码和本服务 API Key；不在聊天发送秘密。
4. 服务上线后取得真实域名记录，确认阿里云 ALIAS 能力和现有 DNS，再授权具体 DNS 修改。
5. 在管理后台配置有权使用的上游账号与必要参数，确认额度消耗后再进行真实图片/视频验收。
