"""Deterministic editable Word export using standard OOXML, with no remote resources."""
import io
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def text(value):
    # Reject XML control characters and unpaired surrogates, preserving all languages.
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', str(value)))


def paragraph(value, style='Normal', language='zh-CN'):
    bidi = '<w:bidi/>' if language in ('ar', 'he', 'fa', 'ur') else ''
    runs = []
    for i, line in enumerate(str(value).splitlines() or ['']):
        if i:
            runs.append('<w:r><w:br/></w:r>')
        runs.append(f'<w:r><w:rPr><w:lang w:val="{text(language)}" w:eastAsia="zh-CN"/>'
                    + ('<w:rtl/>' if bidi else '') + '</w:rPr><w:t xml:space="preserve">'
                    + text(line)+'</w:t></w:r>')
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{bidi}</w:pPr>'+''.join(runs)+'</w:p>'


def build_docx(draft, product):
    content = draft['content']
    language = draft['language']
    parts = [paragraph('MHP 商品双语介绍', 'Title'),
             paragraph('本文提供商品介绍草稿、对应中文译文及宣传图创作提示词。发布前请核对商品事实、语言和当地平台要求。'),
             paragraph('商品名称 '+product.get('fields',{}).get('name',{}).get('value','未识别')),
             paragraph('商品来源 '+draft['source_url']),
             paragraph('目标语言 '+language+'    文本模型 '+draft['model']),
             paragraph('商品介绍','Heading1'),
             paragraph(content['title']['target'], 'Heading2',language),
             paragraph(content['title']['zh'], 'Translation')]
    for section in content['sections']:
        parts += [paragraph(section['heading']['target'],'Heading2',language),
                  paragraph(section['heading']['zh'],'Translation'),
                  paragraph(section['body']['target'],language=language),
                  paragraph('中文翻译 '+section['body']['zh'],'Translation')]
    if content.get('selling_points'):
        parts.append(paragraph('商品卖点','Heading1'))
        for i, point in enumerate(content['selling_points'],1):
            parts += [paragraph(str(i)+' '+point['target'],language=language),
                      paragraph('中文翻译 '+point['zh'],'Translation')]
    parts += [paragraph('宣传图创作提示词','Heading1'),
              paragraph(content['image_prompt_en'],language='en'),
              paragraph('中文翻译 '+content['image_prompt_zh'],'Translation'),
              paragraph('负面提示词','Heading2'),paragraph(content['negative_prompt_en'],language='en')]
    if content.get('notes_zh'):
        parts.append(paragraph('发布前核对事项','Heading1'))
        parts.extend(paragraph(note) for note in content['notes_zh'])
    fields = product.get('fields',{})
    if fields:
        parts.append(paragraph('网页识别依据','Heading1'))
        labels = {'name':'商品名称','description':'网页描述','price':'价格','currency':'币种','size':'商品尺寸',
                  'package_size':'包裹尺寸','material':'材质','width':'宽度','height':'高度','depth':'深度','weight':'重量','price_max':'最高价'}
        parts.extend(paragraph(labels.get(k,k)+' '+v['value']) for k,v in fields.items())
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+f'<w:document xmlns:w="{NS}"><w:body>'+''.join(parts)+'''
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'''
    styles = f'''<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{NS}">
    <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei" w:cs="Arial"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="300" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>
    <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
    <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/><w:color w:val="000000"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="000000"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="140" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/><w:color w:val="000000"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Translation"><w:name w:val="Translation"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="200"/></w:pPr></w:style></w:styles>'''
    buf = io.BytesIO()
    with ZipFile(buf,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>''')
        z.writestr('_rels/.rels','''<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''')
        z.writestr('word/_rels/document.xml.rels','''<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''')
        z.writestr('word/document.xml', document)
        z.writestr('word/styles.xml', styles)
    return buf.getvalue()
