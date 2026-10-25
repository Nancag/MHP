"""Editable storyboard and exact local copy for independent ecommerce images."""
import json
from typing import Literal
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.services.poster_service import _font_coverage, _fit_text, font
from app.services import official_templates

ID = r'^[0-9a-f]{32}$'


class SetPage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_id: str = Field(pattern=ID)
    kind: Literal['main','feature','detail','scene'] = 'detail'
    title: str = Field(min_length=1,max_length=90)
    copy_lines: list[str] = Field(default_factory=list,max_length=4)
    direction: str = Field(default='',max_length=400)
    crop: list[float] | None = Field(default=None,min_length=4,max_length=4)
    source_is_scene: bool = False
    no_overlay: bool = False
    title_zh: str = Field(default='', max_length=150)
    copy_lines_zh: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode='before')
    @classmethod
    def ignore_retired_input(cls,value):
        # Old templates may contain this field; only original material is now used.
        if isinstance(value,dict):
            value=dict(value);value.pop('cutout_id',None)
        return value

    @field_validator('crop')
    @classmethod
    def check_crop(cls,value):
        import math
        if value is not None and (not all(math.isfinite(v) for v in value)
                or not 0 <= value[0] < value[2] <= 1 or not 0 <= value[1] < value[3] <= 1):
            raise ValueError('裁切区域需为0–1之间的左、上、右、下坐标')
        return value

    @field_validator('title')
    @classmethod
    def check_title(cls,value):
        if not value.strip():raise ValueError('标题不能为空')
        return value

    @field_validator('copy_lines')
    @classmethod
    def check_lines(cls,values):
        if any(not text.strip() or len(text)>80 for text in values):
            raise ValueError('每条文案需1至80字符')
        return values

    @field_validator('copy_lines_zh')
    @classmethod
    def check_translations(cls, values):
        if any(len(text) > 150 for text in values):
            raise ValueError('每条中文翻译最多150字符')
        return values


class ProductSetSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_name: str = Field(min_length=1,max_length=100)
    requirements: str = Field(default='',max_length=2000)
    reference_ids: list[str] = Field(default_factory=list,max_length=2)
    language: Literal['ru','en'] = 'ru'
    resolution: Literal['1200','2000'] = '2000'
    count: int = Field(default=8,ge=1,le=9,strict=True)
    pages: list[SetPage] = Field(min_length=1,max_length=9)
    engine: Literal['reference','local'] = 'reference'
    image_quality: Literal['low','medium','high'] | None = None
    palette: Literal['cool','warm','mono'] = 'cool'
    # Omitted on historical jobs = the original local typography pipeline.
    text_rendering: Literal['local','model'] | None = 'local'
    preset_id: str | None = Field(default=None, max_length=80)

    @field_validator('reference_ids')
    @classmethod
    def check_ids(cls,values):
        import re
        if len(set(values))!=len(values) or any(not re.fullmatch(ID,value) for value in values):
            raise ValueError('示例素材编号不正确或重复')
        return values

    @model_validator(mode='after')
    def check_count(self):
        if len(self.pages)!=self.count or self.pages[0].kind!='main':
            raise ValueError('页数须与生成张数一致，第一张须为主图')
        official_templates.check_selection(self.preset_id, self.count, self.language)
        if self.preset_id and any(p.kind == 'main' for p in self.pages[1:]):
            raise ValueError('专用模板仅第一张可为主图')
        official_templates.check_pages(self.preset_id, [
            [p.title, p.title_zh, p.direction, *p.copy_lines, *p.copy_lines_zh] for p in self.pages])
        return self


def output_size(spec):
    edge=int(spec.resolution)
    return edge*3//4,edge


def copy_layout(page,size):
    w,h=size
    blocks=[_fit_text(page.title,(w*.065,h*.055,w*.935,h*.265),w*.082,w*.045,True,3)]
    for i,text in enumerate(page.copy_lines):
        top=h*(.96-len(page.copy_lines)*.047+i*.047)
        blocks.append(_fit_text(text,(w*.07,top,w*.93,top+h*.045),w*.027,w*.019,max_lines=2))
    return blocks


