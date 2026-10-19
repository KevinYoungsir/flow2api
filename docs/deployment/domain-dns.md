# socool.xin 域名与 DNS

已在独立 Railway flow2api 服务添加 socool.xin，取得以下实际记录；尚未修改阿里云 DNS。2026-10-19 云端重启验收后复查：verified=false，路由记录 REQUIRES_UPDATE，证书为 `CERTIFICATE_STATUS_TYPE_VALIDATING_OWNERSHIP`。Railway 自带 HTTPS 地址已经上线，根域名尚未上线。

| 用途 | 阿里云主机记录 | Railway 实际要求值 |
| --- | --- | --- |
| 根域路由（CNAME；已有记录时先确认冲突） | @ | `vz2fefnk.up.railway.app` |
| 所有权 TXT | _railway-verify | `railway-verify=8d6b5abe35bc40154e038eea5a1c024fc36be844d7afcffa5735278e039faf87` |

Railway 返回的路由类型是 CNAME。该 TXT 值用于公开 DNS 归属验证，不是管理员密码或 API Key。服务端口为已配置的 PORT=8000。

## 当前阿里云操作步骤

1. 打开阿里云控制台 → 云解析 DNS → 公网权威解析 → socool.xin → 解析设置，先导出/保留现有记录。
2. 查看主机记录 @ 是否已有 A/AAAA/CNAME/ALIAS/MX/TXT 等记录。已有时先保留并说明类型，不直接删除或覆盖；可以先单独添加下述验证 TXT。
3. @ 无现有记录时，添加类型 CNAME、主机记录 @、记录值 `vz2fefnk.up.railway.app`、默认线路、TTL 600 秒。值不带 https://、端口或路径。
4. 添加类型 TXT、主机记录 `_railway-verify`、记录值为上表完整 `railway-verify=...`，默认线路、TTL 600 秒；主机记录不重复附加 socool.xin。
5. 保存后通知部署人员，以 Railway 实际归属/证书状态与 HTTPS 请求继续验收。不要把 DNS 已保存等同于证书已生效。

这是用户原要求亲自介入的 DNS 修改；本次没有使用阿里云账号、API 密钥或更换托管。普通 CNAME 方案是否适用取决于现有记录；无需先购买付费 DNS。

## 获取真实记录

先完成 Railway 服务部署并确认账号、服务、环境和端口。已实际检查本机 `railway domain --help`，支持创建、list、status 和证书命令。获得用户对域名绑定/DNS 的授权后：

```powershell
railway domain socool.xin --service <确认后的服务> --environment <确认后的环境> --json
railway domain status socool.xin --service <确认后的服务> --environment <确认后的环境> --json
```

端口应与当前服务的 PORT 一致；只有实际知道端口后才填写 `--port`。输出中的目标域名、所有权验证记录名和值必须逐字采用，不猜测。也可在 Railway Settings → Networking 中查看。按当前官方说明，通常同时需要路由记录和验证 TXT。[Railway 域名说明](https://docs.railway.com/networking/domains/working-with-domains)

| 类型 | 阿里云主机记录 | 值 | 当前状态 |
| --- | --- | --- | --- |
| 根域路由 CNAME（有冲突时另行确认） | @ | vz2fefnk.up.railway.app | 已取得，尚未修改 DNS |
| 所有权 TXT | _railway-verify | 见上方完整值 | 已取得，Railway 尚未验证 |
| 其他额外验证记录 | 完全按 Railway 实际要求 | 当前未返回额外记录 | 无 |

## 阿里云根域名注意事项

修改前在阿里云导出完整记录并检查现有 @ A/AAAA/CNAME/ALIAS/MX/TXT/CAA。保留邮箱、SPF、DKIM、DMARC 和其他验证记录，不批量清空记录或更换 NS。

阿里云允许根域 @ 使用 CNAME，但与根域邮箱/验证记录共存可能有影响。需要同时保留这些记录时，ALIAS 可提供 CNAME 展平；当前阿里云说明该功能需要企业旗舰版或尊享版。因此不能把 ALIAS 当成免费默认选项，也不因本次部署自动购买升级。若账号已支持，可评估 @ ALIAS 指向实际 Railway 目标并核验平台接受情况。[阿里云添加解析记录](https://help.aliyun.com/zh/dns/pubz-add-parsing-record/)

不要仅因为阿里云允许保存 @ CNAME 与 MX/TXT，就认为没有影响。阿里云官方明确指出这种组合可能影响收信或 TXT 验证；ALIAS 与 A/AAAA/CNAME 也存在冲突。因此有现有记录时必须确认具体变更后再执行。[阿里云记录冲突规则](https://help.aliyun.com/zh/dns/pubz-dns-record-conflict-rules)

若当前账号不支持合适的根域方案，先保留 DNS 托管与现有记录。可供用户选择的临时方案是 `www.socool.xin` CNAME 到实际 Railway 目标，根域继续保持原状；需要根域 HTTPS 重定向时再确认具备证书能力的跳转服务。不能通过把临时解析到的 Railway IP 写死为 A 记录替代动态路由，也不能未经确认更换整域 nameserver。

## DNS 生效后验收

1. 使用 `Resolve-DnsName socool.xin` 与实际 TXT 名查询记录，比较 Railway domain status，不把 ALIAS 的 A 应答误认为没有展平。
2. 等待 Railway 归属验证和证书状态明确成功，浏览器无证书警告；不使用忽略证书错误参数。
3. 使用实际 GET 请求检查 `https://socool.xin/` 和 `http://socool.xin/` 的响应与跳转（例如 curl.exe -sS -D - -o NUL URL）。FastAPI 根路由未必支持 HEAD，不把 HEAD 405 当作站点故障；API 直接调用 HTTPS。
4. PUBLIC_BASE_URL 与 CORS 改成 `https://socool.xin`，重启并运行只读部署检查脚本。
5. 实测登录/退出、管理数据读取保存、鉴权 `/v1/models`、上游生成和结果 URL；云端重启后再验证持久化。

域名、HTTPS 证书、图片和视频均以实际验收结果记录，不以 DNS 刚保存或应用 /health 正常替代。
