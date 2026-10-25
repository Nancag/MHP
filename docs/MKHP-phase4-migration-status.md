# MHP 业务数据库迁移结果

执行日期：2026-10-24（Asia/Shanghai）。用户已授权独立备份和业务数据库迁移，未授权启动服务、保存密钥或真实网络调用。

- 数据库：`D:\MHP\data\mhp.db`
- 迁移前独立SQLite备份：`D:\MHP\data\backups\mkhp-phase4-migration-20261024-220419\mhp-before-migration.db`
- 详细验收记录：同目录 `migration-report.json`（只含数量、哈希及结构检查结果，不含业务记录明文）。
- SQLite完整性检查：`ok`。
- 原有全部表的记录：逐表比较原列数据的数量与SHA-256，全部保持一致。
- 新增表：`reference_folders`、`product_imports`、`product_drafts`、`password_credentials`、`password_attempts`、`preferences`、`templates`、`research`。
- `assets` 新增字段：`deleted_at`、`folder_id`、`source_url`。
- 历史抠图记录表未删除；没有恢复抠图代码或功能。

执行时只调用数据库初始化模块，未导入应用入口，因此没有启动业务服务、执行启动恢复任务或发起网络请求。未修改 `.env`。

用户选择了项目 `.env` 作为密钥存储方式；本次只确认该方案，实际写入密钥和真实模型验收仍需分别授权。
