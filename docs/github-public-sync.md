# GitHub 到公网 MHP 的自动发布

推送到 `main` 后，[deploy-public.yml](../.github/workflows/deploy-public.yml) 会通过固定 SSH 主机指纹连接生产服务器，并调用 `deploy/github_sync.sh`。脚本只更新 Git 跟踪的应用代码；它先要求已有 `.env` 和 `data/`，因此不会覆盖 API 密钥、账户、数据库、图片或生成历史。Docker 重建完成后必须通过本机健康检查。

首次启用时，在 GitHub 仓库的 `Settings → Environments → production` 中配置并保护以下机密：

- `MHP_DEPLOY_HOST`：公网 IP 或主机名。
- `MHP_DEPLOY_USER`：只具备 `/opt/mhp` 发布权限的非 root 用户。
- `MHP_DEPLOY_PATH`：`/opt/mhp`。
- `MHP_SSH_PRIVATE_KEY`：该发布用户的专用 Ed25519 私钥。
- `MHP_SSH_KNOWN_HOSTS`：从可信渠道取得的服务器 `known_hosts` 单行指纹。

服务器上需要先将现有 `/opt/mhp` 配置为 `https://github.com/Nancag/MHP.git` 远端，并确保发布用户能够执行受限的 Docker Compose 命令。首次接入前应在维护窗口运行一次 `deploy/github_sync.sh`，确认健康检查、登录、历史数据和图片均保留。
