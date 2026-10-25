import io
import urllib.request
from pathlib import Path
from uuid import uuid4

from app.config import DEFAULT_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATION_DIR = PROJECT_ROOT / "data" / "generations"

def _map_size(size: str) -> str:
    from app.services.parameters import dimensions
    _, native = dimensions({}, size)
    return f'{native[0]}*{native[1]}'


PROVIDER_REMOVED_MESSAGE = "AI 模型 API 已移除，请接入新的图像服务后再生成"


def available():
    return False


def submit_task(prompt: str, model: str = DEFAULT_MODEL, size: str = "1024*1024", n: int = 1) -> str:
    raise ValueError(PROVIDER_REMOVED_MESSAGE)


def poll_task(task_id: str) -> dict:
    raise ValueError(PROVIDER_REMOVED_MESSAGE)


def download_image(url: str, output_path: Path) -> dict:
    """Validate bounded input, convert to PNG, then publish atomically."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(30 * 1024 * 1024 + 1)
    if len(data) > 30 * 1024 * 1024:
        raise ValueError('生成图片文件过大')
    from PIL import Image
    with Image.open(io.BytesIO(data)) as img:
        if img.width * img.height > 20_000_000 or getattr(img, 'n_frames', 1) != 1:
            raise ValueError('生成图片尺寸或帧数不受支持')
        image = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')
        image.load()
    return save_png(image, output_path)


def save_png(image, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f'.{output_path.stem}.{uuid4().hex}.tmp')
    try:
        image.save(temporary, format='PNG')
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    width, height = image.size

    return {
        "filename": output_path.name,
        "width": width,
        "height": height,
        "size_bytes": output_path.stat().st_size,
        "output_path": str(output_path),
    }


def generate_product_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    size: str = "1024x1024",
    quality: str = "standard",
    generation_id: str = None,
) -> dict:
    """Compatibility entry point; the external provider has been removed."""
    raise ValueError(PROVIDER_REMOVED_MESSAGE)
