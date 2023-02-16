
import uvicorn 
import utils.sql_util as sql_util
from app.main import app
config = sql_util.loadJosn("setting.json")
if __name__ == "__main__":
    uvicorn.run(app=app,host=config['host'],port=config['port'])
