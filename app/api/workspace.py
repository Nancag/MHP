"""User-owned templates, settings and source-backed market research."""
import csv
import io
import json
import os
import time
from contextlib import closing
from pathlib import Path
from statistics import mean, median
from typing import Annotated, Literal
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter, field_validator
from app.api.auth import CurrentUser
from app.models import db
from app.services import auth_service, reference_service
from app.services.generation_service import available as generation_available

router=APIRouter(prefix='/api/workspace',tags=['设置、模板与市场调研'])

class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid')
    theme: Literal['dark','light']='dark'
    locale: Literal['zh','en']='zh'
    resolution: Literal['1200','2000']='2000'

def admin(user):
    emails={v.strip().lower() for v in os.environ.get('MHP_ADMIN_EMAILS','').split(',') if v.strip()}
    return user.get('email','').lower() in emails

@router.get('/settings')
def settings(user:CurrentUser):
    with closing(db.get_connection()) as con:
        row=con.execute('SELECT value_json FROM preferences WHERE user_id=?',(user['user_id'],)).fetchone()
        password_configured=bool(con.execute('SELECT 1 FROM password_credentials WHERE user_id=?',(user['user_id'],)).fetchone())
    stored=json.loads(row[0]) if row else {}
    preferences=Preferences.model_validate({key:value for key,value in stored.items() if key in Preferences.model_fields}).model_dump()
    return {'preferences':preferences,
        'admin':admin(user),'version':'1.0.0','password_configured':password_configured,
        'services':{'email':auth_service.email_ready(),'image_generation':generation_available(),
            'reference_generation':reference_service.available(),'payment':False},
        'cutout_enabled':False}

@router.put('/settings')
def save_settings(user:CurrentUser,payload:Preferences):
    with closing(db.get_connection()) as con,con:
        con.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)',(user['user_id'],payload.model_dump_json()))
    return payload.model_dump()

class Template(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=80)
    description:str=Field(default='',max_length=300)
    payload:dict

    @field_validator('name')
    @classmethod
    def name_required(cls,v):
        if not v.strip():raise ValueError('模板名称不能为空')
        return v.strip()

    @field_validator('payload')
    @classmethod
    def safe_payload(cls,v):
        if len(json.dumps(v))>40000:raise ValueError('模板内容过大')
        # Persist creation parameters, never credentials, user IDs, or selected private assets.
        allowed={'prompt','params','design','spec','workflow'}
        if set(v)-allowed:raise ValueError('不支持的模板字段')
        result=json.loads(json.dumps(v))
        if not isinstance(result.get('prompt',''),str) or len(result.get('prompt',''))>8000:raise ValueError('模板提示词须为8000字以内的文本')
        schemas={'params':{'ratio','resolution','language','platform','scene','style'},
                 'design':{'kind','headline','subtitle','bullets'},
                 'spec':{'product_name','requirements','reference_ids','language','resolution','count','pages','engine','image_quality','palette','text_rendering'}}
        for key,keys in schemas.items():
            obj=result.get(key)
            if obj is not None and (not isinstance(obj,dict) or set(obj)-keys):raise ValueError('模板包含不支持的嵌套字段')
        params=result.get('params') or {}
        if not isinstance(params,dict) or not isinstance(result.get('prompt',''),str) or result.get('workflow','single') not in ('single','set'):raise ValueError('无效的模板参数')
        if str(params.get('resolution','2000')) not in ('1200','2000'):raise ValueError('仅支持1200/2000尺寸')
        if result.get('spec'):
            from app.services.product_set_service import ProductSetSpec, SetPage
            spec=result['spec']
            if not isinstance(spec,dict) or not isinstance(spec.get('pages',[]),list) or len(spec.get('pages',[]))>9:raise ValueError('无效的套图模板')
            if str(spec.get('resolution','2000')) not in ('1200','2000'):raise ValueError('仅支持1200/2000尺寸')
            spec['reference_ids']=[]
            # Validate new fields even in incomplete historical drafts, using the generation schema.
            if 'text_rendering' in spec:
                TypeAdapter(ProductSetSpec.model_fields['text_rendering'].annotation).validate_python(spec['text_rendering'],strict=True)
            for page in spec.get('pages',[]):
                if not isinstance(page,dict):raise ValueError('无效模板页面')
                if set(page)-{'asset_id','cutout_id','kind','title','copy_lines','direction','crop','source_is_scene','no_overlay','title_zh','copy_lines_zh'}:raise ValueError('模板页面包含不支持字段')
                for key in ('title_zh','copy_lines_zh'):
                    if key in page:
                        field=SetPage.model_fields[key]
                        TypeAdapter(Annotated[field.annotation,*field.metadata]).validate_python(page[key],strict=True)
                if 'copy_lines_zh' in page:SetPage.check_translations(page['copy_lines_zh'])
                page['asset_id']='';page.pop('cutout_id',None)
            if 'count' in spec and spec['count']!=len(spec.get('pages',[])):raise ValueError('模板页数不一致')
            # Validate full new specs with temporary IDs; incomplete legacy drafts remain editable.
            if spec.get('product_name') is not None and spec.get('pages') and all('title' in p for p in spec['pages']):
                checked=json.loads(json.dumps(spec));checked['product_name']=checked['product_name'] or '待填写'
                for page in checked['pages']:
                    page['asset_id']='0'*32
                    page['title']=page['title'] or '待填写'
                ProductSetSpec.model_validate(checked)
        if result.get('design'):
            from app.services.poster_service import PosterDesign
            PosterDesign.model_validate(result['design'])
        if any(not isinstance(value,str) or len(value)>100 for value in params.values()):raise ValueError('无效模板参数值')
        return result

