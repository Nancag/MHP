"""Per-user asset storage limits shared by uploads and browser collection."""
import os


DEFAULT_USER_STORAGE_BYTES = 1024 * 1024 * 1024
DEFAULT_USER_ASSET_COUNT = 2000


class StorageQuotaExceeded(ValueError):
    pass


def _positive_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def limits():
    return (
        _positive_env("MHP_USER_STORAGE_BYTES", DEFAULT_USER_STORAGE_BYTES),
        _positive_env("MHP_USER_ASSET_LIMIT", DEFAULT_USER_ASSET_COUNT),
    )


def _megabytes(value):
    return f"{value / (1024 * 1024):g} MB"


def enforce_asset_quota(connection, user_id, incoming_bytes):
    """Check committed and trashed rows while the caller holds a write lock."""
    if not user_id:
        raise StorageQuotaExceeded("素材必须属于已登录用户")
    if not isinstance(incoming_bytes, int) or incoming_bytes < 0:
        raise StorageQuotaExceeded("素材大小无效")
    byte_limit, asset_limit = limits()
    count, used = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM assets WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if count >= asset_limit:
        raise StorageQuotaExceeded(f"账户素材数量已达上限（{asset_limit} 张）")
    if used + incoming_bytes > byte_limit:
        raise StorageQuotaExceeded(
            f"账户素材存储空间不足（上限 {_megabytes(byte_limit)}）"
        )
