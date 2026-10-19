# Flow2API Railway 单服务部署

一个 FastAPI/Uvicorn 进程同时提供管理 HTML 和兼容 API；SQLite 保持单实例设计，不使用 Vercel、S3 或 Redis。当前验收和阻塞情况见 [阶段报告](stage-report.md)。

## 1. 本地验证

```powershell
Set-Location D:\Flow2API
git switch deploy/railway-single-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\validate_local.ps1
```

脚本先编译再运行 `test*.py` 全部 unittest，包含现有 `testgeneration_config_max_retries.py`。其中进程验收启动临时数据目录，实际访问 HTTP、写配置、轮换测试凭据并重启；没有调用真实上游。Docker 未安装时输出 BLOCKED；不会把该状态作为 Docker 验收通过。

`scripts/check_docker.py` 在 Docker Desktop Linux 容器引擎可用时，实际构建、校验 Compose、启动容器、写入设置、重建容器并检查 Volume 数据；仅清理自己创建的随机名称容器和测试卷。该脚本会生成临时合成凭据，不回显秘密。镜像保留用于检查。当前尚未在本机完成 Docker 验收。

## 2. 账号和目标确认

本机 CLI 的 `railway whoami` 返回 Unauthorized / OAuth invalid_grant，`railway status` 没有关联项目。随后启用的 Railway 连接器已授权成功，识别为 `KevinYoung`（@kevinyoungsir）；唯一可见项目 `eloquent-enchantment` 的 production 环境已有不同仓库的 `autowealth-ai` 服务及持久卷，不是 Flow2API 部署目标。已只读盘点，没有改动该项目。

可以继续通过连接器操作，无需为此重新登录 CLI；但必须先由用户确认是新建独立项目还是在既有项目增加服务、允许的资源费用，以及生产初始化凭据的设置方式。若选择 CLI 路径，再由用户运行：

```powershell
railway login
railway whoami
railway link
railway status
```

关联前确认具体 workspace/account、project、environment、service，以及允许的账单/资源额度。不要直接运行未关联的 `railway up -y`：本机 CLI 的帮助显示这可能自动创建项目和服务。本次没有创建资源或触发部署。

GitHub 自动部署需将本分支推送并授权 Railway 读取该仓库；本次只准备本地分支。也可在确认目标后从本地上传部署当前 checkout；CLI 上传不是 GitHub 分支绑定。

## 3. Railway 服务设置

1. 使用根 Dockerfile，保留镜像 CMD `python main.py`，不另写绕过配置校验的 Uvicorn 多 worker 命令。
2. 附加一个持久 Volume，挂载 `/app/data`。不要在构建或 pre-deploy 阶段初始化数据库。迁移随服务启动执行。
3. 阅读 [变量表](environment-variables.md)，在 Variables 设置生产模式、安全初始化凭据、公开 HTTPS 地址和 CORS 来源。不要复制本地示例密码/API Key。
4. 根 `railway.json` 选择 DOCKERFILE、`/health`、120 秒启动检查、失败最多重试 3 次、单副本。控制台确认只有一个区域一个实例，关闭不适合本服务长任务的休眠设置。
5. 标准镜像没有本地浏览器运行时，生产配置不能选 browser/personal/extension；不会通过自动下载浏览器或规避上游限制完成部署。原有 headed Dockerfile/Compose 仍供原本的本地工作流使用。