@router.get('/template-catalog')
def template_catalog(user:CurrentUser):
    from app.services.template_catalog import catalog
    return catalog()

class TemplateFile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format:Literal['mhp-template']
    version:Literal[1]
    template:Template

@router.post('/templates/import',status_code=201)
def import_template(user:CurrentUser,payload:TemplateFile):
    return create_template(user,payload.template)

@router.get('/templates/{tid}/export')
def export_template(tid:str,user:CurrentUser):
    with closing(db.get_connection()) as con:
        row=con.execute('SELECT * FROM templates WHERE template_id=? AND user_id=?',(tid,user['user_id'])).fetchone()
    if not row:raise HTTPException(404,'模板不存在')
    clean=Template(name=row['name'],description=row['description'],payload=json.loads(row['payload_json']))
    data={'format':'mhp-template','version':1,'template':clean.model_dump()}
    return Response(json.dumps(data,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="MHP-template-{tid}.json"','Cache-Control':'no-store'})

@router.get('/templates')
def templates(user:CurrentUser,q:str=Query(default='',max_length=100)):
    with closing(db.get_connection()) as con:
        rows=con.execute('SELECT * FROM templates WHERE user_id=? ORDER BY updated_at DESC',(user['user_id'],)).fetchall()
    return {'items':[dict(template_id=r['template_id'],name=r['name'],description=r['description'],payload=json.loads(r['payload_json']),updated_at=r['updated_at'])
        for r in rows if q.casefold() in (r['name']+' '+r['description']).casefold()]}

@router.post('/templates',status_code=201)
def create_template(user:CurrentUser,payload:Template):
    tid=uuid4().hex
    with closing(db.get_connection()) as con,con:
        if con.execute('SELECT COUNT(*) FROM templates WHERE user_id=?',(user['user_id'],)).fetchone()[0]>=200:raise HTTPException(400,'最多保存200个模板')
        con.execute('INSERT INTO templates VALUES (?,?,?,?,?,?)',(tid,user['user_id'],payload.name,payload.description,json.dumps(payload.payload,ensure_ascii=False),int(time.time())))
    return {'template_id':tid}

@router.delete('/templates/{tid}')
def delete_template(tid:str,user:CurrentUser):
    with closing(db.get_connection()) as con,con:
        if not con.execute('DELETE FROM templates WHERE template_id=? AND user_id=?',(tid,user['user_id'])).rowcount:raise HTTPException(404,'模板不存在')
    return {'deleted':True}

class Competitor(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    name:str=Field(min_length=1,max_length=120)
    url:str=Field(min_length=8,max_length=1000)
    collected_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    price:float=Field(ge=0,le=1e9)
    rating:float|None=Field(default=None,ge=0,le=5)
    reviews:int|None=Field(default=None,ge=0,le=10**9)
    strengths:str=Field(default='',max_length=1000)
    weaknesses:str=Field(default='',max_length=1000)
    @field_validator('collected_on')
    @classmethod
    def date(cls,v):
        from datetime import date
        date.fromisoformat(v)
        return v
    @field_validator('url')
    @classmethod
    def url_valid(cls,v):
        p=urlsplit(v)
        if p.scheme not in ('http','https') or not p.hostname or p.username:raise ValueError('请输入有效的来源网址')
        return v

class Research(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=120)
    platform:str=Field(default='',max_length=100)
    market:str=Field(default='',max_length=100)
    currency:Literal['CNY','RUB','USD','EUR']='CNY'
    own_price:float|None=Field(default=None,ge=0,le=1e9,allow_inf_nan=False)
    competitors:list[Competitor]=Field(default_factory=list,max_length=50)
    conclusion:str=Field(default='',max_length=10000)

def research_public(row):
    v=json.loads(row['payload_json']);prices=[i['price'] for i in v['competitors']]
    stats={'samples':len(prices),'minimum':min(prices) if prices else None,'maximum':max(prices) if prices else None,
        'median':median(prices) if prices else None,'average':round(mean(prices),2) if prices else None}
    if prices and v.get('own_price') is not None and stats['median']:
        stats['own_vs_median_percent']=round((v['own_price']/stats['median']-1)*100,1)
    return {'project_id':row['project_id'],'updated_at':row['updated_at'],**v,'statistics':stats,
        'data_notice':'统计仅基于录入的同币种样本；评分、评价数不是销量，价格差不代表利润。'}

@router.get('/research')
def list_research(user:CurrentUser):
    with closing(db.get_connection()) as con:
        rows=con.execute('SELECT * FROM research WHERE user_id=? ORDER BY updated_at DESC',(user['user_id'],)).fetchall()
    return {'items':[research_public(r) for r in rows]}

@router.post('/research',status_code=201)
def add_research(user:CurrentUser,payload:Research):
    rid=uuid4().hex
    with closing(db.get_connection()) as con,con:
        if con.execute('SELECT COUNT(*) FROM research WHERE user_id=?',(user['user_id'],)).fetchone()[0]>=200:raise HTTPException(400,'最多200个调研项目')
        con.execute('INSERT INTO research VALUES (?,?,?,?,?)',(rid,user['user_id'],payload.title,payload.model_dump_json(),int(time.time())))
        row=con.execute('SELECT * FROM research WHERE project_id=?',(rid,)).fetchone()
    return research_public(row)

@router.put('/research/{rid}')
def update_research(rid:str,user:CurrentUser,payload:Research):
    with closing(db.get_connection()) as con,con:
        if not con.execute('UPDATE research SET title=?,payload_json=?,updated_at=? WHERE project_id=? AND user_id=?',
            (payload.title,payload.model_dump_json(),int(time.time()),rid,user['user_id'])).rowcount:raise HTTPException(404,'调研项目不存在')
        return research_public(con.execute('SELECT * FROM research WHERE project_id=?',(rid,)).fetchone())

@router.delete('/research/{rid}')
def delete_research(rid:str,user:CurrentUser):
    with closing(db.get_connection()) as con,con:
        if not con.execute('DELETE FROM research WHERE project_id=? AND user_id=?',(rid,user['user_id'])).rowcount:raise HTTPException(404,'调研项目不存在')
    return {'deleted':True}

@router.get('/research/{rid}/export')
def export_research(rid:str,user:CurrentUser):
    with closing(db.get_connection()) as con:
        row=con.execute('SELECT * FROM research WHERE project_id=? AND user_id=?',(rid,user['user_id'])).fetchone()
    if not row:raise HTTPException(404,'调研项目不存在')
    data=research_public(row);out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['名称','来源','采集日期','价格',data['currency'],'评分','评价数','优势','不足'])
    def cell(v):
        s='' if v is None else str(v)
        return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
    for item in data['competitors']:
        writer.writerow([cell(item[k]) for k in ('name','url','collected_on','price')]+[data['currency']]+[cell(item[k]) for k in ('rating','reviews','strengths','weaknesses')])
    writer.writerow([]);writer.writerow(['调研结论',cell(data['conclusion'])])
    return Response(('\ufeff'+out.getvalue()).encode(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="research-{rid}.csv"'})

def operations_root():return Path(os.environ.get('MHP_OPERATIONS_DIR',str(db.DB_PATH.parent/'operations')))

@router.get('/backups')
def backups(user:CurrentUser):
    if not admin(user):raise HTTPException(403,'仅管理员可以管理整站备份')
    root=operations_root();index=root/'index.json'
    return {'items':json.loads(index.read_text()) if index.exists() else [],
        'operations':[json.loads(p.read_text()) for p in sorted((root/'results').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:12]],
        'policy':'每日北京时间03:30自动备份，保留最近7份日常备份；含业务数据库、图片、应用与私密配置，模型可重新安装。恢复前会自动备份当前状态。',
        'worker_ready':(root/'heartbeat').exists() and time.time()-(root/'heartbeat').stat().st_mtime<180}

class BackupAction(BaseModel):
    action:Literal['backup','restore']
    backup_id:str=Field(default='',pattern=r'^[a-zA-Z0-9_-]*$',max_length=80)
    confirmation:str=''

@router.post('/backups',status_code=202)
def backup_action(user:CurrentUser,payload:BackupAction):
    if not admin(user):raise HTTPException(403,'仅管理员可以操作整站备份')
    root=operations_root()
    if not (root/'heartbeat').exists() or time.time()-(root/'heartbeat').stat().st_mtime>180:raise HTTPException(503,'备份服务尚未就绪')
    if payload.action=='restore':
        if payload.confirmation!='恢复整站':raise HTTPException(400,'请输入“恢复整站”确认；将回到备份时状态并退出所有登录')
        index=json.loads((root/'index.json').read_text()) if (root/'index.json').exists() else []
        if not any(i['backup_id']==payload.backup_id for i in index):raise HTTPException(404,'备份不存在')
    folder=root/'requests';folder.mkdir(parents=True,exist_ok=True)
    if any(folder.glob('*.json')):raise HTTPException(409,'已有备份操作等待处理')
    oid=uuid4().hex;value={'operation_id':oid,**payload.model_dump(),'requested_by':user['user_id'],'state':'queued','created_at':int(time.time())}
    tmp=folder/(oid+'.tmp');tmp.write_text(json.dumps(value),encoding='utf-8');tmp.replace(folder/(oid+'.json'))
    return value
