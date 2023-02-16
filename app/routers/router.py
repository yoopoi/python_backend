from fastapi import Depends, FastAPI, HTTPException, APIRouter
# from utils.db import
from utils.storage import Database as Db
import app.lib.apiRes as apiRes
router = APIRouter()
tableList = []


def createRoute(path, name, icon="flUser", role=["admin"], children=None, showParent=False, component=False, showLink=True):
    res = {}
    meta = {}
    meta["icon"] = icon
    meta["title"] = name
    meta["roles"] = role
    res["path"] = path
    res["name"] = name

    if children:
        if showParent:
            meta["showParent"] = showParent
        res["children"] = children
    else:
        meta["showParent"] = True
    if component:
        res["component"] = f"/src/views{component}.vue"
    meta["showLink"] = showLink
    res["meta"] = meta
    return res


def createTableRouter():
    global tableList
    if not tableList:
        tableList = Db.instance().getTableList()
    res = []
    for item in tableList:
        name = "_".join(item.split("_")[1::])
        print(tableList)
        res.append(createRoute(path=f"/system/database/{name}",
                               name=f"{name}", component="/system/database/table"),)
        res.append(createRoute(path=f"/system/database/{name}/form",
                               component="/system/database/form", name=f"form-{name}", showLink=False))
    return res


def getRouter():
    return [createRoute(path="/system", icon="setting", name="system", children=[
        # createRoute(path="/system/terminal/index", name="terminal",),
        createRoute(path="/system/database", name="数据库",
                    children=createTableRouter())
    ])]


@router.get("/getAsyncRoutes")
def getAsyncRoutes():
    res = getRouter()
    return apiRes.resp_200(data=res)
    # tablenames = Db.instance().getTableList()
    # return apiRes.resp_200(data=tablenames)
