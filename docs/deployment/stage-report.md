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
| Railway 配置 | PASS（服务设置已核对） | 先前 schema 静态检查不能证明新服务支持旧 railway.json；平台明确拒绝该方式后已移除，通过连接器设置 Dockerfile/health/资源上限并读取验证 |
| Compose 文件解析 | PASS（静态） | PyYAML 解析全部 4 文件；原文件不变，**没有运行 Compose** |
| Docker build/run/重建/Volume | **BLOCKED** | `docker version` / `docker compose version` 命令不可用；check_docker.py 实际返回 2 / BLOCKED；没有镜像或容器验收成功记录 |

本地日志 `baseline-tests.log`、`regression-tests.log`、`deployment-tests.log`、`final-tests.log` 已被 .gitignore 排除，仅作为本机执行证据。数据库测试在临时目录，不是生产数据；没有测试遗留运行服务。

仍有 Python 3.12 SQLite datetime adapter 和 Starlette/AnyIO 依赖的 DeprecationWarning，不影响本次通过结果。容器基于 Python 3.11，当前只能在 Windows Python 3.12 实测；Linux 镜像构建与运行必须补验。

## 阶段四：云端项目、服务与 Volume 已创建，等待秘密变量

已安装 CLI，首次版本输出 5.26.2。`railway whoami` 返回 OAuth invalid_grant / Unauthorized，status 无关联项目；只读查看过 up/domain/volume/login 实际帮助。

随后 Railway 连接器变为可用并成功授权：账号 `KevinYoung`（@kevinyoungsir），workspace `KevinYoung's Projects`；现有唯一项目 `eloquent-enchantment`（83e87226-36ca-497e-b230-f1d3cc676bec），production 环境（e0607769-04f8-47f9-9ab2-60bfe4fc16ac）。已只读盘点：其中只有连接 `KevinYoungsir/autowealth-ai@main` 的 autowealth-ai 服务、sfo 单副本、500MB 卷挂载 `/data/research_runs`，没有待发布变更。不是当前 Flow2API 仓库，不能替换它来部署本次代码。

用户随后明确授权**新建独立 flow2api 项目、一个应用服务和 /app/data 持久卷，月度上限 5 美元**。已将通过测试的部署分支实际推送到 GitHub，最初代码提交 `330c7b258947528db9eea21a086b1458b0083d1f` 在远端可验证。

早先因试用到期与预算前置条件受阻。用户现已确认 **Hobby 已激活，Compute 硬上限已设为 $5，接受同时影响旧项目**，该前置条件已解决，不再重复询问。

已实际创建并通过 describe-service 读取核对：

- 独立私有项目 flow2api：`a1ad9b63-e582-46b6-9c4a-4566a682c1f1`。
- production 环境：`dcc6e47d-ac81-43a1-88d1-44695fea3bfa`。
- flow2api 服务：`5a28a95f-7579-4595-8755-a9a1aeddb151`。
- flow2api-data 卷：`a5f5a5fe-1b12-46af-b8e4-79be8b3cabf2`，500MB，sfo，挂载 `/app/data`。
- Dockerfile builder，启动 python main.py，/health，启动检查 120 秒，sfo 单副本，0.5 vCPU / 0.5GB 内存限制。
- 已配置 9 个非秘密变量（包括 PORT=8000、生产模式、公开地址、CORS 和数据/缓存目录）。
- Railway 地址：`https://flow2api-production-d82c.up.railway.app`，路由目标端口 8000；尚未以健康检查验收上线。

平台拒绝新服务使用旧 railway.json，已根据当前官方说明改用服务设置；本仓库快照只用于审计，不会自动应用。CLI 的账号授权仍失效，但连接器能完成本次资源操作。

当前等待用户在 Variables 设置 FLOW2API_ADMIN_PASSWORD 和 FLOW2API_API_KEY。已提供操作步骤，不索取秘密值。构建、运行、云端重启持久化仍待真正执行；资源创建不能标记部署成功。

## 阶段五：域名与 HTTPS 未验收

已在新服务添加 socool.xin，实际路由目标为 `vz2fefnk.up.railway.app`，并取得 `_railway-verify.socool.xin` 的实际验证 TXT。完整记录已写入 [domain-dns.md](domain-dns.md)。Railway 返回证书状态 VALIDATING_OWNERSHIP，未声称归属验证或 HTTPS 已完成。

尚未修改阿里云 DNS，需保留原 MX/TXT。早前本地解析与 TLS 探测未成功（可能为本机合成解析/代理环境），不能据此断言全球 DNS 或证书状态。

具体根域 ALIAS、MX/TXT 保留及验证步骤见 [domain-dns.md](domain-dns.md)。实际 Railway 记录、域名归属和证书状态仍待取得。

## 阶段六：真实业务未验收

真实 Google Flow 账号、必要登录态、权限和额度尚未配置。**真实图片生成：NOT RUN；真实视频生成：NOT RUN；生成结果可访问：NOT RUN；云端重启持久化：NOT RUN**。测试夹具、模型目录返回和健康检查均未被当作生成成功。

视频默认应用超时 1500 秒超过 Railway 当前 HTTP 15 分钟上限。SSE 不能突破该总时限，阶段六的较长请求验证仍是开放项；若合法业务实测超过平台窗口，需另行设计可恢复异步任务方案。

## 用户下一步

1. 安装/启动可用 Docker Desktop Linux 容器引擎，以便真实补跑容器与 Compose 验收。
2. 套餐、5 美元工作区硬上限及影响范围已经由用户确认，不再重复要求。使用 CLI 时才需要另行 railway login。
3. 通过 Railway Variables 设置新库管理员密码和本服务 API Key；不在聊天发送秘密。
4. 真实域名记录已取得；确认阿里云 ALIAS 能力和现有 DNS，再授权具体 DNS 修改。
5. 在管理后台配置有权使用的上游账号与必要参数，确认额度消耗后再进行真实图片/视频验收。
