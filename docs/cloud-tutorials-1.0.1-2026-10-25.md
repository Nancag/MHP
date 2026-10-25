# MHP 教程与 1.0.1 公告发布记录

日期：2026-10-25（北京时间）。网站：https://118.178.92.58/

网页发布标识：`2026.10.25-tutorials-1.0.1`。

## 发布内容

- PTMD 五页新手教程：上一步、下一步、完成；首次进入自动展示，中途退出记忆进度，完成后可从顶部入口重新查看。支持手机、中英文与深浅色主题。
- MKHP 现有插件安装与详细教程入口保留，已确认发布后的网页仍可打开。
- 首页公告新增 `v1.0.1 · 2026-10-25`，内容为「新增MKHP 插件教程」「新增PTMD新手教程」，提供对应英文文案，保留原公告。

## 发布范围与验证

本次仅更新前端源码、静态资源与 web 镜像。发布包冻结为 79 个文件；切换前核对 77 个原版本文件，新镜像与公网 HTTPS 的 8 个静态文件 SHA256 全部一致。

本地前端构建通过。PTMD 教程此前的 23 项隔离交互检查通过。本次新增 6 项发布后浏览器检查通过：真实首页公告展示、公告历史保留、已发布前端的五页教程完成、永久入口重看、MKHP 插件教程可打开、无 JavaScript 异常。

登录后页面使用隔离的合成账号数据验证，所有业务 API 均由浏览器拦截模拟；没有创建真实用户、写入业务记录、调用真实模型或发送邮件。

API 容器未重启，原 `.env`、compose 配置和业务数据保留。健康接口正常，API 版本仍为 `1.0.0`，build 仍为 `2026.10.25-redesign.3`；本次 `1.0.1` 为网页公告版本，没有发布 Windows 安装包。

## 备份和证据

- 云端备份：`/opt/mhp-backups/before-2026.10.25-tutorials-1.0.1`，包含原前端源码、归档及原 web 镜像标识。部署脚本带失败回滚。
- 发布包 SHA256：`c8baa33984ae51da4dde0b803f4b64fe0669c8381851cbaac9afcc0a2bc98e0f`。
- 前端备份 SHA256：`cbd98d3fe9506dda50e9c4d5120fc1d5a03be6a71ede8e1a0ea3a191767be582`。
- 固定清单与构建元数据：`work/tutorial-release-1.0.1/package-report.json`。
- 云端报告：`work/tutorial-release-1.0.1/cloud-release-report.json`。
- 浏览器报告与截图：`work/tutorial-release-1.0.1/public-browser-report.json`、`live-home-announcement.png`、`published-tutorial-synthetic-step5.png`。

发布内容以固定清单为准；发布后的本地编辑不会自动同步。网页保留旧缓存时可用 Ctrl+F5 刷新。
