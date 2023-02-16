from utils.db import Db
import datetime
import uuid
import time
import random


def initStorage():
    database = Db()
    # database.delteTable("user")
    # database._createTable("user", {
    #     "id": ["INTEGER", "PRIMARY KEY"],
    #     "username": ["VARCHAR", "UNIQUE"],
    #     "password": ["VARCHAR"],
    #     "type": ["INT"],
    #     "disabled": ["BOOLEAN", "DEFAULT false"],
    #     "createDate": ["DATE"]
    # })
    database.addItem("user", {
        "username": "admin",
        "password": "$2b$12$rQFPHvGK7dgZCzfpXtdxyuQUAILrNT8F4Oh6cPu/46PDwrf4iXJZS",
        "createDate": "2023-01-16 22:45:18"
    })
    t1 = time.time()
    for i in range(1000):
        # database.addItem("user_role", {
        #     "from_user": i+1,
        #     "from_role": 1,  # xcbo221
        # })

        # database.addItem("role", {
        #     "name": "游客"+str(i),
        #     "role": 1
        # })
        database.addItem("user", {
            "username": str(uuid.uuid1()),
            "password": "$2b$12$rQFPHvGK7dgZCzfpXtdxyuQUAILrNT8F4Oh6cPu/46PDwrf4iXJZS",  # xcbo221
            "createDate": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    print(f"用时:{int(time.time()-t1)}s")


if __name__ == "__main__":
    check = input("即将清空所有数据，按 y 确认: ")
    if check == "y":
        initStorage()
    else:
        print("用户取消")
