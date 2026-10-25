# MHP Windows 未签名内测客户端

版本0.1.0，Windows 10/11 x64。连接用户指定的 https://118.178.92.58/。

## 实现和交付

使用Windows Forms + 微软WebView2，NSIS生成当前用户安装包。复用本机已有.NET编译器，未安装Rust、Visual Studio或其他大型编译环境。独立工程位于desktop/windows，不改变现有Web/API功能。

安装包：data/windows-client/release/MHP-Setup-0.1.0-x64.exe。
便携版：同目录MHP-0.1.0-x64-portable.zip，完整解压后运行MHP/MHP.exe。
同目录README.txt、SHA256SUMS和build-manifest.json记录说明、校验值和依赖来源。

依赖为.NET Framework 4.8和微软WebView2 Runtime。检测到缺少WebView2时，安装包会调用附带的微软官方小型引导程序，联网安装运行时；未包含完整离线运行时。.NET 4.8需由用户先准备。安装包未签名，不能承诺没有Windows发布者或SmartScreen提示，不自动绕过安全提示。

客户端加载服务器当前网页，账户、签到、额度和图片保留在服务器。本地WebView2资料位于当前用户LocalAppData/MHP/WebView2，独立于普通浏览器。持久Cookie按服务器有效期保留，会话Cookie在启动及正常关闭时清理。没有新建账户数据库或打包任何API Key、邮箱授权码、用户数据库和抠图模型。

正式编译禁用调试端口、不接受其他服务器地址或QA参数；限定顶层导航到指定MHP来源，不暴露主机对象或网页消息接口。仅允许该来源连续下载，每个成品仍需选择保存位置。客户端支持PNG、JPG、WEBP和ZIP，不执行下载文件；证书验证保持开启。工具栏提供首页、刷新和版本说明。单实例运行，更新前关闭客户端，首版采用手动覆盖安装。

卸载移除程序、当前用户快捷方式及卸载记录，保留WebView2资料和云端数据；公共电脑应先在网页中退出登录。安装目录默认LocalAppData/Programs/MHP Beta，无需给客户端用户提供Python、Docker、Rust或开发工具。

## 实际验证和边界

- 2026-10-18，HTTPS网页、/api/health、/api/auth/config实际读取通过，邮箱登录开启、短信关闭。原生WebView2使用独立空白资料打开云端，文档标题MHP，导航成功；未登录真实账户或调用云端生图。
- 原生WebView2中的23项网页回归通过，含本地排版、裁切、核对和恢复及PC/手机布局、中英文、明暗主题。使用隔离数据库，AI和邮件请求被拦截，不消耗真实用户额度。
- 原生下载回归实际写出合法PNG及含独立PNG的ZIP；连续下载、可执行文件下载阻止、站外顶层导航阻止、断网错误和恢复通过。用合成Cookie验证完整关闭重启后持久Cookie保留、会话Cookie删除。
- 使用仅限127.0.0.1的自签名TLS测试页，明确触发证书阻止事件；未向系统证书库导入任何证书，也未关闭验证。
- 实际静默安装到D:/MHP/data/windows-client/installed-test，核对全部文件、当前用户注册表卸载信息、桌面和开始菜单快捷方式；覆盖安装及卸载通过，测试记录和快捷方式随后清理。
- 微软运行时引导程序验证为Microsoft Corporation有效签名；主程序和MHP安装包为未签名。
- 仅在本机Windows设备测试，未在缺少WebView2/.NET的干净设备和其他Windows版本上实际安装。QA下载使用隔离路径自动保存，真实邮箱登录、Windows保存位置选择及取消保存、云端真实生成仍需用户内测。不能把本地模拟图像验收当作云端真实画质验收。
- 云端HTML引用index-CC7DwQ1l.js，本地前端已有其他更新。两端版本不同，客户端不会部署本地参数精简、模型或密钥配置。同步云端应用后客户端才会显示对应网页变化。

## 重新构建

先验证desktop/windows/build.py语法，再运行：

```powershell
.\.venv\Scripts\python.exe -B desktop/windows/build.py
```

构建依赖放在data/windows-client/tools，来源和固定SHA256见desktop/windows/dependencies.json。构建会先验证这些文件及微软引导程序Authenticode签名，再编译、检查运行时和生成安装包；不会自动下载新版本或上传文件。源码依赖.NET系统编译器，不依赖Visual Studio IDE。

QA使用同一源文件的QA条件编译，单独生成MHP-QA.exe，不包含在交付包中。调试端口9226及本机地址覆写只存在于QA版本；tests/windows_client_native.mjs记录原生行为检查，tests/material_ui.mjs可通过MHP_QA_DEBUG_URL连接QA WebView2。测试资料位于data/windows-client/qa-*，包含测试会话，不作为发布文件上传。

## 网站下载页（已发布）

2026-10-18 已发布 https://118.178.92.58/download.html ，安装包和便携版位于 /downloads/windows/，同目录提供 README.txt 和 SHA256SUMS。无需登录。首页原有“下载客户端”按钮已连接到下载页；旧版登录弹窗出现时另提供公开下载入口，离开首页进入工作台后隐藏该兼容入口。

仅更新7个公开静态文件及首页入口。保留云端原有JavaScript、API、数据库、模型、密钥和收款开关。前后端容器编号及启动时间核对一致，均未重启。已构建包含下载文件的新 mhp-web 镜像，后续重建容器仍可使用；主机 frontend/public 和 frontend/dist 同步保留公开文件。

5项发布脚本测试（含预检、损坏包拒绝、旧版本不一致拒绝、失败回滚和重复发布）通过；12项本地浏览器测试和13项公网测试通过。公网安装包和ZIP完整下载后的SHA256与原始内测包一致，断点请求返回206，HTTPS正常验证，PC/手机布局及匿名下载入口实际检查通过。未发送验证码或调用真实生图。

服务器备份：/opt/mhp/data/backups/download-site-o8xcsp1q。发布前镜像：sha256:dd4f1910a2fa8bfb402ebb0e97cf5bd93ef5aec02bc257ab7e148ca02b2b4886。发布后镜像：sha256:e8817d0ebb3b11c480853e5ff3b82386536d91bc8f56573d252181817656fba2。

重新准备网站包前，先AST验证 deploy/build_download_release.py 和 deploy/publish_downloads.py，再运行前者。它核验原始内测包SHA256后生成 frontend/public 下载文件及 data/cloud-upload/mhp-download-release.tar.gz。构建网页版前先执行此步骤，公开二进制不提交到源码库。上传仅限该专用包和校验文件，不能上传整个data目录、QA资料、tools或TLS测试私钥。

deploy/run_download_release.py 接受预期上传包SHA256，校验后安全解包，AST验证发布脚本并先运行 --check，再发布、校验和构建持久Web镜像。镜像构建上下文仅包含Web Dockerfile、Caddyfile和现有前端静态文件。脚本不重启容器、不修改后端；没有购买证书、新服务器或付费服务。

如需回滚，使用服务器发布工作目录内的 publish_downloads.py 加 --rollback 和上述备份路径恢复旧静态文件，并将上述发布前镜像重新标记为 mhp-web。此说明不自动执行回滚。公网测试记录位于 data/windows-client/website-live-qa/verification.json。
