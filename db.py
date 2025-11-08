# db.py
import pymysql
from config import MYSQL

def get_conn():
    """Establish a connection to the MySQL database using settings from config.py"""
    return pymysql.connect(
        host=MYSQL["host"],
        port=MYSQL["port"],
        user=MYSQL["user"],
        password=MYSQL["password"],
        database=MYSQL["db"],
        charset=MYSQL["charset"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
