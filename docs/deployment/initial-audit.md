# 初始审计（2026-10-19）

## 实际仓库与阶段一结果

- 指定目录 `D:\Flow2API` 初始为空，无本地数据库、Git 仓库或未提交修改。已从用户指定 origin `https://github.com/KevinYoungsir/flow2api` 克隆。
- 基线 HEAD：`60e673b05fe2630189f49e6dd3b275c2c8599158`。开发分支：`deploy/railway-single-service`。未发现 AGENTS.md。
- 已检查 README、两个 main、core/config/database/auth/logger/models、api、services、三个 HTML、示例配置、两个 Dockerfile、全部 Compose 和全部现有测试。
- Python 3.12.10；项目独立 `.venv` 安装 requirements 成功。测试基线见后续阶段报告。
- Railway CLI 5.26.2 已安装；`whoami` 返回 OAuth `invalid_grant` / Unauthorized；`status` 无关联项目。尚未部署、创建服务、修改变量、Volume 或 DNS。
- Docker 不在 PATH，标准 Docker Desktop 安装路径也未找到，容器验收受阻。
- 后续补充：Railway 连接器已可用并识别 KevinYoung 账号；现有 eloquent-enchantment/production 仅有不同仓库的 autowealth-ai 服务。只读盘点完成，目标与新增资源费用待用户确认；详见阶段报告。CLI 状态与连接器授权相互独立。

## 当前架构和风险

| 项目 | 发现 | 处理 |
| --- | --- | --- |
| 启动 | `python main.py` → Uvicorn `src.main:app`；host/port 仅 TOML | PORT 优先，生产强制 0.0.0.0，单 worker |
| 前端 | FastAPI 返回 `/`、`/login`、`/manage`、`/test`；后两者有会话保护；HTML 同源 fetch | 保留页面；补充静态赞助图路由；Tailwind CDN 为外部依赖 |
| 配置 | 缺 setting.toml 时读 example；DB 只在缺行时初始化，随后同步内存 | 保留 DB 设置，区分 bootstrap 变量和每次生效的运行时变量 |
| 凭据 | 示例 admin/admin、han1234；管理员密码明文存 DB；鉴权直接比较 | 生产默认凭据拒绝启动；密码哈希兼容迁移；常量时间比较 |
| SQLite | 根目录 data/flow.db，镜像内 `/app/data/flow.db`；WAL、busy_timeout 30s、进程内写锁 | 一个实例/worker，Volume `/app/data`；增加数据目录变量及数据库就绪探测 |
| 文件 | FileCache 类默认相对 tmp；现有主生成器已显式指定项目绝对 tmp，静态挂载也为项目 tmp；公开 URL 优先 cache.base_url，再请求头 | 在现有一致路径基础上统一支持 TMP_DIR；明确 public URL；缓存为公开且可丢失文件 |
| 会话 | 进程内 set，退出/改密码会撤销，重启丢失；无过期；Cookie HttpOnly/Lax，但 Secure=false | 加过期和生产 Secure、来源检查；保留单进程会话设计 |
| CORS | 任意来源且允许 credentials | 生产明确 HTTPS 白名单，不允许通配 |
| 健康检查 | 已有 `/health`，暴露 Token 汇总且 DB 异常仍 200 | 初始化完成且 DB 可读写才 200；失败 503；只公开状态 |
| metrics | `/metrics` 无鉴权 | 使用管理员会话保护 |
| 日志 | debug 可记录请求体、响应、Cookie；短 Token 可能不遮罩；URL query 可含 key | 生产禁详细 debug、禁 Uvicorn access log（含查询串）；保留脱敏维护路径 |
| Docker | 普通镜像 COPY 全目录；已有 dockerignore 排除部分构建产物，但没有完整排除本地 TOML/数据目录/浏览器资料；不含 Chromium | 扩展既有忽略规则排除状态和秘密；普通镜像沿用，生产拒绝需要本地浏览器的模式 |
| 浏览器 | Dockerfile.headed 安装 Chromium、Xvfb、Fluxbox；标准镜像无此运行时 | 本次不更改验证码/上游限制逻辑；仅有授权时使用现有上游方式 |
| 长请求 | 图片默认 300s、视频 1500s；SSE 支持；任务/槽位主要在内存 | 文档说明边缘请求时限、重启中断、单实例限制；真实验证依赖上游权限 |

## 阻塞项和拟修改文件

本地适配无需用户作产品决定。云端后续必须由用户重新执行 `railway login` 并确认账号、项目、环境、服务和账单；真实凭据通过 Railway Variables/管理后台输入；DNS 修改需用户授权。Docker 测试需要 Docker Desktop 可用。缺合法上游账号，不能验收真实图片/视频。

拟修改：`src/core/config.py`、`database.py`、`auth.py`、`src/main.py`、`src/api/admin.py`、`routes.py`、`src/services/file_cache.py`、根 `main.py`、Dockerfile、忽略文件；新增 railway.json、部署文档、SQLite 备份脚本、验收脚本和部署测试。保留现有 Compose、本地配置及核心生成逻辑。

## 测试方案

1. 在独立环境执行全部现有 unittest（`test*.py` 包含原有非标准命名文件），记录基线。
2. 新增生产配置拒绝、环境/DB 优先级、PORT、CORS/来源限制、Secure Cookie、会话过期、API 鉴权、页面、health 异常、缓存 URL/静态文件和 SQLite 备份恢复测试。
3. 编译检查、完整测试；真实子进程 HTTP 启动并重启，验证 DB/管理员/API Key/配置持久化。
4. Docker 存在时实际 build/run/重建和 Compose config；否则标 BLOCKED，不能标 PASS。
5. Railway 授权后才执行部署、Volume/域名实测；有效上游账号和权限就绪后才执行真实生成。
