# GitHub 到公网 MHP 的自动发布

推送到 `main` 后，[deploy-public.yml](../.github/workflows/deploy-public.yml) 会在 GitHub Runner 上构建 Vue 前端并生成 SHA-256 校验发布包，再通过固定 SSH 主机指纹上传到生产服务器。它不要求服务器安装 Node、npm 或将 `/opt/mhp` 变为 Git 仓库。服务器脚本保留 `.env`、`data/`、现有 `compose.json` 及其 `/operations` 挂载；仅替换应用源码、插件、部署文件、前端产物与运行依赖。Docker 重建完成后必须通过本机健康检查，否则自动恢复旧源码、旧 Compose 和旧镜像标签。

首次启用时，在 GitHub 仓库的 `Settings → Environments → production` 中配置并保护以下机密：

- `MHP_DEPLOY_HOST`：公网 IP 或主机名。
- `MHP_DEPLOY_USER`：当前服务器源码为 root 所有且 Docker 命令由 root 管理，首次接入可填 `root`；后续如创建受限发布用户，再切换为该用户。
- `MHP_DEPLOY_PATH`：`/opt/mhp`。当前服务器目录由 root 管理时，此值对应的 SSH 用户必须具备读取 `.env`、写入源码目录和 Docker Compose 权限。
- `MHP_SSH_PRIVATE_KEY`：该发布用户的专用 Ed25519 私钥。
- `MHP_SSH_KNOWN_HOSTS`：从可信渠道取得的服务器 `known_hosts` 单行指纹。

服务器不需要 Git 工作目录。首次接入前应在维护窗口手动上传一次构建包并运行 `deploy/apply_github_release.sh`，确认健康检查、登录、历史数据、图片及 `/operations` 挂载均保留。
