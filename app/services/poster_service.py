"""Deterministic Russian main-image typography; no network or model calls."""
import io
import re
import struct
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator

FONT_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'


class PosterDesign(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['russian_main'] = 'russian_main'
    headline: str = Field(min_length=1, max_length=90)
    subtitle: str = Field(default='', max_length=100)
    bullets: list[str] = Field(default_factory=list, max_length=2)

    @field_validator('headline', 'subtitle')
    @classmethod
    def clean_text(cls, value):
        return ' '.join(unicodedata.normalize('NFC', value).split())

    @field_validator('headline')
    @classmethod
    def russian_title(cls, value):
        if not re.search('[А-Яа-яЁё]', value):
            raise ValueError('请填写俄文商品标题')
        return value

    @field_validator('bullets')
    @classmethod
    def clean_bullets(cls, values):
        result = [' '.join(unicodedata.normalize('NFC', v).split()) for v in values]
        if any(not v or len(v) > 32 for v in result):
            raise ValueError('每条卖点需为1至32个字符')
        return result


@lru_cache(maxsize=2)
def _font_coverage(filename):
    """Read the bundled TrueType cmap, so unsupported glyphs fail before charging."""
    data = (FONT_DIR / filename).read_bytes()
    tables = struct.unpack_from('>H', data, 4)[0]
    for index in range(tables):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + index * 16)
        if tag == b'cmap':
            break
    else:
        raise ValueError('字体缺少字符映射')
    count = struct.unpack_from('>H', data, offset + 2)[0]
    covered = set()
    for index in range(count):
        platform, encoding, relative = struct.unpack_from('>HHI', data, offset + 4 + index * 8)
        start = offset + relative
        if platform not in (0, 3) or struct.unpack_from('>H', data, start)[0] != 4:
            continue
        segments = struct.unpack_from('>H', data, start + 6)[0] // 2
        end_at = start + 14
        begin_at = end_at + segments * 2 + 2
        delta_at = begin_at + segments * 2
        range_at = delta_at + segments * 2
        for seg in range(segments):
            end = struct.unpack_from('>H', data, end_at + seg * 2)[0]
            begin = struct.unpack_from('>H', data, begin_at + seg * 2)[0]
            delta = struct.unpack_from('>h', data, delta_at + seg * 2)[0]
            shift = struct.unpack_from('>H', data, range_at + seg * 2)[0]
            for cp in range(begin, min(end + 1, 65535)):
                glyph = struct.unpack_from('>H', data, range_at + seg * 2 + shift + (cp - begin) * 2)[0] if shift else cp
                if glyph and (glyph + delta) % 65536:
                    covered.add(cp)
    return frozenset(covered)


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ('NotoSans-Bold.ttf' if bold else 'NotoSans-Regular.ttf')), max(1, round(size)))


def validate_design(design):
    design = PosterDesign.model_validate(design)
    try:
        for bold, texts in ((True, [design.headline.upper()]), (False, [design.subtitle, *design.bullets])):
            coverage = _font_coverage('NotoSans-Bold.ttf' if bold else 'NotoSans-Regular.ttf')
            if any(ord(c) not in coverage for text in texts for c in text):
                raise ValueError('文案含不支持的字符，请使用俄文、英文、数字及常用标点')
            font(24, bold)
        # Validate actual line fitting at the smallest export size before any upstream call.
        poster_layout(design, (720, 960))
    except (OSError, struct.error) as exc:
        raise ValueError('海报字体不可用，请联系管理员') from exc
    return design


def _fit_text(text, box, maximum, minimum, bold=False, max_lines=1):
    for size in range(round(maximum), round(minimum) - 1, -1):
        face = font(size, bold)
        lines = []
        line = ''
        # Break at spaces or an existing hyphen, never arbitrarily split a Russian word.
        tokens = re.findall(r'[^\s-]+-?|\s+', text)
        for token in tokens:
            candidate = line + token
            if face.getlength(candidate.rstrip()) <= box[2] - box[0]:
                line = candidate
            else:
                if line.strip():
                    lines.append(line.strip())
                line = token.lstrip()
        if line.strip():
            lines.append(line.strip())
        line_height = round(size * 1.38)
        if (len(lines) <= max_lines and len(lines) * line_height <= box[3] - box[1]
                and all(face.getlength(part) <= box[2] - box[0] for part in lines)):
            return dict(lines=lines, size=size, box=box, line_height=line_height, bold=bold)
    raise ValueError('文案过长，无法清晰排版，请缩短标题或卖点')