Railway 持久卷仅在运行阶段挂载，并自动注入挂载路径变量；服务依靠该变量检查 DATA_DIR 与卷路径一致。此检查不替代云端查看 Volume 及重启验证。[Railway Volumes](https://docs.railway.com/volumes)

## 4. 部署和上线检查

确认账号、目标、费用、Variables、Volume 以后，在指定分支执行：

```powershell
railway status
railway up --service <确认后的服务> --environment <确认后的环境>
railway logs --help
railway logs
```

本机 CLI `up --detach` 仅提交部署，不代表健康。查看构建与部署结果，确认运行日志 `0.0.0.0:<PORT>`、/health 200、卷路径 `/app/data`、数据库存在；不导出 Variables 或包含秘密的日志。

用实际 Railway HTTPS 域名先验收：将 PUBLIC_BASE_URL/CORS 配置为该域名，执行 `python scripts/check_deployment.py https://<实际域名>`。可通过本地 `FLOW2API_CHECK_API_KEY` 加入鉴权模型检查。不要照抄占位地址，也不要通过关闭 TLS 验证解决证书问题。

浏览器验证登录→管理数据→保存设置→重新读取→退出；重启云端实例后重新登录并确认设置、Token、日志保留。内存会话重启失效属于预期。然后按 [DNS 指南](domain-dns.md) 绑定 socool.xin 并更新两个 URL 变量。

Railway 会按配置调用健康检查；本服务仅在必要初始化完成且数据库能进行写事务时返回 200，不要求先导入上游账号，也不会在健康检查中发起图片/视频请求。[Railway Healthchecks](https://docs.railway.com/deployments/healthchecks)

## 5. 生成文件和长期数据

- `/app/data/flow.db`、WAL/SHM：管理配置、Token/Cookie、任务和请求日志，必须持久保存。
- `/app/tmp`：可清理缓存及生成结果的本地副本，公开 URL 为 `PUBLIC_BASE_URL/tmp/<文件名>`。首次上线不挂持久卷，重建/迁移后可能丢失；同一容器进程重启时偶尔保留不构成持久保证。关闭缓存时仍可能返回有有效期的上游链接。
- 真正需要长期保存的图片/视频，下载至受控存储；本次不自动增加额外存储服务。不要在缓存目录放数据库、Cookie 或备份。

## 6. 长请求与单实例限制

Railway 当前 HTTP 最长 15 分钟，持续无数据传输 5 分钟会关闭连接。项目视频默认超时 1500 秒，超过平台上限；SSE 流式进度可以避免空闲中断，但无法突破总时限。优先使用现有 `stream=true`，客户端读取超时需匹配；不要把提高 Uvicorn keep-alive 当成长任务解决方案。[Railway 网络时限](https://docs.railway.com/networking/public-networking/specs-and-limits)

单实例/单 worker 维持会话、并发槽位及 SQLite 写锁的一致性。滚动重建、强制停止、内存不足会中断进行中的请求，当前没有持久任务队列/可恢复作业承诺；优先在无生成任务时部署。若真实视频超过 15 分钟，异步任务提交/查询的设计是单独的后续工作，阶段六该项必须保留未通过，不能用本地测试代替。没有上游账号时也无法验证 Railway 到上游网络、授权、额度和实际延迟。

## 7. SQLite 备份与恢复

在线备份使用 SQLite backup API（含 WAL 中已提交的数据），不在运行时只复制主 DB 文件：

```powershell
.\.venv\Scripts\python.exe scripts/sqlite_backup.py data/flow.db backups/flow-<时间戳>.db
.\.venv\Scripts\python.exe scripts/sqlite_backup.py backups/flow-<时间戳>.db backups/restore-rehearsal-<时间戳>.db
```

在运行容器内可调用 `python /app/scripts/sqlite_backup.py /app/data/flow.db /app/data/backups/flow-<时间戳>.db`。命令中的时间戳需要实际替换，目标必须不存在。脚本运行 integrity_check，拒绝覆盖；容器备份仍在同一卷，应另行下载到受控的外部备份位置。

恢复演练：在新路径/新卷恢复快照，单独启动隔离实例，检查登录、配置、行数、integrity_check。正式恢复先暂停写入并备份当前版本，由用户确认后切换到验证过的卷/数据库；保留原卷回滚，不直接覆盖活跃 flow.db 或删除 WAL/SHM。本次只在临时目录真实执行了快照和新路径恢复，没有触碰生产数据。

SQLite Schema 迁移沿用已有增列/补表，缺行补齐，不覆盖已有设置。版本回滚可能不兼容新 Schema，先备份再部署。Railway config 以仓库配置为准，Volume、域名和 Variables 仍需在目标服务实际确认。[配置参考](https://docs.railway.com/config-as-code/reference)
