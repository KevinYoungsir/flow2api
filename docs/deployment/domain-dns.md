# socool.xin 域名与 DNS

当前未关联 Railway 服务，未取得真实 Railway CNAME/ALIAS 目标或验证 TXT；本次没有修改 DNS，也未确认 Railway 证书。任何公网现有响应都不能作为本次部署成功的证据。

## 获取真实记录

先完成 Railway 服务部署并确认账号、服务、环境和端口。已实际检查本机 `railway domain --help`，支持创建、list、status 和证书命令。获得用户对域名绑定/DNS 的授权后：

```powershell
railway domain socool.xin --service <确认后的服务> --environment <确认后的环境> --json
railway domain status socool.xin --service <确认后的服务> --environment <确认后的环境> --json
```

端口应与当前服务的 PORT 一致；只有实际知道端口后才填写 `--port`。输出中的目标域名、所有权验证记录名和值必须逐字采用，不猜测。也可在 Railway Settings → Networking 中查看。按当前官方说明，通常同时需要路由记录和验证 TXT。[Railway 域名说明](https://docs.railway.com/networking/domains/working-with-domains)

| 类型 | 阿里云主机记录 | 值 | 当前状态 |
| --- | --- | --- | --- |
| 根域路由 ALIAS/CNAME（需先确认方案） | @ | 仅填 Railway 实际返回目标 | 未取得 |
| 所有权 TXT | 将 Railway 提供的完整记录名换成 socool.xin 相对主机名 | Railway 实际返回值 | 未取得 |
| 其他额外验证记录 | 完全按 Railway 实际要求 | 实际返回值 | 未取得 |

## 阿里云根域名注意事项

修改前在阿里云导出完整记录并检查现有 @ A/AAAA/CNAME/ALIAS/MX/TXT/CAA。保留邮箱、SPF、DKIM、DMARC 和其他验证记录，不批量清空记录或更换 NS。

Railway 根域名要求 CNAME 展平或动态 ALIAS。阿里云现有 ALIAS 可用于这种场景，但账号套餐、解析线路及 Railway 验证兼容性需要在实际控制台确认；若可用，优先评估 @ ALIAS 指向 Railway 给出的目标，并保留 MX/TXT。[阿里云添加解析记录](https://help.aliyun.com/zh/dns/pubz-add-parsing-record/)

不要仅因为阿里云允许保存 @ CNAME 与 MX/TXT，就认为没有影响。阿里云官方明确指出这种组合可能影响收信或 TXT 验证；ALIAS 与 A/AAAA/CNAME 也存在冲突。因此有现有记录时必须确认具体变更后再执行。[阿里云记录冲突规则](https://help.aliyun.com/zh/dns/pubz-dns-record-conflict-rules)

若当前账号不支持合适的根域方案，先保留 DNS 托管与现有记录。可供用户选择的临时方案是 `www.socool.xin` CNAME 到实际 Railway 目标，根域继续保持原状；需要根域 HTTPS 重定向时再确认具备证书能力的跳转服务。不能通过把临时解析到的 Railway IP 写死为 A 记录替代动态路由，也不能未经确认更换整域 nameserver。

## DNS 生效后验收

1. 使用 `Resolve-DnsName socool.xin` 与实际 TXT 名查询记录，比较 Railway domain status，不把 ALIAS 的 A 应答误认为没有展平。
2. 等待 Railway 归属验证和证书状态明确成功，浏览器无证书警告；不使用忽略证书错误参数。
3. `curl.exe -I https://socool.xin/` 和 `curl.exe -I http://socool.xin/` 检查跳转；API 直接调用 HTTPS，避免 HTTP POST 重定向改变语义。
4. PUBLIC_BASE_URL 与 CORS 改成 `https://socool.xin`，重启并运行只读部署检查脚本。
5. 实测登录/退出、管理数据读取保存、鉴权 `/v1/models`、上游生成和结果 URL；云端重启后再验证持久化。

域名、HTTPS 证书、图片和视频均以实际验收结果记录，不以 DNS 刚保存或应用 /health 正常替代。
