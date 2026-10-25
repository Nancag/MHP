# MHP 服务器 SSH 连接

2026-10-18 已配置并实际验证。服务器为用户的阿里云 ECS 118.178.92.58，账户root，SSH端口22。沿用服务器已有SSH服务，没有重启服务或调整安全组。

在本机正常 PowerShell 中执行：

```powershell
ssh mhp-ecs
```

本机配置文件为 `%USERPROFILE%\.ssh\config`，仅新增 Host mhp-ecs。专用身份为 `%USERPROFILE%\.ssh\id_ed25519_mhp_ecs`，公钥文件带 `.pub` 后缀。私钥只保留在本机，不在发布包中，也不上传服务器。不要向聊天或其他人发送私钥。

公钥由用户通过阿里云控制台终端登记到 /root/.ssh/authorized_keys，保留已有授权条目。控制台输出的ED25519主机指纹与网络探测一致：

```text
SHA256:o8XnFdBeGfsluS44vROq5M/0kd4+GjlgWBk2YOKsLMY
```

核对后保存到 `%USERPROFILE%\.ssh\known_hosts_mhp`。连接启用严格主机校验和专用身份，不跳过主机验证。实际执行只读 `id -un` 返回root，后续上传、发布及复查均通过此连接完成。没有配置SSH代理服务或修改系统全局SSH设置。

本机是未设口令的专用密钥，使用Windows用户目录权限保护；需要长期多人维护时可另行规划受限部署账户。当前配置只针对这台用户电脑，换电脑需要另行登记新公钥；无需复制私钥。

如阿里云实例重装导致主机指纹变化，先通过控制台重新核对，再更新专用known_hosts文件，不直接忽略警告。公网IP或SSH端口变更时，需要同步修改Host mhp-ecs配置。
