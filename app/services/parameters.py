"""Stable parameter values; translated labels are accepted for older clients/history."""
OPTIONS = {
    'language': [('zh', '中文', 'Chinese'), ('ru', '俄语', 'Russian'), ('en', '英语', 'English'), ('other', '其他', 'Other')],
    'platform': [('ozon', 'Ozon', 'Ozon'), ('wildberries', 'Wildberries', 'Wildberries'), ('amazon', 'Amazon', 'Amazon'), ('other', '其他', 'Other')],
    'scene': [('livingroom', '客厅', 'Living room'), ('bedroom', '卧室', 'Bedroom'), ('kitchen', '厨房', 'Kitchen'), ('office', '办公室', 'Office'), ('outdoor', '户外', 'Outdoor'), ('car', '车内', 'In-car'), ('warehouse', '仓库', 'Warehouse'), ('industrial', '工业场景', 'Industrial')],
    'style': [('premium', '高级', 'Premium'), ('minimalist', '极简', 'Minimalist'), ('tech', '科技', 'Tech'), ('business', '商业', 'Business'), ('natural', '自然', 'Natural'), ('lifestyle', '生活方式', 'Lifestyle')],
}


def canonical(field, value):
    for row in OPTIONS.get(field, []):
        if str(value).casefold() in [v.casefold() for v in row]:
            return row[0]
    return value


def aliases(field, value):
    key = canonical(field, value)
    return next((list(row) for row in OPTIONS.get(field, []) if row[0] == key), [value])


def label(field, value, language='en'):
    key = canonical(field, value)
    return next((row[1 if language == 'zh' else 2] for row in OPTIONS.get(field, []) if row[0] == key), value)


def normalize(params):
    return {key: canonical(key, value) for key, value in params.items()}


def dimensions(params, legacy_size='1024x1024'):
    if not params.get('ratio') and not params.get('resolution'):
        try:
            width, height = map(int, legacy_size.replace('*', 'x').split('x'))
        except (ValueError, AttributeError):
            raise ValueError('图片尺寸格式不正确')
        if not (512 <= width <= 2000 and 512 <= height <= 2000):
            raise ValueError('图片尺寸须为 512–2000 像素；4K/8K已停用')
    else:
        ratio = params.get('ratio', '1:1')
        resolution = str(params.get('resolution', '2000'))
        if ratio not in ('1:1', '4:3', '3:4', '16:9', '9:16') or resolution not in ('1200', '2000'):
            raise ValueError('仅支持1200/2000像素；4K/8K已停用')
        a, b = map(int, ratio.split(':'))
        edge = int(resolution)
        width, height = (edge, round(edge*b/a)) if a >= b else (round(edge*a/b), edge)
    scale = min(1, 1440 / max(width, height))
    native = (max(512, round(width*scale)), max(512, round(height*scale)))
    return (width, height), native
