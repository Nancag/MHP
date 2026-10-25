from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.generations import router as generations_router
from app.api.account import router as account_router
from app.api.product_sets import router as product_sets_router
from app.api.workspace import router as workspace_router
from app.api.library import router as library_router
from app.api.mkhp import router as mkhp_router
from app.api.product_drafts import router as drafts_router
from app.api.product_plans import router as plans_router, recover_plans
from contextlib import asynccontextmanager
import threading
from app.models.db import init_db


# 启动时确保数据库表已创建（幂等，保留已有数据）。
init_db()
from app.api.mkhp import recover_imports
recover_imports()
from app.api.product_drafts import recover_drafts
recover_drafts()
recover_plans()
from app.repositories.recovery import interrupted_on_startup
interrupted_on_startup()


@asynccontextmanager
async def lifespan(app):
    from app.services.reminder_service import run
    stop=threading.Event()
    worker=threading.Thread(target=run,args=(stop,),daemon=True)
    worker.start()
    yield
    stop.set()


app = FastAPI(title="MHP",lifespan=lifespan)

# 允许前端本地开发服务器跨域访问（仅限本机开发环境）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册商品图片的上传和预览接口。
app.include_router(assets_router)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(product_sets_router)
app.include_router(workspace_router)
app.include_router(library_router)
app.include_router(mkhp_router)
app.include_router(drafts_router)
app.include_router(plans_router)


# 注册 AI 生图任务接口。
app.include_router(generations_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "MHP", "version":"1.0.0","build":"2026.10.25-redesign.4"}


from fastapi import Request
from fastapi.responses import JSONResponse
import logging

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.getLogger(__name__).error('请求处理失败', exc_info=exc)
    return JSONResponse(status_code=503, content={'detail': '服务暂不可用，请稍后重试'})