def validate_copy(spec):
    coverage = _font_coverage('NotoSans-Regular.ttf') & _font_coverage('NotoSans-Bold.ttf')
    for page in spec.pages:
        model_text = spec.engine == 'reference' and spec.text_rendering == 'model'
        for text in (() if page.no_overlay or model_text else (page.title,*page.copy_lines)):
            if any(ord(char) not in coverage and char!='\n' for char in text):
                raise ValueError('成品文案暂支持俄文与英文，请将商品标题和卖点翻译后再生成')
        if not page.no_overlay and spec.language=='ru' and not any('А'<=c<='я' or c in 'Ёё' for c in page.title):
            raise ValueError('俄语套图每页都需要俄文标题')
        if spec.engine=='local':
            if not page.no_overlay:local_layout(page,(900,1200))
            if page.kind=='scene' and not page.source_is_scene:
                raise ValueError('本地场景页需要真实场景素材；请上传并勾选确认，或改为卖点页')
            if page.kind=='scene' and page.crop:
                raise ValueError('场景页需使用完整真实照片，请取消裁切')
            if page.kind=='detail' and page.asset_id==spec.pages[0].asset_id and page.crop is None:
                raise ValueError('本地细节页请选择真实特写素材或明确裁切区域；同一主图卖点请使用卖点页')
        else:
            if not page.no_overlay and not model_text:copy_layout(page,(900,1200))
    return spec


def build_instruction(spec,index):
    page=spec.pages[index]
    # Exact seller copy is rendered locally, so it need not be spelled by the image model.
    brief = {
        'main':'Full complete product, large premium hero composition. No cropped lid or base. Immediately recognizable category. Minimal visual clutter.',
        'detail':'A refined genuine detail photograph, emphasizing the relevant feature visible in image 1. Never invent cutaway internals or specifications.',
        'feature':'A refined product photograph illustrating the supplied selling point. Do not invent internal components or extra accessories.',
        'scene':'A realistic use environment with believable product scale, lighting and contact shadows. Props must not resemble included accessories.',
    }[page.kind]
    footer=round((.06+len(page.copy_lines)*.047)*100) if page.copy_lines else 3
    zones = ('Use the full image for the complete product on a pure white background. No added text, labels, decoration, pricing, badges or watermarks. '
             if page.no_overlay else f'Leave upper 27% pale and clean for a prominent locally typeset title, and lower {footer}% clean for exact seller copy. Place the photographic subject between these areas. ')
    model_text = spec.text_rendering == 'model' and not page.no_overlay
    if model_text:
        zones = ('Integrate the EXACT approved target-language lettering below into this ONE composition. '
                 'Create a prominent readable headline and clear short selling points with flexible editorial hierarchy. '
                 'Do not translate, paraphrase, add claims, add Chinese translations or invent extra text. '
                 'Preserve all characters, numbers and units. Exact text data: '
                 + json.dumps({'headline': page.title, 'selling_points': page.copy_lines}, ensure_ascii=False) + '. ')
    lettering = ('No unapproved lettering, logos or watermarks. ' if model_text
                 else 'No poster text, invented labels, logos or watermarks. ')
    composition = ('One finished poster only, never a sheet of multiple finished posters. Small genuine product detail insets may support this single design. '
                   if model_text else 'No collage, grid, multiple panels or contact sheet. ')
    return ('Create ONE independent portrait 3:4 premium ecommerce image. Image 1 is the ONLY authority for product structure, color and included accessories. '
            'Images 2-3, if present, are STYLE/LAYOUT references only; never copy their product, claims, logo or accessories. '
            'Preserve the exact product identity. No invented parts, accessories, labels or functional claims. '
            'Follow seller style requirements and example aesthetics; maintain a coherent visual identity across the set. '
            +official_templates.image_rules(spec.preset_id,index)+zones+lettering+'Preserve actual product markings. '+composition+brief+' '
            f'Product: {spec.product_name}. Page {index+1}/{spec.count}. Feature: {page.title}. '
            f'Page art direction: {page.direction}. Seller creative requirements: {spec.requirements}')


def render_copy(source_path,page,size,*,text_rendering='local'):
    """Preserve seller strings, case and numbers; fit without stretching the artwork."""
    with Image.open(source_path) as source:
        image=ImageOps.fit(source.convert('RGB'),size,method=Image.Resampling.LANCZOS).convert('RGBA')
    if page.no_overlay or text_rendering=='model':return image.convert('RGB')
    w,h=size
    # Narrow opaque copy zones hide accidental AI lettering in reserved areas.
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,w,h*.273),fill='#f6f9fd')
    if page.copy_lines:
        draw.rectangle((0,h*(.94-len(page.copy_lines)*.047),w,h),fill='#f6f9fd')
    draw.rounded_rectangle((w*.065,h*.033,w*.135,h*.039),radius=w*.003,fill='#2876a4')
    for block in copy_layout(page,size):
        for i,text in enumerate(block['lines']):
            draw.text((block['box'][0],block['box'][1]+i*block['line_height']),text,
                      font=font(block['size'],block['bold']),anchor='lt',fill='#102c46' if block['bold'] else '#36516a')
    return image.convert('RGB')


