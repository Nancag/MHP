"""MHP presets and attributed platform guidance, never platform certification."""
from copy import deepcopy
from app.services.official_templates import PET_ID, get_preset

DATE='2026-10-24'
OZON='https://seller-edu.ozon.ru/rabota-s-tovarami/trebovaniya-k-kartochkam-tovarov/media/foto-i-video-tovara'
WB='https://seller.wildberries.ru/instructions/ru/tj/material/item-photo-rules-recommendations-and-common-mistakes'
YANDEX='https://yandex.ru/support2/global-marketplace/ru/assortment/create/main-fields/images'


def preset(key,name,kinds,*,plain=False,requirements='',palette='cool',source='',rules=None,status='verified'):
    titles={'main':'Товар','feature':'Особенности','detail':'Детали','scene':'Применение'}
    return {'template_id':key,'name':name,'description':'请替换商品名称和已核实文案，选择原图并检查每页；不包含素材或虚构商品参数。',
            'source_url':source,'checked_on':DATE,'verification':status,'rules':rules or [],
            'payload':{'workflow':'set','prompt':'','params':{'resolution':'2000','language':'ru','ratio':'3:4'},'design':None,
                       'spec':{'engine':'local','palette':palette,'product_name':'','requirements':requirements,'reference_ids':[],
                               'language':'ru','resolution':'2000','count':len(kinds),'image_quality':None,
                               'pages':[{'asset_id':'','kind':kind,'title':titles[kind],'copy_lines':[],
                                         'direction':'完整真实商品，干净背景；不得编造配件或商品属性。','no_overlay':plain}
                                        for kind in kinds]}}}


def catalog():
    common='平台规则按通用品类整理；类目例外须在卖家后台复核。不保证通过审核，不代表平台认证。'
    pet = get_preset(PET_ID)
    items=[preset('mhp-main','MHP · 纯商品主图',['main'],plain=True),
           preset('mhp-feature','MHP · 主图＋卖点',['main','feature']),
           preset('mhp-detail','MHP · 主图＋细节',['main','detail']),
           preset('mhp-scene','MHP · 主图＋使用场景',['main','scene'],palette='warm'),
           preset('wb-ru','Wildberries 俄罗斯 · 商品图规范预设',['main'],plain=True,source=WB,
                  requirements='保持完整商品、清晰真实，避免营销文字；核实类目规则。',
                  rules=['可读取的官方俄文跨境卖家区域说明：至少700×900像素，JPG/PNG/WEBP，单张不超过10MB；部分官方服务使用700×933，本预设1500×2000同时超过两者。俄罗斯卖家后台及类目规则仍需复核。',common]),
           preset('yandex-ru','Yandex Market 俄罗斯 · 主图规范预设',['main'],plain=True,source=YANDEX,
                  requirements='完整商品，纯白背景，无额外文字、价格、水印、店铺标志或联系方式。',
                  rules=['俄文跨境卖家规范：至少300×300像素，单张不超过10MB；展示适配3:4。','主图应清晰、完整，商品占画面至少三分之二；不要附加价格、广告、水印或配送信息。',common]),
           preset('ozon-ru','Ozon 俄罗斯 · 待核实规范',['main'],plain=True,source=OZON,status='pending',
                  rules=['官方说明页本次无法读取，尺寸、文件大小和类目例外尚未核实；暂不作为已核实平台模板启用。',common])]
    items.insert(0, {'template_id': PET_ID, 'name': pet['name'],
                    'description': '专用官方流程：核实商品 → 选择7/8/9张 → 大白话生成俄语＋中文方案 → 逐页确认 → 逐张生图。套用不调用API。',
                    'source_url': '', 'checked_on': '2026-10-25', 'verification': 'mhp-official',
                    'rules': pet['rules'], 'payload': {'workflow': 'set', 'prompt': '',
                    'params': {'language': 'ru', 'ratio': '3:4', 'resolution': '2000'},
                    'design': None, 'spec': None, 'planner': {'preset_id': PET_ID}}})
    return {'items':deepcopy(items),'notice':'MHP官方模板与按平台规范整理的预设；均非平台认证或平台提供的设计文件。官方模板中的商品功能仍须逐项核实。Amazon按用户选择暂缓。原图背景和文字在本地模式仍会保留，不含抠图。'}
