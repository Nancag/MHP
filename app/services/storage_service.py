from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError


# 根据本文件位置找到 MHP 根目录，不依赖终端当前目录。从代码文件位置计算 MHP 目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]        
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

# 文件最大 10 MB，图片最多 2000 万像素.。限制单张文件为 10 MB
MAX_FILE_BYTES = 10 * 1024 * 1024         
MAX_IMAGE_PIXELS = 20_000_000

# 根据实际图片格式决定扩展名，不信任上传文件名。
ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
}


def save_product_image(image_bytes: bytes, folder_id: str | None = None) -> dict:
    """检查商品图片，保存原图，并返回素材信息。"""

    # 1. 检查文件是否为空或超过限制。
    if not image_bytes:
        raise ValueError("上传文件不能为空")

    if len(image_bytes) > MAX_FILE_BYTES:
        raise ValueError("图片不能超过 10 MB")

    # 2. 检查图片格式、尺寸及完整性。
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size

            if image_format not in ALLOWED_FORMATS:
                raise ValueError("只支持 JPG 和 PNG 图片")

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("图片不能超过 2000 万像素")

            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("暂不支持动画图片")

            image.verify()

        # 重新打开并解码，确认图片像素能够正常读取。
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()

    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("图片像素过大") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("文件不是有效图片，或图片已损坏") from exc

    # 3. 创建保存目录。
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 4. 生成唯一编号和文件名。
    asset_id = uuid4().hex
    extension = ALLOWED_FORMATS[image_format]
    filename = f"{asset_id}{extension}"
    if folder_id is not None:
        import re
        if not re.fullmatch(r'[0-9a-f]{32}', folder_id):
            raise ValueError('文件夹编号无效')
        directory = UPLOAD_DIR / 'references' / folder_id
        directory.mkdir(parents=True, exist_ok=True)
        filename = f'references/{folder_id}/{filename}'
    file_path = UPLOAD_DIR / filename

    # 5. 保存原始图片；如果文件已存在，则拒绝覆盖。
    with file_path.open("xb") as output:
        output.write(image_bytes)

    # 6. 返回素材信息，不向前端暴露本机绝对路径。
    return {
        "asset_id": asset_id,
        "filename": filename,
        "width": width,
        "height": height,
        "format": image_format,
        "size_bytes": len(image_bytes),
    }
