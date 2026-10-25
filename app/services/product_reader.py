"""Parse page evidence without executing scripts or inventing product facts."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from app.services.public_web import normalize_url


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.images, self.scripts, self.text = {}, [], [], []
        self.script = None
        self.skip = 0
        self.heading = None
        self.title_parts, self.h1_parts = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('title', 'h1'):
            self.heading = tag
        if tag == 'meta':
            self.meta.setdefault((a.get('property') or a.get('name') or '').lower(), a.get('content', ''))
        if tag == 'img':
            self.images.append(a.get('data-src') or a.get('src') or '')
        if tag == 'script':
            self.script = [] if a.get('type', '').lower().split(';')[0] == 'application/ld+json' else None
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        if tag in ('tr', 'p', 'li', 'div', 'dt', 'dd', 'h1', 'h2'):
            self.text.append('\n')
        if tag in ('td', 'th'):
            self.text.append(' | ')

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.heading = None
        if tag == 'script' and self.script is not None:
            self.scripts.append(''.join(self.script)); self.script = None
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        if tag in ('tr', 'p', 'li', 'div', 'dt', 'dd'):
            self.text.append('\n')

    def handle_data(self, data):
        if self.heading == 'title':
            self.title_parts.append(data)
        if self.heading == 'h1':
            self.h1_parts.append(data)
        if self.script is not None:
            self.script.append(data)
        if not self.skip:
            self.text.append(data)


def scalar(value):
    if isinstance(value, dict):
        return ' '.join(str(value.get(k, '')) for k in ('value', 'unitText', 'unitCode')).strip()[:1000]
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)[:1000]
    return ''


def products(value, depth=0):
    if depth > 20:
        return
    if isinstance(value, dict):
        kinds = value.get('@type', [])
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if isinstance(kinds, list) and any(str(k).rsplit('/', 1)[-1] == 'Product' for k in kinds):
            yield value
        for child in value.values():
            yield from products(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from products(child, depth + 1)


def parse_product(html, url):
    page = Page(); page.feed(html)
    found = []
    for script in page.scripts[:100]:
        try:
            found.extend(products(json.loads(script)))
        except (ValueError, RecursionError):
            continue
    product = found[0] if found else {}
    fields = {}

    def put(key, value, evidence):
        value = scalar(value)
        if value and key not in fields:
            fields[key] = {'value': value, 'evidence': evidence, 'source_url': url}

    put('name', product.get('name') or page.meta.get('og:title'), 'JSON-LD / og:title')
    put('name', ''.join(page.h1_parts) or ''.join(page.title_parts), '网页 h1 / title（需核对）')
    put('description', product.get('description') or page.meta.get('description'), 'JSON-LD / meta description')
    offer = product.get('offers') or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    if isinstance(offer, dict):
        put('price', offer.get('price') if offer.get('price') is not None else offer.get('lowPrice'), 'JSON-LD offers (第一个报价或最低价)')
        put('currency', offer.get('priceCurrency'), 'JSON-LD offers')
        put('price_max', offer.get('highPrice'), 'JSON-LD offers.highPrice')
    put('price', page.meta.get('product:price:amount') or page.meta.get('og:price:amount'), 'meta price')
    put('currency', page.meta.get('product:price:currency') or page.meta.get('og:price:currency'), 'meta currency')
    for key in ('material', 'size', 'width', 'height', 'depth', 'weight'):
        put(key, product.get(key), 'JSON-LD Product.' + key)
    aliases = {'material': ('材质', '材料', 'material', 'материал'),
               'size': ('商品尺寸', '产品尺寸', 'product dimensions', 'item dimensions', 'размер товара'),
               'package_size': ('包装尺寸', '包裹尺寸', 'package dimensions', 'packaging dimensions', 'размер упаковки')}
    props = product.get('additionalProperty', [])
    if isinstance(props, dict):
        props = [props]
    if isinstance(props, list):
        for prop in props:
            if not isinstance(prop, dict):
                continue
            name = str(prop.get('name', '')).lower()
            for key, words in aliases.items():
                if any(word == name.strip() for word in words):
                    put(key, prop.get('value'), 'JSON-LD additionalProperty: ' + name)
    lines = [' '.join(x.split()).strip(' |') for x in ''.join(page.text).splitlines()]
    for line in lines:
        if len(line) > 500:
            continue
        for key, words in aliases.items():
            for word in words:
                m = re.match(r'^' + re.escape(word) + r'\s*[:：|]\s*(.{1,250})$', line, re.I)
                if m:
                    put(key, m[1], line)
    raw_images = product.get('image', [])
    if not isinstance(raw_images, list):
        raw_images = [raw_images]
    raw_images += [page.meta.get('og:image', '')]
    fallback = not any(raw_images)
    if fallback:
        raw_images = page.images
    images = []
    for item in raw_images:
        if isinstance(item, dict):
            item = item.get('contentUrl') or item.get('url')
        if not isinstance(item, str) or not item.strip():
            continue
        try:
            link = normalize_url(urljoin(url, item))
        except ValueError:
            continue
        if link not in images:
            images.append(link)
        if len(images) >= 200:
            break
    warnings = ['仅解析静态网页；价格可能随规格、地区和时间变化。未识别字段不代表商品没有该属性。']
    if len(found) > 1:
        warnings.append('网页含多个 Product，当前采用第一个，请核对是否为目标商品。')
    if fallback:
        warnings.append('未找到结构化商品图，图片为页面候选，可能包含标识或无关素材，请人工核对。')
    if len(images) > 20:
        warnings.append('首次下载前20张候选图；其余可点击继续归档，失败图片也可单独确认后重试。')
    required = ('name', 'price', 'size', 'package_size', 'material')
    return {'fields': fields, 'missing_fields': [k for k in required if k not in fields],
            'image_urls': images, 'warnings': warnings}
