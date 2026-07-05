"""
RQ Worker 启动脚本
运行方式: python worker.py
"""
import logging
import os
import sys

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq import Worker, Queue
import redis

# Redis 连接配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

def main():
    """启动 RQ Worker"""
    try:
        conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        conn.ping()
        logging.info("✅ Redis 连接成功")
    except Exception as e:
        logging.error(f"❌ Redis 连接失败: {e}")
        return
    
    worker = Worker(['crawl'], connection=conn)
    logging.info("🚀 RQ Worker 已启动，监听 crawl 队列")
    worker.work(with_scheduler=True)

if __name__ == '__main__':
    main()
