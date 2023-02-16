from urllib.parse import urlparse, parse_qs
import sqlite3
import pymysql
import json
import datetime
from dbutils.pooled_db import PooledDB, SharedDBConnection
import time
import threading
sqlstructureMap = {
    "int": ["INT", "INTEGER"],
    "str": ["VARCHAR(255)", "VARCHAR"],
    "key": ["PRIMARY KEY AUTO_INCREMENT", "PRIMARY KEY"]
}


class Database:
    _instance_lock = threading.Lock()

    def __init__(self, url) -> None:
        parsed_result = urlparse(url)
        query_dict = parse_qs(parsed_result.query)
        print("#"*32)
        print('协议     :', parsed_result.scheme)
        print('数据库名 :', parsed_result.path[1::])
        print('用户名:  :', parsed_result.username)
        print('密码     :', parsed_result.password)
        print('域名     :', parsed_result.hostname)
        print('端口     :', parsed_result.port)
        print('表名前缀 :', query_dict.get("prefix", [None])[0])
        print('超时     :', str(query_dict.get("timeout", [10])[0])+"秒")
        print("#"*32)
        self.schema = parsed_result.scheme
        self.databaseName = parsed_result.path[1::]
        self.username = parsed_result.username
        self.password = parsed_result.password
        self.hostname = parsed_result.hostname
        self.port = parsed_result.port
        self.prefix = query_dict.get("prefix", [None])[0]
        self.timeout = query_dict.get("timeout", [10])[0]
        self._conn = None
        self._tableList = []
        Database._instance = self
        self._connect()

    @classmethod
    def instance(cls, *args, **kwargs):
        if not hasattr(Database, "_instance"):
            with Database._instance_lock:   # 为了保证线程安全在内部加锁
                if not hasattr(Database, "_instance"):
                    Database._instance = Database(*args, **kwargs)
        return Database._instance

    def getDate(self):
        return datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S.000Z")

    def _connect(self):
        if self.schema == "sqlite":
            self._connectSqlite()
        elif self.schema == "mysql":
            self._connectMysql()

    def _connectSqlite(self, kv=True):
        if not self._conn:
            self._conn = sqlite3.connect(
                self.databaseName+".db", check_same_thread=False, timeout=self.timeout)
            self._conn.text_factory = str
        if kv == True:
            self._conn.row_factory = self.dict_factory
        else:
            self._conn.row_factory = None
        return self._conn

    def getConn(self, kv):
        if self.schema == "mysql":
            return self._connectMysql(kv)
        elif self.schema == "sqlite":
            return self._connectSqlite(kv)
        else:
            print("schema不匹配")

    def _connectMysql(self, kv):
        if not self._conn:
            self.POOL = PooledDB(
                creator=pymysql,
                maxconnections=10,
                maxcached=10,
                maxshared=10,
                blocking=True,
                setsession=[],
                host=self.hostname, port=self.port, user=self.username, passwd=self.password, db=self.databaseName, charset="utf8"
            )
        _conn = self.POOL.connection()
        return _conn

    def debug(func):
        def calcIntval(self, sql, commit=True, fetchOne=False, raise_exc=False, add=False, kv=True):
            print("fetchOne2", fetchOne)
            t1 = time.time()
            res = None
            try:
                res = func(self, sql, commit=True, fetchOne=fetchOne,
                           raise_exc=raise_exc, add=add, kv=kv)
            except Exception as e:
                print(f"[x]执行出错: {e}")
                if raise_exc:
                    raise Exception(e)
            t2 = time.time()
            delta = "%.3f" % (t2-t1)
            print(f"[{delta}s]执行语句:{sql}")
            return res
        return calcIntval

    @debug
    def exec(self, sql, commit=True, fetchOne=False, raise_exc=False, add=False, kv=True):
        conn = self.getConn(kv)
        cur = conn.cursor()
        cur.execute(sql)
        print("fetchOne", fetchOne)
        if fetchOne == True:
            data = cur.fetchone()
        else:
            data = cur.fetchall()
        if commit:
            conn.commit()
        cur.close()
        if add:
            return cur.lastrowid
        if not data:
            return []
        return data

    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _fixPrefix(self, tableName, *args):
        if self.prefix and self.prefix not in tableName:
            return f"{self.prefix}_{tableName}"
        else:
            return tableName

    def setPrefix(func):
        def _fixPrefix(self, tableName, *args):
            return func(self, self._fixPrefix(tableName), *args)
        return _fixPrefix

    @setPrefix
    def isExistTable(self, tablename):
        if len(self._tableList) == 0:
            self.getTableList()
        if tablename in self._tableList:
            return True
        else:
            return False

    def getTableList(self):
        sql = ""
        if self.schema == "sqlite":
            sql = "select name from sqlite_master where type='table' order by name"
        else:
            sql = "SHOW TABLES;"
        data = self.exec(sql, kv=False)
        print(data)
        res = []
        for item in data:
            res.append(item[0])
        self._tableList = res
        return res

    @setPrefix
    def create(self, tableName):
        return CreateTableFactory(self, tableName)

    @setPrefix
    def select(self, tableName):
        return SelectTableFacctory(self, tableName)

    @setPrefix
    def insert(self, tableName):
        return InsertTableFactory(self, tableName)

    @setPrefix
    def delete(self, tableName):
        return DeleteTableFacctory(self, tableName)

    @setPrefix
    def update(self, tableName):
        return UpdateTableFactory(self, tableName)

    @setPrefix
    def deleteTable(self, tableName):
        try:
            sql = f"DROP TABLE {tableName}"
            self.exec(sql)
            return True
        except Exception as e:
            print(f"[x]:{e}")


