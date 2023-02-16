from fastapi import Depends, FastAPI, HTTPException, APIRouter, Body
from utils import sql_util
from utils.storage import Database
import app.lib.apiRes as apiRes
import json
import os
from app.routers.auth import get_password_hash
router = APIRouter()
config = sql_util.loadJosn("setting.json")
tableData = {}

actionMap = {
    "hashable": get_password_hash
}


def checkDatabase():
    global tableData
    print("[*]开始检测数据库")
    json_list = os.listdir(config["jsonTablePath"])
    tableList = Database.instance().getTableList()
    for item in json_list:
        tableName = item.split(".")[0]
        data = sql_util.loadJosn(os.path.join(config["jsonTablePath"], item))
        tableData[tableName] = data
        if Database.instance().isExistTable(tableName):
            print(f"[{tableName}]已存在")
        else:
            print(f"[{tableName}]未存在")
            # Db.instance._createTable(tableName, data["base"])
            Database.instance().create(tableName).columns(data["base"]).exec()
            items = data["defaultInsert"]
            for item in items:
                # Db.instance.addItem(tablename=tableName, data=item)
                Database.instance().insert(tableName).columnMap(item).exec()
        # print(data)
    # if Db.instance.


@router.post("/tablenames")
def tableNames():
    tablenames = Database.instance().getTableList()
    return apiRes.resp_200(data=tablenames)


@router.get("/getTableStructure")
def getTableStructure(name: str):
    global tableData
    return apiRes.resp_200(data=tableData[name]["show"])


def formatColumnsFromCache(tableName, cacheData):
    columns = cacheData["show"]["column"]
    columnList = []
    for item in columns:
        if item.get("fromKey"):
            if item.get("formatKey"):
                columnList.append(
                    f"{item['fromKey']}[{item['formatKey']}]")
            else:
                columnList.append(
                    f"{item['fromKey']}")
        else:
            if item.get("formatKey"):
                columnName = f"{tableName}.{item['key']}[{item['formatKey']}]"
            else:
                columnName = f"{tableName}.{item['key']}"
            columnList.append(columnName)
    return columnList


def formatLeftJoinFromCache(tablename, cacheData):
    columns = cacheData["show"]["column"]
    leftJoin = {}
    for item in columns:
        if item.get("leftJoin"):
            print(item['leftJoin'])
            for joinTable in item['leftJoin']:
                # print(joinTable, item['leftJoin'])
                leftJoin[joinTable] = item['leftJoin'][joinTable]
    return leftJoin


def formatForm(tableName, form):
    global tableData
    columns = tableData[tableName]["show"]["column"]
    cacheFormatData = {}
    newForm = {}
    for column in columns:
        for key in actionMap:
            if column.get("actions") and column["actions"].get(key):
                name = column.get("formatKey", column["key"])
                if form.get(name):
                    form[name] = actionMap[key](form[name])
        if column.get("key"):
            cacheFormatData[column.get(
                "formatKey", column["key"])] = column["key"]
    for key in form:
        if cacheFormatData.get(key):
            newForm[cacheFormatData[key]] = form[key]
    return newForm


def processActions(tableName, form):
    global tableData
    columns = tableData[tableName]["show"]["column"]
    for column in columns:
        for key in actionMap:
            if column.get(key):
                actionMap[key](form[key])


@router.post("/getTableData")
def getTableData(body=Body(...)):
    global tableData
    tableName = body["tableName"]
    cacheData = tableData[tableName]
    columnList = body.get(
        "columns", formatColumnsFromCache(tableName, cacheData))
    leftJoin = body.get(
        "leftJoin", formatLeftJoinFromCache(tableName, cacheData))
    form = body.get("form", {})
    print("leftJoin", leftJoin, "columnList", columnList)
    data = Database.instance().select(tableName).wheres(
        form.get("where", {})).leftJoinFromMap(leftJoin).columnsList(columnList).exec()
    # data = Db.instance.getData(
    #     column=columnList, tablename=tableName, left_join=leftJoin, where=form['where'], offset=form.get("offset", 0), limit=form.get("limit", 10))
    count = Database.instance().select(tableName).wheres(form.get("where", {})).offset(
        form.get("offset", 0)).limit(form.get("limit", 10)).counts()
    print(data, count)
    return apiRes.response(data=data, total=count)


@router.post("/addTableData")
def addData(body=Body(...)):
    tableName = body["tableName"]
    form = formatForm(tableName, body["form"])
    # res = Db.instance.addItem(tablename=tableName, data=form)
    res = Database.instance().insert(tableName).columnMap(form).exec()
    return apiRes.resp_200(data=res)


@router.post("/deleteData")
def addData(body=Body(...)):
    tableName = body["tableName"]
    form = body["form"]
    # res = Db.instance.deleteItem(tablename=tableName, where=form)
    res = Database.instance().delete(tableName).wheres(form).exec()
    return apiRes.resp_200(data=res)


@router.post("/editData")
def addData(body=Body(...)):
    tableName = body["tableName"]
    form = formatForm(tableName, body["form"])
    # res = Db.instance.updateItem(
    #     tablename=tableName, data=form, where=body["where"])
    res = Database.instance().update(tableName).setDict(
        form).wheres(body["where"]).exec()
    return apiRes.resp_200(data=res)
