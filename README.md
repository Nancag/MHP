# MHP

MHP 程序源码，包括 Python 后端、Vue 前端、Windows 客户端、Edge 商品采集插件和 Docker 部署脚本。

当前功能与版本说明见 [README-当前版本.md](README-当前版本.md)。本仓库用于保存和构建程序；后端运行需要 Python 服务和持久化存储。

## 目录

| 目录 | 内容 |
| --- | --- |
| `app/` | API、业务逻辑、数据模型及排版字体 |
| `frontend/` | Vue 3 / Vite 前端源码、静态资源及依赖锁文件 |
| `desktop/windows/` | Windows 客户端及采集插件安装辅助工具源码 |
| `extensions/mhp-collector/` | Edge 采集插件和安装辅助工具 |
| `launcher/` | 本地启动器源码 |
| `deploy/` | Docker、发布、备份及部署检查脚本 |
| `docs/` | 功能、版本和运维文档 |

## 构建前端

安装 Node.js 后，在仓库根目录执行：

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
```

构建结果位于 `frontend/dist/`，由本机生成，不提交到 Git。

## 本地运行

使用 Python 3.12 创建虚拟环境，并安装已锁定的后端依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cloud.lock
```

根据 `.env.auth.example`、`.env.text.example` 等示例在本机配置 `.env`。真实密钥仅保存在后端环境中。后端调用外部服务需要系统可用的 `curl`。

在两个终端中分别启动后端与前端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm --prefix frontend run dev
```

## 云端部署

先构建前端，再运行只读检查和打包：

```powershell
python -B deploy/preflight.py
python -B deploy/build_bundle.py
```

按 [云端部署说明](deploy/README.zh-CN.md) 在 Linux x86_64 服务器上部署 Docker 服务。GitHub 仓库保存代码；上传到仓库本身不会自动更新正在运行的服务器。

Windows 客户端构建流程及所需工具见 `desktop/windows/build.py`、`desktop/windows/dependencies.json` 和 [客户端说明](docs/windows-client.md)。

## 本地文件

真实 `.env`、私钥、`data/` 业务数据、虚拟环境、`node_modules/`、前端构建结果、临时工作目录及无关第三方安装器均由 `.gitignore` 排除。运行所需配置请根据示例单独填写，业务数据库和用户图片应单独备份。
