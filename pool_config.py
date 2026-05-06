import pymysql
from dbutils.pooled_db import PooledDB
import os


DB_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
DB_USER = os.environ.get("MYSQL_USER", "root")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
DB_NAME = os.environ.get("MYSQL_DATABASE", "data1")


# 数据库配置类
class Config(object):
    DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    
    MYSQL_HOST = DB_HOST
    MYSQL_PORT = DB_PORT
    MYSQL_USER = DB_USER
    MYSQL_PASSWORD = DB_PASSWORD
    MYSQL_DATABASE = DB_NAME

    ServerPublicIP = DB_HOST
    # 创建数据库连接池
    PYMYSQL_POOL = PooledDB(
        creator=pymysql,  # 数据库驱动
        maxconnections=10,  # 最大连接数
        mincached=2,  # 初始化时创建的空闲连接数
        maxcached=5,  # 最大闲置连接数
        blocking=True,  # 阻塞等待
        maxusage=100,
        host=ServerPublicIP,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor
    )

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = (
        f"mysql://{DB_USER}:{DB_PASSWORD}@{ServerPublicIP}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    

    # 跨域资源共享
    CORS_HEADERS = 'Content-Type'
    
    # 其他配置项
    MAXTURN = 30
    APPID = os.environ.get("WECHAT_APPID", "")
    SECRET = os.environ.get("WECHAT_SECRET", "")
    END_REPLY = "今天的聊天结束啦，注意休息，我们改天再会~"
