FIDELITY_INSTRUCTION = (
    "【商品保真要求】\n"
    "- 保持商品主体形状、颜色、Logo、品牌、标签、关键结构完全不变\n"
    "- 禁止添加不存在的配件\n"
    "- AI仅负责：背景、场景、灯光、环境、构图、视觉风格"
)

SCENE_MAP = {
    "outdoor": "户外",
    "kitchen": "厨房",
    "bedroom": "卧室",
    "livingroom": "客厅",
    "office": "办公室",
    "car": "汽车",
    "garage": "车库",
    "garden": "花园",
    "warehouse": "仓库",
    "commercial": "商业环境",
}

PLATFORM_MAP = {
    "ozon": "OZON",
    "wildberries": "Wildberries",
    "amazon": "Amazon",
}

LANG_MAP = {"zh": "中文", "en": "English", "ru": "Русский"}


def _build_system_prompt(params: dict, language: str = "zh") -> str:
    """构建系统提示词。"""

    lang_name = LANG_MAP.get(language, language or "中文")

    scene = params.get("scene", "")
    style = params.get("style", "")
    platform = params.get("platform", "")
    ratio = params.get("ratio", "")
    resolution = params.get("resolution", "")

    scene_name = SCENE_MAP.get(scene, scene) if scene else "未指定"
    platform_name = PLATFORM_MAP.get(platform, platform) if platform else "未指定"

    return (
        f"你是一个专业的电商产品摄影Prompt生成助手。根据以下信息生成一段详细的文生图Prompt。\n\n"
        f"场景：{scene_name}\n"
        f"风格：{style or '未指定'}\n"
        f"平台：{platform_name}\n"
        f"比例：{ratio or '未指定'}\n"
        f"分辨率：{resolution or '未指定'}\n"
        f"语言：{lang_name}\n\n"
        f"要求：\n"
        f"1. Prompt必须用{lang_name}编写\n"
        f"2. 描述商品在{scene_name}场景中的展示效果\n"
        f"3. 采用{style or '自然'}视觉风格\n"
        f"4. 适合{platform_name}平台展示（以实际平台规则为准）\n"
        f"5. 只描述背景、场景、灯光、环境、构图、视觉风格\n"
        f"6. 不描述对商品本身的修改（不改变形状/颜色/Logo/品牌/标签）\n"
        f"7. Prompt长度控制在100-200字\n"
        f"8. 直接输出Prompt内容，不要加引号或解释"
    )


def _build_user_prompt(product_info: dict, params: dict) -> str:
    """构建用户提示词。"""

    filename = product_info.get("filename", "")
    asset_id = product_info.get("asset_id", "")

    parts = []
    if filename:
        parts.append(f"商品文件名：{filename}")
    if asset_id:
        parts.append(f"商品编号：{asset_id}")

    scene = params.get("scene", "")
    style = params.get("style", "")
    platform = params.get("platform", "")

    if scene:
        parts.append(f"场景：{SCENE_MAP.get(scene, scene)}")
    if style:
        parts.append(f"风格：{style}")
    if platform:
        parts.append(f"平台：{PLATFORM_MAP.get(platform, platform)}")

    return "\n".join(parts) if parts else "请生成一个通用的电商产品展示Prompt"


def _fallback_prompt(product_info: dict, params: dict, language: str = 'zh') -> str:
    from app.services.parameters import normalize, label, canonical
    params = normalize(params)
    language = canonical('language', language)
    language = language if language in ('zh', 'en', 'ru') else 'en'
    scene = label('scene', params.get('scene', 'livingroom'), language)
    style = label('style', params.get('style', 'natural'), language)
    platform = label('platform', params.get('platform', 'amazon'), language)
    ratio, resolution = params.get('ratio', '1:1'), params.get('resolution', '2000')
    if language == 'zh':
        return f'空置的{scene}背景，{style}风格，柔和专业摄影光线，为商品预留中央前景，适合{platform}展示。比例{ratio}，最终长边{resolution}像素。不要绘制商品、文字或标志。'
    if language == 'ru':
        scenes = dict(zip(['livingroom','bedroom','kitchen','office','outdoor','car','warehouse','industrial'], ['гостиная','спальня','кухня','офис','улица','салон автомобиля','склад','промышленное помещение']))
        styles = dict(zip(['premium','minimalist','tech','business','natural','lifestyle'], ['премиальный','минимализм','технологичный','деловой','естественный','повседневный']))
        return f"Пустой фон: {scenes.get(params.get('scene'), 'гостиная')}. Стиль: {styles.get(params.get('style'), 'естественный')}. Мягкое освещение, свободный центр для товара. Платформа: {platform}. Соотношение {ratio}, длинная сторона {resolution} пикселей. Без товаров, текста и логотипов."
    return f'Empty {scene} background, {style} style, soft professional lighting, clear central foreground for a product overlay, suitable for {platform}. Aspect ratio {ratio}, final long edge {resolution} pixels. No products, text or logos.'


def generate_prompt(product_info: dict, params: dict, language: str = "zh", model: str = "local-template") -> str:
    """Build a local template. No text-model API is connected."""
    return _fallback_prompt(product_info, params, language)


def inject_fidelity_instruction(prompt: str) -> str:
    """在生图Prompt中注入商品保真指令。"""

    return f"{prompt}\n\n{FIDELITY_INSTRUCTION}"