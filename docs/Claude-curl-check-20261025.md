# Claude curl 最小连通性验收

用户明确授权1次真实调用后，使用Windows内置curl发送：

- 地址：`https://api.openai-next.com/v1/messages`
- 模型：`claude-sonnet-4-6`
- 用户输入：`Hello`
- 最大输出：32 Token
- 请求头：`x-api-key`、`anthropic-version: 2023-06-01`、JSON内容类型。
- 密钥仅由后端配置读入，再经标准输入传给curl，不出现在命令行、脚本、报告或临时密钥文件中。
- 本次明确使用IPv4，禁用代理，不跟随重定向，不自动重试，保持证书校验。

结果：HTTP200，返回模型`claude-sonnet-4-6`，停止原因`end_turn`，回复“Hey! How can I help you today?”。上游报告输入510 Token、输出13 Token，实际扣费须以渠道账单为准。

请求标识：`a4faaa998843c891-AMS`。原始脱敏结果：`data/acceptance/curl-claude-20261025/result.json`。

结论：本次密钥、Claude模型权限和原生接口可用。此前Python请求HTTP403/Cloudflare1010不能据此归因于密钥失效。由于curl与此前Python请求在请求头、TLS/HTTP实现等方面不同，这不是对所有变量均受控的对照实验，不能单凭本次成功认定某一特征是唯一原因。

尚未完成完整双语结构化文案、Word导出或GPT Image 2的真实模型验收。用户随后授权本地curl适配及离线测试，并选择curl默认双栈；本地实现已完成，81项离线回归测试通过。运行中的后端尚未重启加载本次改动，默认双栈的真实调用也尚未验证，不能把上述IPv4最小请求成功等同于MHP完整功能已恢复。详见 `MHP-curl-transport-20261025.md`。
