# 提交给 API 服务商的问题说明（未发送）

MHP后端对`https://api.openai-next.com`的域名证书验证及IPv4 TLS1.3握手成功，但下列接口请求收到HTTP403：

- POST `/v1/messages`，模型`claude-sonnet-4-6`，使用Claude原生协议及`anthropic-version: 2023-06-01`。
- POST `/v1/images/edits`，模型`gpt-image-2`，multipart参考图输入，低质量、1张、1536×2048。
- GET `/v1/models`，Bearer鉴权，响应Server为Cloudflare，错误type指向Cloudflare Error1010。

GET诊断的Ray/请求标识：`a4fa83e3191695ab-AMS`。

请核实该域名是否为正确API入口，是否有可供后端程序使用的API访问策略/授权入口，及账号是否具有上述模型和接口权限。当前不是浏览器交互场景，后端不能完成浏览器挑战。

我们没有关闭TLS验证、没有伪装浏览器绕过规则、没有自动重试生成请求。请求资料是虚构商品与本地绘制测试图，不含真实商品资料。请一并核对失败请求是否扣费。

本说明不含API密钥、邮箱授权码、验证码、用户密码或账单信息。不要在公开工单附上完整密钥。
