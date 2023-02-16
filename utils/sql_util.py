import json
import os
def loadJosn(path): 
    with open(path,'r' ,encoding="utf-8") as f:
        try:
            return json.loads(f.read())
        except Exception as e:
            print(e)
            return None

def saveJson(path,data):
    with open(path,'w',encoding='utf-8') as f:
        try:
            f.write(json.dumps(data,ensure_ascii=False))
            return True
        except Exception as e:
            print(e)
            return False
def listToStr(data:list[str],prefix:str="",suffix:str="",begin=True,end=True,formatFunc=""):
    tmp = ""
    i=0
    for item in data:
        if formatFunc:
            item = formatFunc(item)
        if len(data) == 1:
            if begin:
                tmp += f"{prefix}"
            tmp +=item 
            if end:
                tmp+=suffix
            return tmp
        if i==0:
            if begin:
                tmp += f"{prefix}{item}{suffix}"
            else:
                tmp += f"{item}{suffix}"
        elif i==len(data)-1:
            if end:
                tmp += f"{prefix}{item}{suffix}"
            else:
                tmp += f"{prefix}{item}"
        else:
            tmp += f"{prefix}{item}{suffix}"
        i+=1
    return tmp

def dictToStr(data:dict,format=" = ",formatFunc="",suffix="",end=True):
    tmp = ""
    i=0
    for key in data:
        _val = data[key]
        if formatFunc:
            _val = formatFunc(_val)
        
        if i==len(data)-1:
            if end:
                tmp+=f"{key}{format}{_val}"
            else:
                tmp+=f"{key}{format}{_val}{suffix}"
        else:
            tmp+=f"{key}{format}{_val}{suffix}"
        i+=1
    return tmp