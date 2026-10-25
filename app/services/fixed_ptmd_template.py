"""Owner-approved deterministic PTMD image pairs.

An exact approved source file returns its approved finished poster.  This is a
fixed template, not an AI request: prompt, language, quality and scene settings
cannot change the output and no provider request or credit charge is made.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'app' / 'assets' / 'templates' / 'pet-heating-pad-fixed-ru-a.png'
TEMPLATE_ID = 'pet-heating-pad-fixed-ru-a-v1'
# The approved source is retained in two lossless/converted forms by the existing
# product library. Either exact file is the same owner-approved input image.
SOURCE_SHA256S = frozenset({
    '04945f2209abcaf84d0ceb765fc69869bc417d959be69cb2627d93231263467c',
    'c1321ea7656cf639910e648586042297833b1a4c6a347c8a4956b2756e3238af',
})


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def matches(path: Path) -> bool:
    """Only the exact owner-approved source bytes select this fixed output."""
    return path.is_file() and digest(path) in SOURCE_SHA256S


def publish(output: Path) -> dict:
    """Atomically copy the approved result without transforming its pixels."""
    if not RESULT.is_file():
        raise RuntimeError('固定 PTMD 成品模板文件缺失')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name('.' + output.stem + '.' + uuid4().hex + '.tmp')
    try:
        with RESULT.open('rb') as source, temporary.open('xb') as destination:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                destination.write(block)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    with Image.open(output) as image:
        image.verify()
    with Image.open(output) as image:
        width, height = image.size
    return {'filename': output.name, 'width': width, 'height': height,
            'size_bytes': output.stat().st_size, 'output_path': str(output)}