def local_layout(page,size):
    w,h=size
    blocks=[_fit_text(page.title,(w*.065,h*.055,w*.935,h*.265),w*.082,w*.045,True,3)]
    for index,text in enumerate(page.copy_lines):
        if page.kind=='feature':
            top=h*(.36+index*.135)
            blocks.append(_fit_text(text,(w*.075,top,w*.42,top+h*.115),w*.032,w*.020,max_lines=4))
        else:
            top=h*(.96-len(page.copy_lines)*.047+index*.047)
            blocks.append(_fit_text(text,(w*.07,top,w*.93,top+h*.045),w*.027,w*.019,max_lines=2))
    return blocks


def material_image(path,page):
    """Crop only the seller's explicit region. Keep product pixels and actual scene."""
    with Image.open(path) as source:
        image=ImageOps.exif_transpose(source).convert('RGBA')
    source_size=image.size
    if page.crop is not None:
        x0,y0,x1,y1=page.crop
        bounds=(round(x0*image.width),round(y0*image.height),round(x1*image.width),round(y1*image.height))
        if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:raise ValueError('裁切区域太小')
        image=image.crop(bounds)
    alpha=image.getchannel('A')
    bounds=alpha.getbbox()
    if bounds is None:raise ValueError('商品素材或裁切区域为空，请重新选择')
    transparent=alpha.getextrema()[0]<255
    if transparent:image=image.crop(bounds)
    return image,source_size,transparent


def render_material(path,page,size,*,palette='cool'):
    """Local layout only: no inference, no downloaded backgrounds, no new views."""
    from PIL import ImageFilter
    if page.no_overlay:
        original,_,_=material_image(path,page)
        image=Image.new('RGBA',size,'white')
        original.thumbnail((int(size[0]*.92),int(size[1]*.92)),Image.Resampling.LANCZOS)
        image.alpha_composite(original,((size[0]-original.width)//2,(size[1]-original.height)//2))
        return image.convert('RGB')
    colors={
        'cool':('#f6f9fd','#e6eef6','#102c46','#2876a4'),
        'warm':('#faf6f0','#eee2d2','#493629','#a36d3b'),
        'mono':('#f5f5f4','#e7e7e5','#202526','#565e60'),
    }
    bg,panel,ink,accent=colors[palette]
    image=Image.new('RGBA',size,bg)
    w,h=size
    draw=ImageDraw.Draw(image)
    draw.ellipse((w*.18,h*.24,w*1.2,h*1.05),fill=panel)
    draw.rounded_rectangle((w*.065,h*.033,w*.135,h*.039),radius=w*.003,fill=accent)
    if page.kind=='feature':
        box=(w*.47,h*.30,w*.94,h*.91)
    else:
        bottom=h*(.925-len(page.copy_lines)*.047)
        box=(w*.075,h*.29,w*.925,bottom)
    product,source_size,transparent=material_image(path,page)
    fitted=ImageOps.contain(product,(max(1,round(box[2]-box[0])),max(1,round(box[3]-box[1]))),method=Image.Resampling.LANCZOS)
    x=round((box[0]+box[2]-fitted.width)/2)
    y=round((box[1]+box[3]-fitted.height)/2)
    if transparent:
        shadow=Image.new('RGBA',size)
        bottom=y+fitted.height
        ImageDraw.Draw(shadow).ellipse((x+fitted.width*.08,bottom-h*.006,x+fitted.width*.92,bottom+h*.018),fill=(25,35,45,55))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(1,w*.012))))
    else:
        draw.rounded_rectangle((x-w*.012,y-h*.009,x+fitted.width+w*.012,y+fitted.height+h*.009),radius=w*.012,fill='white')
    image.alpha_composite(fitted,(x,y))
    draw=ImageDraw.Draw(image)
    for block in local_layout(page,size):
        for i,text in enumerate(block['lines']):
            draw.text((block['box'][0],block['box'][1]+i*block['line_height']),text,font=font(block['size'],block['bold']),anchor='lt',fill=ink)
    return image.convert('RGB'),{'source_size':source_size,'region_size':product.size,'placed_size':fitted.size}
