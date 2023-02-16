# -*- coding: UTF-8 -*-
from enum import Enum
from fastapi import APIRouter
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, FastAPI, HTTPException
from starlette import status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext  # passlib 处理哈希加密的包
from pydantic import BaseModel
import app.lib.apiRes as apiRes
from utils.storage import Database
# to get a string like this run: openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # 密钥
ALGORITHM = "HS256"  # 算法
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 访问令牌过期分钟
# class Role(Enum):
#     admin:"ADMIN"
#     tourist:"TOURIST"
router = APIRouter()
'''用户数据（模拟数据库用户表）；账号：johndoe 密码：secret
   用于我们稍后验证。'''
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
    }
}

'''FastAPI参数类型验证模型'''
# token url相应模型


class UserResult(BaseModel):
    username: str
    roles: list[str]
    accessToken: str
    refreshToken: str
    expires: str


class Token(BaseModel):
    access_token: str
    token_type: str

# 令牌数据模型


class TokenData(BaseModel):
    username: str = None

# 用户基础模型


class User(BaseModel):
    id: int
    username: str
    email: str = None
    full_name: str = None
    disabled: bool = None
    type: int
 # 用户输入数据模型


class UserInDB(User):
    hashed_password: str


class CreateUserDict(BaseModel):
    username: str = ""
    password: str = ""
    role: int = 2


class UserInput(BaseModel):
    username: str = ""
    password: str = ""


'''为了数据安全，我们利用PassLib对入库的用户密码进行加密处理，推荐的加密算法是"Bcrypt"
其中，我们主要使用下面方法：
	pwd_context.hash(password) # 对密码进行加密
	pwd_context.verify(plain_password, hashed_password) 对密码进行校验
	----- 具体使用可见后面代码 ------
'''
# Context是上下文,CryptContext是密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# oauth2_scheme是令牌对象，token: str = Depends(oauth2_scheme)后就是之前加密的令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
'''
OAuth2PasswordBearer是接收URL作为参数的一个类：客户端会向该URL发送username和password参数，然后得到一个token值。
OAuth2PasswordBearer并不会创建相应的URL路径操作，只是指明了客户端用来获取token的目标URL。
当请求到来的时候，FastAPI会检查请求的Authorization头信息，如果没有找到Authorization头信息，或者头信息的内容不是Bearer token，它会返回401状态码(UNAUTHORIZED)。
'''
# verify_password验证密码
# plain_password普通密码, hashed_password哈希密码
# 返回True和False


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 获取哈希密码;普通密码进去，对应的哈希密码出来。


def get_password_hash(password):
    return pwd_context.hash(password)

# 模拟从数据库读取用户信息


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

# 验证用户


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# 创建访问令牌（token）


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta  # expire 令牌到期时间
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


########## 新货分界线 ###########
'''数据请求验证
用户拿到token信息后，必须在后续请求中，头信息的Authorization带有Bearer token，才能访问其他数据接口。
下面添加一个校验函数，对请求的合法性进行校验，读取token内容解析并进行验证，验证token通过后，获取接口响应数据'''

# 获取当前用户
# 通过oauth2_scheme，拿到用户请求头文件里的token


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # jwt 解码
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 通常在jwt 解码会进行验证抛出各种异常PyJWTError，如令牌过期等；
        # 获取生成token时候，我们放进去的username信息
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except Exception as e:
        print(e)
    # 获取该用户信息
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


# 获取当前激活用户，通过数据库信息及相关条件对用户有效性进行过滤；如该用户存在，密码正确，token验证通过，但数据库字段显示该用户被封号或欠费了（非激活用户），就这此处触发异常，结束访问。
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# 数据请求接口（获得自己的数据库信息），依赖上面的校验函数


@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


# @router.post("/login", response_model=UserLogin)
# async def login(form: UserInput):
#     data = Db.instance.getData(
#         "user", where=[("username", form.username, "=")], fetchOne=True)
#     print(data)
#     return apiRes.resp_200(data=data)

''' ----  登录验证，获取token的接口 --------
	用户发送post请求获取token,后端验证该用户是否存在，密码是否正确。如果验证通过，会生成‘token’给到用户。'''
# name = johndoe    password = secret


@router.post("/login")
async def login_for_access_token(form_data: UserInput):
    # 1、验证用户
    # user = get_user(fake_db, username)
    # user = Db.instance.getData(
    #     "user", where=[("username", form_data.username, "=")], fetchOne=True)
    user = Database.instance().select("user").where(
        "username", form_data.username).exec(fetchOne=True)
    print("user", user)
    # if user and form_data.password != user["password"]:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Incorrect username or password",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 2、access_token_expires访问令牌过期
    # timedelta表示两个datetime对象之间的差异。（来自datetime包）
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 3、create_access_token创建访问令牌
    access_token = create_access_token(
        data={"sub": user['username']}, expires_delta=access_token_expires)
    return apiRes.resp_200(data=UserResult(username=user["username"],
                                           roles=["admin"],
                                           accessToken=access_token,
                                           refreshToken="refresh",
                                           expires=str(access_token_expires)).dict())

    # 返回
    # return {"access_token": access_token, "token_type": "bearer"}


# @router.post("/edit-password")
# async def editPassword(form: UserInput):
#     user = Db.instance.getData(
#         "user", where=[("username", form.username, "=")], fetchOne=True)
#     print("user", user)
#     if user:
#         hash_passwd = get_password_hash(form.password)
#         Db.instance.updateItem(tablename="user", data={
#             "password": hash_passwd,
#         }, where={
#             "id": user["id"]
#         })
#         return apiRes.resp_200(data=hash_passwd)
#     else:
#         return apiRes.resp_200(data="找不到用户")


# @router.post("/create-user")
# async def createUser(form: CreateUserDict):
#     user = Db.instance.getData(
#         "user", where=[("username", form.username, "=")], fetchOne=True)
#     print("user", user)
#     if user:

#         # hash_passwd = get_password_hash(form.password)
#         # Db.instance.updateItem(tablename="user", data={
#         #     "password": hash_passwd,
#         # }, where={
#         #     "id": user["id"]
#         # })
#         return apiRes.resp_200(data="用户已存在")
#     else:
#         Db.instance.addItem("user", {
#             "username": form.username,
#             "password": get_password_hash(form.password),
#             "type": form.role,
#             "createDate": datetime.now().strftime("%Y-%m-%d %H-%M-%S")
#         })
#         return apiRes.resp_200(data={
#             "msg": "创建成功",
#             "datail": Db.instance.getData("user", where=[("username", form.username, "=")], fetchOne=True)
#         })
    # Db.instance.addItem("user", {
    #     "username": form.username,
    #     "password": get_password_hash(form.password),
    #     "address": 2,
    #     "createDate": datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    # })


@router.get("/info")
async def info():
    # print(form.dict())
    # user =
    # Db.instance
    # data = Db.instance().getData(
    #     "user", where=[("username", "admin", "=")])
    data = Database.instance().select("user").where("username", "admin")
    print(data)
    return apiRes.resp_200(data=data[0])
    # user
    # return Http
