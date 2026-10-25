# MHP 云端首次内测部署

目标：Linux x86_64、Docker/Compose 已安装。Python 3.12 位于容器内，不升级系统 Python；单实例、单个后端工作进程。默认 Compose 仅监听服务器本机回环地址，不开启收款。本指南描述当前本地代码的部署方式，不代表线上服务器已经同步。

## 上传前

本地上传目录为 `D:\MHP\data\cloud-upload`。

- `mhp-cloud-code.tar.gz`：后端、前端正式构建、插件和部署文件；不含真实 .env、数据库、用户图片、会话或支付密钥。
- `SHA256SUMS`：代码压缩包的校验值。

使用 `python -B deploy/build_bundle.py` 生成当前代码包后再上传代码包和 SHA256SUMS。抠图功能和本地抠图模型已移除，无需上传模型包。云端构建、存储和模型调用可能产生费用，实际以服务商账单为准。

## 1. 解包和检查

上传代码包和 SHA256SUMS 后，先在 `/root` 执行 `sha256sum --ignore-missing -c SHA256SUMS`，确认 `mhp-cloud-code.tar.gz: OK`，再执行：

```bash
mkdir -p /opt/mhp
tar -xzf /root/mhp-cloud-code.tar.gz -C /opt/mhp
cd /opt/mhp
cp deploy/cloud.env.example .env
chmod 600 .env
python3 deploy/preflight.py --server
docker compose -f compose.json config --quiet
```

仅首次创建空目录时执行此处的 `cp`。以后更新保留自己的 .env，不覆盖它。主机预检查使用标准库，不启动业务程序，也不发送邮件或调用 AI。

`SHA256SUMS` 上传后可先在 `/root` 执行 `sha256sum --ignore-missing -c SHA256SUMS`；上传了哪个压缩包，就应显示对应的 OK。必须先确认要解包的压缩包已显示 OK。

## 2. 构建镜像

```bash
cd /opt/mhp
docker compose -f compose.json build
```

构建会下载 Python/Caddy 基础镜像、curl、证书及 Python 依赖，不调用 AI 或邮件服务。后端镜像构建检查依赖和Python语法。按用户要求测试源码已归档并从工作目录删除，镜像不再依赖 tests 目录或运行单元测试。前端使用本地已构建的 dist，不在云端安装 Node.js。真实 .env 不进入镜像。

当前电脑没有 Docker 引擎，尚未在本地完成 Linux 镜像构建。最终以此步骤在目标服务器的构建和测试结果为准。若出现镜像下载超时，保留原始错误；不要随意运行陌生镜像站或一键安装脚本。

## 3. 准备持久化目录

首次部署时为容器用户准备数据目录；更新时保留已有数据库、图片和密钥：

```bash
cd /opt/mhp
python3 deploy/preflight.py --server
install -d -o 10001 -g 10001 -m 750 data/uploads data/generations data/mhp-recovery
chown 10001:10001 data
```

数据库、图片、认证密钥等业务数据持久保存在主机 `/opt/mhp/data`。模型请求由后端curl发出：Claude原生接口生成双语文案，GPT Image 2处理商品参考图；密钥只配置在后端。镜像已声明curl依赖，默认双栈，不自动重试。

## 4. 在服务器内部启动

```bash
cd /opt/mhp
docker compose -f compose.json up -d
docker compose -f compose.json ps
curl --fail http://127.0.0.1:8080/api/health
```

应返回 `{"status":"ok","app":"MHP"}`。后端容器 8000 不映射到公网；网页仅绑定服务器 127.0.0.1:8080。暂时不用开放 8000、5173、8080 公网端口。Caddy 保留 /api 路径转发，其他请求提供前端页面。

## 5. 查看网页与配置登录

有可用 SSH 登录凭据后，可以从自己的 Windows 终端建立转发：

```powershell
ssh -N -L 8080:127.0.0.1:8080 你的服务器登录用户@服务器公网IP
```

随后在自己电脑打开 `http://127.0.0.1:8080`。Workbench 免密登录不等同于本机 SSH 已配置好；如没有本机 SSH 凭据，先完成连接配置，再使用此命令。登录密码和私钥不要发到聊天。

首次云端内测使用空数据库，不自动迁移本地用户、额度和图片。在 `/opt/mhp/.env` 中安全填写已有网易 SMTP 账号及授权码后，运行 `docker compose -f compose.json up -d --force-recreate api` 使配置生效；只 `restart` 不会重新载入 Compose env_file。不要把包含授权码的配置截图发送到聊天。

AI Key 默认留空，需确认预算后配置，可参考项目 `.env.text.example` 中的变量名称；站内赠送次数不代表供应商免费额度。健康检查和本地模板操作不调用收费模型。Compose 强制保持 ALIPAY_ENABLED=0，会员邮件提醒关闭。

## 6. 后续验收与正式访问

先验证登录、找回密码、素材上传、MKHP采集与双语文案、PTMD生成、模板、成本计算、历史及下载。真实模型与邮件测试另行授权。Linux镜像、浏览器插件及客户端升级仍需在目标环境实际验收，不能用本地语法检查代替。

`docker compose -f compose.json stop` 可停止业务容器，但不会停止 ECS 计费。试用不足时先备份 data/.env，再按云控制台规则处理资源。`docker compose down` 不会删除主机 data；不要使用删除主机 data 的命令。查看配置时使用 `config --quiet`，不要把展开了密钥的完整配置或环境变量发到聊天。
