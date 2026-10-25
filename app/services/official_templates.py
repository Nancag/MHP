"""Versioned MHP workflow rules, separate from unverified product claims."""
import re
from copy import deepcopy

PET_ID = 'mhp-pet-heating-pad-ru-v1'
RULES = [
    '俄罗斯电商风格，与供应商素材采用不同风格和排版，整套视觉统一。',
    '主图突出醒目的俄语商品品名，少字；如已确认真实尺寸，在主图展示；尺寸仅在主图展示，详情页不展示尺寸。',
    '7/8/9张独立3:4图片，先主图，再真实细节、已核实卖点及使用场景；逐张生成，禁止拼图或九宫格。',
    '逐页安排：第1页品名主图，第2–4页分配已核实功能，第5–6页真实材质/控制器等细节，第7页居家宠物场景；如选8/9页，再补不同真实场景或有依据的卖点。资料不足时改为可见外观与适用场景，不补造功能。',
    '商品外形、颜色、结构和配件以原图与已确认事实为准，不添加随箱配件，不虚构内部结构或安全功能。',
    '所有功能参数须经卖家核实；外语文案附中文对照，逐页人工确认后才进入生图。',
]
CHECKLIST = [
    '商品是否确为宠物加热垫；颜色、材质及包装内配件是什么？',
    '尺寸是否为30×35 cm？只在核实后填写真实尺寸。',
    '是否八档调温？实际档位及温度范围是什么？',
    '是否支持4/8/12小时定时？',
    '防水、阻燃、耐磨耐咬、过热自动断电分别有何依据及使用限制？',
    '快速升温、均匀发热、亲肤舒适、节能省电是否有真实依据？',
]
BRIEF = '宠物加热垫，面向俄罗斯电商。' + '\n'.join(RULES)


def get_preset(preset_id):
    if preset_id is None:
        return None
    if preset_id != PET_ID:
        raise ValueError('未知官方策划模板')
    return deepcopy({'preset_id': PET_ID, 'name': 'MHP 官方 · 宠物加热垫（俄语）',
                     'language': 'ru', 'counts': [7, 8, 9], 'rules': RULES,
                     'checklist': CHECKLIST, 'wishes': BRIEF})


def check_selection(preset_id, count, language):
    preset = get_preset(preset_id)
    if preset and (count not in preset['counts'] or language != preset['language']):
        raise ValueError('宠物加热垫官方模板须选择7/8/9张，文案语言为俄语')
    return preset


def has_dimensions(text):
    # Concrete dimensions/units, not timing, temperature or generic feature numbers.
    return bool(re.search(r'\d+(?:[.,]\d+)?\s*(?:[×xхXХ*]\s*\d|(?:cm|mm|см|мм|inch|inches)\b)', text, re.I)
                or re.search(r'\d\s*(?:厘米|毫米|英寸)', text))


def check_pages(preset_id, pages):
    if not get_preset(preset_id):
        return
    for page in pages[1:]:
        if has_dimensions(' '.join(page)):
            raise ValueError('专用模板的尺寸只能放在主图，请移除详情页尺寸及尺寸标注要求')


def image_rules(preset_id, index):
    if not get_preset(preset_id):
        return ''
    return ('MHP pet heating pad template: redesign supplier styling and typography; cohesive premium Russian ecommerce design. '
            'Preserve the real heating pad, controller, cable and included accessories exactly as in the product material; '
            'never add accessories, unverified safety claims or invented internals. '
            + ('Only this main image may display seller-confirmed dimensions. Make the Russian product name large and prominent, with minimal copy. '
               if index == 0 else 'Do not display any dimensions, size labels, rulers or measurement arrows on this detail/scene image. '))
