import pymysql
import time
import datetime
import sqlite3
from enum import Enum
from dbutils.pooled_db import PooledDB, SharedDBConnection
import threading

from utils import sql_util


class DbException(Exception):
    pass


class SqCommend(Enum):
    insert = "INSERT"
    update = "UPDATE"
    delete = "DELETE"
    select = "SELET"
    create = "CREATE"


class Db:
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        config = sql_util.loadJosn("setting.json")
        self.config = config
        self.host = config['dbHost']
        self.port = config['dbPort']
        self.user = config['dbUsername']
        self.passwd = config['dbPassword']
        self.db = config['dbName']
        self.prefix = config['dbPrefix']
        self._tableStructures = {}
        self._tableList = []
        self.conn = ""
        self._connect()

    @classmethod
    @property
    def instance(cls, *args, **kwargs):
        if not hasattr(Db, "_instance"):
            with Db._instance_lock:   # 为了保证线程安全在内部加锁
                if not hasattr(Db, "_instance"):
                    Db._instance = Db(*args, **kwargs)
        return Db._instance

    def _connect(self):
        if self.config["dbType"] == "sqlite":
            if self.conn:
                return self.conn
            self.conn = sqlite3.connect(
                self.db+".db", check_same_thread=False, timeout=10)
            return self.conn
            # self.conn = sqlite3.connect(host=self.host,port=self.port,user=self.user,passwd=self.passwd,db=self.db,charset="utf8")
        else:
            if not self.conn:
                self.POOL = PooledDB(
                    creator=pymysql,
                    maxconnections=10,
                    maxcached=10,
                    maxshared=10,
                    blocking=True,
                    setsession=[],
                    host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db, charset="utf8"
                )
            conn = self.POOL.connection()
            return conn

    def isSqlite(self):
        return self.config["dbType"] == "sqlite"

    def exec(self, sql, commit=True, raise_exc=False, add=False):
        try:
            conn = self._connect()
            print(f"[*]执行语句:{sql}")
            cur = conn.cursor()
            cur.execute(sql)
            data = cur.fetchall()
            if commit:
                conn.commit()
            cur.close()
            if add:
                return cur.lastrowid
            return data
        except Exception as e:
            print(e)
            if cur:
                cur.close()
            if raise_exc:
                raise DbException(e)

    def _getRealColumnName(self, item):
        if item.find(".") != -1:
            [name, col] = item.split(".")
            return col
        else:
            return item

    def listToKV(self, data, structList):
        print("data", data, "structList", structList)
        res = []
        for item in data:
            i = 0
            tmp = {}
            for struct in structList:
                real_struct = ""
                if "[" in struct:
                    real_struct = struct.split("[")[1][0:-1]
                else:
                    real_struct = self._getRealColumnName(struct)
                tmp[real_struct] = item[i]
                i += 1
            print(tmp)
            res.append(tmp)
        return res

    def isExistTable(self, tablename):
        if len(self._tableList) == 0:
            self.getTableList()
        tablename = self._setPrefix(tablename)
        if tablename in self._tableList:
            return True
        else:
            return False

    def getTableList(self):
        sql = ""
        if self.isSqlite():
            sql = "select name from sqlite_master where type='table' order by name"
        else:
            sql = "SHOW TABLES;"
        data = self.exec(sql)
        res = []
        for item in data:
            res.append(item[0])
        self._tableList = res
        return res

    def _getTableStructure(self, tablename):
        res = self._tableStructures.get(tablename)
        if res:
            return res
        else:
            sql = ""
            if self.isSqlite():
                sql = f"PRAGMA table_info({tablename})"
                data = self.exec(sql)
                res = []
                for item in data:
                    res.append(item[1])
                self._tableStructures[tablename] = res
            else:
                sql = f"SHOW FULL COLUMNS FROM {tablename}"
                data = self.exec(sql)
                res = []
                for item in data:
                    res.append(item[0])
                self._tableStructures[tablename] = res
        return res

    def _formatColumn(self, item: str):
        if type(item) == str and item.find(".") != -1:
            if item.find(" ") != -1:
                item_arr = item.split(" ")
                [name, col] = item_arr[-1].split(".")
                name = self._setPrefix(name)
                prefix = ''
                if col.find("[") != -1:
                    col = col.split("[")[0]
                for i in range(len(item_arr)-1):
                    prefix += item_arr[i]+" "
                return f"{prefix} {name}.{col}"
            else:
                [name, col] = item.split(".")
                name = self._setPrefix(name)
                return f"{name}.{col}"
        else:
            return item

    def _processLeftJoin(self, data):
        res = ""
        for key in data:
            tmp_str = sql_util.listToStr(
                [data[key][0], data[key][1]], suffix=f" {data[key][2]} ", end=False, formatFunc=self._formatColumn)
            res += f" LEFT JOIN {self._setPrefix(key)} ON {tmp_str} "
        return res

    def _processOn(self, on):
        if type(on) == list:
            ret = []
            for row in on:
                if len(row) == 0:
                    continue
                res = []
                for item in row:
                    value = ""
                    print(item[1])
                    if type(item[1]) == str and item[1].find(".") != -1:
                        value = item[1]
                    else:
                        value = self._formatType(item[1])
                    res.append(sql_util.listToStr(
                        [item[0], value], end=False, suffix=f" {item[2]} ", formatFunc=self._formatColumn))
                suffix = " AND "
                if len(item) == 4:
                    suffix = item[3]
                ret.append(
                    f'({sql_util.listToStr(res,end=False,suffix=f" {suffix} ")})')
            return sql_util.listToStr(ret, suffix=" AND ", end=False)

        else:
            res = []
            for item in on:
                res.append(sql_util.listToStr(
                    [item[0], item[1]], end=False, suffix=f" {item[2]} ", formatFunc=self._formatColumn))
            # print("on:",)
        return sql_util.listToStr(res, end=False, suffix=" AND ")
        # for key in on:

    def _processInnerJoin(self, join):
        res = sql_util.listToStr(
            join, prefix="INNER JOIN ", formatFunc=self._setPrefix, suffix=" ")
        return res

    def _processWhereItem(self, data):
        pass

    def _processWhere(self, data):
        res = " WHERE "
        next_suffix = ""
        i = 0
        for item in data:
            tmp_str = ""
            # print(type(item))
            if type(item[1]) == list:
                if len(item[1]) == 0:
                    tmp_str = " (1=1) "
                else:
                    tmp_str = f'({sql_util.listToStr(item[1],prefix=f" {self._formatColumn((item[0]))} = ",suffix=" OR ",end=False,formatFunc=self._formatType)})'
            else:
                tmp_str = f" {self._formatColumn((item[0]))} {item[2]} {self._formatType(item[1])} "
            if i == len(data)-1:
                next_suffix = ""
            elif len(item) == 4:
                next_suffix = item[3]
            else:
                next_suffix = " AND "
            res += f"{tmp_str}{next_suffix}"
            i += 1
        return res

    def getData(self, tablename, column=[], offset=0, limit=10, like="", where={}, inner_join={}, left_join={}, on={}, kv=True, fetchOne=False):
        column_str = ""
        tablename = self._setPrefix(tablename)
        prefixColumn = []
        for item in column:
            prefixColumn.append(item.split("[")[0])
        if len(column) != 0:
            column_str = sql_util.listToStr(
                prefixColumn, suffix=" , ", formatFunc=self._formatColumn, end=False)
        else:
            column = self._getTableStructure(tablename)
            column_str = "*"
        join_str = ""
        where_str = ""
        limit_str = ""
        offset_str = ""
        if inner_join:
            join_str += self._processInnerJoin(inner_join)
        if left_join:
            join_str += self._processLeftJoin(left_join)
        if where:
            where_str = self._processWhere(where)
        if limit:
            limit_str = f" LIMIT {limit} "
        if offset:
            offset_str = f" OFFSET {offset} "
        sql = f"SELECT {column_str} FROM {tablename} {join_str} {where_str} {limit_str} {offset_str}"
        data = self.exec(sql)
        if kv:
            res = self.listToKV(data, column)
            if fetchOne:
                if len(res) > 0:
                    return res[0]
                else:
                    return {}
            return res
        else:
            if fetchOne:
                if len(data) > 0:
                    return list(data)[0]
                else:
                    return []
            if data:
                return list(data)
            else:
                return [[]]

    def getTableCount(self, tablename):
        tablename = self._setPrefix(tablename)
        sql = f"SELECT COUNT(id) FROM {tablename}"
        count = self.exec(sql)
        return count[0][0]
    # def joinTable(self,):

    def addItem(self, tablename, data: dict):
        try:
            tablename = self._setPrefix(tablename)
            keys = sql_util.listToStr(data.keys(), suffix=" , ", end=False)
            values = sql_util.listToStr(
                data.values(), suffix=",", end=False, formatFunc=self._formatType)
            sql = f"INSERT INTO {tablename} ({keys}) VALUES ({values});"
            return self.exec(sql, add=True)
        except Exception as e:
            print(f"[x]{e}")
            return False

    def updateItem(self, tablename, data: dict, where: dict):
        try:
            tablename = self._setPrefix(tablename)
            values = sql_util.dictToStr(
                data, formatFunc=self._formatType, suffix=" , ")
            if where:
                where_str = self._processWhere(where)
            sql = f"UPDATE {tablename} SET {values}  {where_str};"
            return self.exec(sql)
        except Exception as e:
            print(f"[x]{e}")
            return False

    def deleteItem(self, tablename, where: dict):
        try:
            tablename = self._setPrefix(tablename)
            where_str = sql_util.dictToStr(
                where, formatFunc=self._formatType, suffix=" AND ")
            sql = f"DELETE FROM {tablename} WHERE ({where_str});"
            return self.exec(sql)
        except Exception as e:
            print(f"[x]{e}")
            return False

    def _formatType(self, val):
        if type(val) == str:
            if "'" in val:
                val = '"'+val+'"'
            else:
                val = "'"+val+"'"
        elif type(val) == time:
            val = time.strftime("%Y-%m-%d %H-%M%S")
        return val

    def _setPrefix(self, tablename):
        if self.prefix:
            return f"{self.prefix}_{tablename}"
        else:
            return tablename

    def _listToKV(self, tablename, data):
        res = {}
        i = 0
        for col in self._getTableStructure(tablename):
            res[col] = data[i]
            i += 1
        return res

    def _createTable(self, name, structure: dict):
        try:
            name = self._setPrefix(name)
            structureKeyList = structure.keys()
            items = []
            for key in structureKeyList:
                sub_str = sql_util.listToStr(structure[key], suffix=" ")
                items.append(f"{key} {sub_str}")
            items_str = sql_util.listToStr(items, suffix=", ", end=False)
            sql = f"""
            CREATE TABLE {name} ({items_str}); 
            """
            self.exec(sql)
            return True
        except Exception as e:
            print(f"[x]:{e}")

    def delteTable(self, name):
        try:
            name = self._setPrefix(name)
            sql = f"DROP TABLE {name}"
            self.exec(sql)
            return True
        except Exception as e:
            print(f"[x]:{e}")


