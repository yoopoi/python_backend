
from .routers import auth, data_base, router, file_upload
import json
from threading import local
from fastapi import FastAPI, Request
# from storage import LocalStorage
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path
from typing import Union, Any
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, File, UploadFile
from utils.storage import Database
from utils import sql_util
import requests
import time
from requests_toolbelt import MultipartEncoder
import datetime
from requests.cookies import RequestsCookieJar
from typing import Any
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

#  , router, file_upload
origins = [
    "*"
]
config = sql_util.loadJosn("setting.json")
database = Database(config["dburl"])
data_base.checkDatabase()
adminTemplate = Jinja2Templates(directory=config["adminPath"])
app = FastAPI()
app.include_router(auth.router)
app.include_router(data_base.router)
app.include_router(router.router)
app.include_router(file_upload.router)
app.mount(
    f"/{config['uploadFilePath']}", StaticFiles(directory=f"{config['uploadFilePath']}/"), name="static")
app.mount(
    "/static", StaticFiles(directory=f"{config['adminPath']}/static"), name="static")
app.mount(
    "/assets", StaticFiles(directory=f"{config['adminPath']}/assets"), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许访问的源
    allow_credentials=True,  # 支持 cookie
    allow_methods=["*"],  # 允许使用的请求方法
    allow_headers=["*"]  # 允许携带的 Headers
)


class ApiRes(BaseModel):
    code: int = 0
    data: Any
    msg: str = ""


@app.get("/")
def home(request: Request):
    return adminTemplate.TemplateResponse(
        "index.html",
        {
            "request": request
        }
    )


@app.get("/serverConfig.json")
def serverConfig():
    with open(f"{config['adminPath']}/serverConfig.json", 'r') as f:
        data = json.loads(f.read())
    return data
