"""Backend-only GPT Image 2 reference editing. One request, no redirects/retries."""
import base64
import io
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.request
from uuid import uuid4
from PIL import Image, ImageOps
from app.services.copywriter import NoRedirect
from app.services import curl_transport

MODEL='gpt-image-2'
ENDPOINT='https://api.openai-next.com/v1'
NOT_CONFIGURED='后端尚未配置 GPT Image 2，请完成配置后再生成'
MAX_IMAGE=20*1024*1024

def public_error(message):
    safe={NOT_CONFIGURED,'图像服务响应过大；请核对上游用量',
          '图像服务返回数量不符合请求，未自动重试',
          '渠道未返回内嵌图片，请先核实参考图接口兼容性；未下载未知网址',
          '生成图片超过大小上限','生成图片尺寸或帧数不受支持',
          '生成图片尺寸不符合1536×2048请求；请核对上游用量，未自动重试',
          '图像服务响应无效、连接失败或超时，上游可能已计费；未自动重试',
          '单张输入图超过20MB，请压缩后重试','输入图尺寸过大或为动态图','输入图转换后超过20MB，请压缩后重试'}
    if message in safe or re.fullmatch(r'图像服务返回 HTTP [1-5][0-9]{2}；请检查权限、模型和额度，未自动重试',message or ''):
        return message
    return '图片生成或保存失败，请确认上游状态后手动重试；未自动重复调用'

class ProviderError(Exception):
    pass

def settings():
    base=os.environ.get('MHP_IMAGE_BASE_URL',ENDPOINT).strip().rstrip('/')
    if base!=ENDPOINT:raise ProviderError('图像接口地址须为已授权的 https://api.openai-next.com/v1')
    return base,os.environ.get('MHP_IMAGE_API_KEY','').strip()

def available():
    try:return bool(settings()[1] and curl_transport.available())
    except ProviderError:return False

def _png(path):
    path=Path(path)
    if path.stat().st_size>MAX_IMAGE:raise ProviderError('单张输入图超过20MB，请压缩后重试')
    with Image.open(path) as source:
        if source.width*source.height>20_000_000 or getattr(source,'n_frames',1)!=1:
            raise ProviderError('输入图尺寸过大或为动态图')
        image=ImageOps.exif_transpose(source).convert('RGBA' if 'A' in source.getbands() else 'RGB')
        image.load()
    output=io.BytesIO();image.save(output,format='PNG');data=output.getvalue()
    if len(data)>MAX_IMAGE:raise ProviderError('输入图转换后超过20MB，请压缩后重试')
    return data

def edit_image(prompt,image_paths,size,quality):
    base,key=settings()
    if not key:raise ProviderError(NOT_CONFIGURED)
    if not 1<=len(image_paths)<=3:raise ProviderError('需要1张商品原图和最多2张参考图')
    if tuple(size)!=(1536,2048):raise ProviderError('当前仅支持1536×2048原生生成尺寸')
    if quality not in ('low','medium','high'):raise ProviderError('请选择图像质量')
    boundary='mhp-'+uuid4().hex
    parts=[]
    def field(name,value):
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    for name,value in {'model':MODEL,'prompt':prompt,'n':'1','size':'1536x2048',
                       'quality':quality,'output_format':'png'}.items():field(name,value)
    for index,path in enumerate(image_paths):
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="input-{index+1}.png"\r\nContent-Type: image/png\r\n\r\n').encode())
        parts.extend((_png(path),b'\r\n'))
    parts.append(f'--{boundary}--\r\n'.encode())
    req=urllib.request.Request(base+'/images/edits',data=b''.join(parts),
        headers={'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary,'Accept':'application/json'})
    opener=curl_transport.build_opener(limit=42*1024*1024)
    try:
        with opener.open(req,timeout=180) as response:raw=response.read(42*1024*1024+1)
        if len(raw)>42*1024*1024:raise ProviderError('图像服务响应过大；请核对上游用量')
        data=json.loads(raw)
        if len(data['data'])!=1:raise ProviderError('图像服务返回数量不符合请求，未自动重试')
        encoded=data['data'][0].get('b64_json')
        if not isinstance(encoded,str):raise ProviderError('渠道未返回内嵌图片，请先核实参考图接口兼容性；未下载未知网址')
        image_bytes=base64.b64decode(encoded,validate=True)
        if len(image_bytes)>30*1024*1024:raise ProviderError('生成图片超过大小上限')
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.width*image.height>20_000_000 or getattr(image,'n_frames',1)!=1:
                raise ProviderError('生成图片尺寸或帧数不受支持')
            if image.size!=tuple(size):
                raise ProviderError('生成图片尺寸不符合1536×2048请求；请核对上游用量，未自动重试')
            image.load()
        return {'image_bytes':image_bytes}
    except urllib.error.HTTPError as exc:
        raise ProviderError(f'图像服务返回 HTTP {exc.code}；请检查权限、模型和额度，未自动重试') from None
    except ProviderError:raise
    except Exception:
        raise ProviderError('图像服务响应无效、连接失败或超时，上游可能已计费；未自动重试') from None
