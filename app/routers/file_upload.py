from fastapi import Depends, FastAPI, HTTPException, APIRouter
from fastapi import APIRouter, Depends, File, UploadFile
from utils.storage import Database
import app.lib.apiRes as apiRes
import os
from tempfile import NamedTemporaryFile
from pathlib import Path
from utils import sql_util
import shutil
from pydantic import BaseModel
import hashlib
config = sql_util.loadJosn("setting.json")
router = APIRouter()


def file_hash(file: File, hash_method=hashlib.md5) -> str:
    h = hash_method()
    while b := file.read(8192):
        h.update(b)
    return h.hexdigest()


class UploadModel(BaseModel):
    tablename: str = ""
    file: UploadFile = File(...)


def getFileInDb(tablename, filePath):
    # data = Db.instance.getData(tablename, where=[("url", filePath, "=")])
    data = Database.instance().select(tablename).wheres(
        [("url", filePath, "=")]).exec()
    print(data)
    if data and data[0]:
        return data[0]["id"]


def storeFileInfo(tablename, filename, filePath):
    # res = Db.instance.addItem(tablename, data={
    #     "name": filename,
    #     "url": filePath
    # })
    res = Database.instance().insert(tablename).columnMap({
        "name": filename,
        "url": filePath
    }).exec()
    print(res)
    return res


@router.post("/image-upload")
async def upload_image(tablename="images", file: UploadFile = File(...)):
    md5 = file_hash(file.file)
    suffix = Path(file.filename).suffix
    save_dir = config["uploadFilePath"]
    filePath = os.path.join(save_dir, f"{md5}{suffix}")
    if os.path.exists(filePath):
        id = getFileInDb(tablename, filePath)
        if not id:
            id = storeFileInfo(tablename, md5, filePath)
        print(f"文件已存在:id:{id} 路径 {filePath}")
    else:
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        file.file.seek(0)
        with open(filePath, 'wb') as f:
            while b := file.file.read(8192):
                f.write(b)
        id = storeFileInfo(tablename, md5, filePath)
    print("上传完成")
    return apiRes.resp_200(data={
        "id": id,
        "fileName": md5,
        "filePath": filePath
    })

    # try:
    #     suffix = Path(file.filename).suffix

    #     with NamedTemporaryFile(delete=False, suffix=suffix, dir=save_dir) as tmp:
    #         shutil.copyfileobj(file.file, tmp)
    #         tmp.
    #         tmp_file_name = Path(tmp.name).name
    #         print(tmp_file_name)
    # finally:
    #     file.file.close()
    # Db.instance.
