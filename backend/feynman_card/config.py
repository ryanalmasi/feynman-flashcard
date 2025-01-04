from dotenv import load_dotenv
import os
import redis

load_dotenv()

class AppConfig:
    SECRET_KEY = os.getenv("SECRET_KEY")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{os.getenv('DB_USRNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/Illumina"
    
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_URL = redis.from_url(os.getenv("REDIS_URL"))