if __name__ == "__main__":
    db = Db()
    now = datetime.datetime.now()
    db.delteTable("user")
    db.delteTable("city")
    db._createTable("user", {
        "id": ["INTEGER", "PRIMARY KEY"],
        "username": ["VARCHAR", "UNIQUE"],
        "password": ["VARCHAR"],
        "address": ["INT"],
        "is_delete": ["BOOLEAN", "DEFAULT false"],
        "createDate": ["DATE"]})
    db._createTable("city", {
        "id": ["INTEGER", "PRIMARY KEY"],
        "name": ["VARCHAR", "UNIQUE"],
    })
    db.addItem("user", {
        "username": "222",
        "password": "xcbo221",
        "address": 1,
        "createDate": datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    })
    db.addItem("user", {
        "username": "qq",
        "password": "xcbo221",
        "address": 2,
        "createDate": datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    })
    db.addItem("city", {
        "name": "杭州"
    })
    db.addItem("city", {
        "name": "温州"
    })
    db.addItem("city", {
        "name": "台州"
    })
    print(db.getData("user", column=["user.username", "user.address", "city.name"], inner_join=[
          "city"], on=[[("user.address", "city.id", "=")], [("city.name", "杭州", "!=")]]))
    # db.deleteItem("user",{
    #     "id":2
    # })