class BaseTableWhereFactory:
    def __init__(self, tableName):
        self.tableName = tableName
        self.whereList = []

    def _formatType(self, val):
        if type(val) == str:
            if "'" in val:
                val = '"'+val+'"'
            else:
                val = "'"+val+"'"
        return val

    def setWherePrefix(func):
        def setPrefix(self, key, val, *args):
            if "." not in key:
                key = self.db._fixPrefix(f"{self.tableName}.{key}")
            else:
                key = self.db._fixPrefix(key)
            print(key)
            val = _formatType(val)
            return func(self, key, val, *args)
        return setPrefix

    def wheres(self, wheres=[]):
        for where in wheres:
            self.where(*where)
        return self

    @setWherePrefix
    def where(self, key, val, exp="=", prefix="AND"):
        if len(self.whereList) > 0:
            self.whereList.append(f" {prefix} {key} {exp} {val}")
        else:
            self.whereList.append(f" WHERE {key} {exp} {val}")
        return self

    @setWherePrefix
    def andWhere(self, key, val, exp="="):
        self.whereList.append(f" AND {key} {exp} {val}")
        return self

    @setWherePrefix
    def orWhere(self, key, val, exp="="):
        self.whereList.append(f" OR {key} {exp} {val}")
        return self


class SelectTableFacctory(BaseTableWhereFactory):
    def __init__(self, dbinstance: Database, tableName):
        super().__init__(tableName)
        self.colList = []
        self.aliasMap = {}
        self.db = dbinstance
        self.leftJoinList = []
        self._offset = 0
        self._limit = 10
        self.count = False

    def offset(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def setColPrefix(func):
        def _fixPrefix(self, *args):
            if type(args[0]) == list:
                args = args[0]
            res = []
            # print(args)
            for colname in args:
                if self.tableName and f"." not in colname:
                    colname = f"{self.tableName}.{colname}"
                else:
                    colname = self.db._fixPrefix(colname)
                res.append(colname)
            return func(self, *res)
        return _fixPrefix
    # @Database.setPrefix

    def leftJoin(self, tableName, on=[]):
        tableName = self.db._fixPrefix(tableName)
        # if len(on) != 2:
        #     raise ValueError("参数出错")
        print(on)
        on[0] = f"{self.db._fixPrefix(on[0].split('.')[0])}.{on[0].split('.')[1]}"
        on[1] = f"{self.db._fixPrefix(on[1].split('.')[0])}.{on[1].split('.')[1]}"
        self.leftJoinList.append(
            f" LEFT JOIN {tableName} ON {on[0]} = {on[1]} ")
        return self

    def leftJoinFromMap(self, joinMap: dict):
        for key in joinMap:
            self.leftJoin(key, joinMap[key])
        return self

    @setColPrefix
    def columns(self, *args):
        for item in args:
            self.colList.append(item)
        return self

    def columnsList(self, columns: list):
        for item in columns:
            # self.colList.append(item)
            self.columns(item)
        return self

    def counts(self):
        self.count = True
        res = self.exec(fetchOne=True)
        if res:
            return res.get("total", 0)
        return 0

    def exec(self, fetchOne=False):
        if self.count:
            colStr = "COUNT(id) as total"
        elif len(self.colList) == 0:
            colStr = "*"
        else:
            colStr = listToStr(self.colList, suffix=",", end=False)
        leftJoinStr = listToStr(self.leftJoinList, suffix=" ")
        whereStr = listToStr(self.whereList, suffix=" ", end=False)
        sql = f"SELECT {colStr} FROM {self.tableName} {leftJoinStr} {whereStr}  LIMIT {self._offset},{self._limit};"
        return self.db.exec(sql, fetchOne=fetchOne)


class InsertTableFactory:
    def __init__(self, dbinstance: Database, tableName):
        self.tableName = tableName
        self.colList = []
        self.valList = []
        self.cacheValList = []
        self.db = dbinstance

    def columns(self, columns):
        for column in columns:
            self.col(*column)
        return self

    def columnMap(self, columns):
        for key in columns:
            self.col(key, columns[key])
        return self

    def col(self, key, value):
        if key not in self.colList:
            self.colList.append(key)
        self.valList.append(value)
        return self

    def pushCache(self):
        valStr = listToStr(self.valList, suffix=" , ",
                           end=False, formatFunc=_formatType)
        self.cacheValList.append(f"({valStr})")
        self.valList = []
        if len(self.cacheValList) > 1000:
            self.exec()
        return self

    def exec(self):
        colStr = listToStr(self.colList, suffix=" , ", end=False)
        if len(self.valList) > 0:
            self.pushCache()
        if len(self.cacheValList) > 0:
            valStr = listToStr(self.cacheValList, suffix=" , ", end=False)
            sql = f"INSERT INTO {self.tableName} ({colStr}) VALUES {valStr};"
            self.cacheValList = []
            # print(sql)
            return self.db.exec(sql, add=True)


class DeleteTableFacctory(BaseTableWhereFactory):
    def __init__(self, dbinstance: Database, tableName):
        super().__init__(tableName)
        self.db = dbinstance

    def exec(self):
        whereStr = listToStr(self.whereList, suffix=" ", end=False)
        sql = f"DELETE FROM {self.tableName} {whereStr}"
        return self.db.exec(sql, add=True)


class UpdateTableFactory(BaseTableWhereFactory):
    def __init__(self, dbinstance: Database, tableName):
        super().__init__(tableName)
        self.db = dbinstance
        self.updateList = []

    def set(self, key, value):
        value = _formatType(value)
        self.updateList.append(f"{key} = {value}")
        return self

    def setDict(self, sets: dict):
        for key in sets:
            self.set(key, sets[key])
        return self

    def setList(self, sets):
        for set in sets:
            self.set(*set)
        return self

    def exec(self):
        updateStr = listToStr(self.updateList, suffix=",", end=False)
        whereStr = listToStr(self.whereList, suffix=" ", end=False)
        sql = f"UPDATE {self.tableName} SET {updateStr} {whereStr};"
        return self.db.exec(sql, add=True)


class CreateTableFactory:
    def __init__(self, dbinstance: Database, tableName):
        self.tableName = tableName
        self.colList = []
        self.db = dbinstance

    def columns(self, columns={}):
        for key in columns:
            self.col(key, columns[key])
        return self

    def col(self, key: str, val=[]):
        if self.db.schema == "sqlite":
            index = 1
        else:
            index = 0
        for i in range(len(val)):
            _tmp = sqlstructureMap.get(val[i])
            if _tmp:
                val[i] = _tmp[index]
        self.colList.append(f"{key} {listToStr(val,suffix=' ',end=False)}")
        return self

    def exec(self):
        colStr = listToStr(self.colList, suffix=" , ", end=False)
        sql = f"CREATE TABLE {self.tableName} ( {colStr} );"
        return self.db.exec(sql)


def listToStr(data: list[str], prefix: str = "", suffix: str = "", begin=True, end=True, formatFunc=""):
    tmp = ""
    i = 0
    for item in data:
        if formatFunc:
            item = formatFunc(item)
        if len(data) == 1:
            if begin:
                tmp += f"{prefix}"
            tmp += item
            if end:
                tmp += suffix
            return tmp
        if i == 0:
            if begin:
                tmp += f"{prefix}{item}{suffix}"
            else:
                tmp += f"{item}{suffix}"
        elif i == len(data)-1:
            if end:
                tmp += f"{prefix}{item}{suffix}"
            else:
                tmp += f"{prefix}{item}"
        else:
            tmp += f"{prefix}{item}{suffix}"
        i += 1
    return tmp


def dictToStr(data: dict, format=" = ", formatFunc="", suffix="", end=True):
    tmp = ""
    i = 0
    for key in data:
        _val = data[key]
        if formatFunc:
            _val = formatFunc(_val)

        if i == len(data)-1:
            if end:
                tmp += f"{key}{format}{_val}"
            else:
                tmp += f"{key}{format}{_val}{suffix}"
        else:
            tmp += f"{key}{format}{_val}{suffix}"
        i += 1
    return tmp


def _formatType(val):
    if type(val) == str:
        if "'" in val:
            val = '"'+val+'"'
        else:
            val = "'"+val+"'"
    return val
