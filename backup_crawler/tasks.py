"""
任务队列模块 - 基于 Redis + RQ（生产环境就绪）
"""
import logging
import uuid
import threading
from datetime import datetime
from typing import Dict, Optional, Any, Callable
import redis
from rq import Queue, Worker
from rq.job import Job
from rq.exceptions import NoSuchJobError

from config import CONFIG

logger = logging.getLogger(__name__)

class RedisTaskManager:
    """基于 Redis + RQ 的任务管理器"""
    
    def __init__(self):
        self._use_redis = False
        self.tasks = {}
        self._worker_thread = None
        self._lock = threading.Lock()
        
        # 检查Redis是否启用
        redis_config = CONFIG.get('redis', {})
        if redis_config.get('enabled', False):
            try:
                self.conn = redis.Redis(
                    host=redis_config.get('host', 'localhost'),
                    port=redis_config.get('port', 6379),
                    db=redis_config.get('db', 0)
                )
                self.conn.ping()
                self.queue = Queue('crawl', connection=self.conn)
                self._use_redis = True
                logger.info("✅ Redis 连接成功，使用 Redis + RQ 任务队列")
            except Exception as e:
                logger.warning(f"⚠️ Redis 连接失败: {e}，将使用内存队列作为备用")
                self._use_redis = False
        else:
            logger.info("✅ Redis 已禁用，使用内存队列")
    
    def _run_memory_worker(self):
        """内存模式下的后台工作线程"""
        while True:
            try:
                # 查找待处理的任务
                pending_task = None
                with self._lock:
                    for task_id, task in self.tasks.items():
                        if task['status'] == 'pending':
                            pending_task = task
                            break
                
                if pending_task:
                    task_id = pending_task['task_id']
                    params = pending_task['params']
                    
                    # 更新任务状态为运行中
                    with self._lock:
                        if task_id in self.tasks:
                            self.tasks[task_id]['status'] = 'running'
                    
                    logger.info(f"开始执行内存任务: {task_id}")
                    
                    try:
                        # 执行任务
                        result = crawl_task(params)
                        
                        # 更新任务状态为完成
                        with self._lock:
                            if task_id in self.tasks:
                                self.tasks[task_id]['status'] = 'completed'
                                self.tasks[task_id]['progress'] = 100
                                self.tasks[task_id]['result'] = result
                        
                        logger.info(f"内存任务完成: {task_id}, 新增 {result.get('added', 0)} 条")
                    
                    except Exception as e:
                        logger.error(f"内存任务失败: {task_id}, {e}")
                        with self._lock:
                            if task_id in self.tasks:
                                self.tasks[task_id]['status'] = 'failed'
                                self.tasks[task_id]['error'] = str(e)
                
                # 没有任务时休眠
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"内存工作线程异常: {e}")
                import time
                time.sleep(5)
    
    def _ensure_memory_worker(self):
        """确保内存工作线程在运行"""
        if not self._use_redis and (self._worker_thread is None or not self._worker_thread.is_alive()):
            self._worker_thread = threading.Thread(target=self._run_memory_worker, daemon=True)
            self._worker_thread.start()
            logger.info("内存工作线程已启动")
    
    def create_task(self, task_type: str, params: Dict) -> str:
        """创建新任务"""
        if self._use_redis:
            job = self.queue.enqueue(crawl_task, params)
            logger.info(f"创建 Redis 任务: {job.id}, 类型: {task_type}")
            return job.id
        else:
            task_id = str(uuid.uuid4())
            with self._lock:
                self.tasks[task_id] = {
                    'task_id': task_id,
                    'task_type': task_type,
                    'params': params,
                    'status': 'pending',
                    'created_at': datetime.now(),
                    'progress': 0,
                    'message': ''
                }
            logger.info(f"创建内存任务: {task_id}, 类型: {task_type}")
            # 确保工作线程在运行
            self._ensure_memory_worker()
            return task_id
    
    def create_crawl_task(self, user_id: int, sources: list, query: str, max_results: int = 20) -> str:
        """创建采集任务"""
        params = {
            'user_id': user_id,
            'selected_sources': sources,
            'search_query': query,
            'max_results': max_results
        }
        return self.create_task('crawl', params)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        if self._use_redis:
            try:
                job = Job.fetch(task_id, connection=self.conn)
                return {
                    'task_id': task_id,
                    'status': job.get_status(),
                    'result': job.result if job.is_finished else None,
                    'error': job.exc_info if job.is_failed else None
                }
            except NoSuchJobError:
                return None
        else:
            with self._lock:
                task = self.tasks.get(task_id)
                if task:
                    return dict(task)
                return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态详情（兼容旧接口）"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        status = task.get('status', 'unknown')
        result = task.get('result')
        error = task.get('error', '')
        
        # 统一状态名称：把 RQ 的 finished 转换成 completed
        if status == 'finished':
            status = 'completed'
        
        if result and isinstance(result, dict):
            return {
                'status': status,
                'progress': 100 if status == 'completed' else task.get('progress', 0),
                'completed': result.get('added', 0),
                'total': result.get('added', 0) + result.get('duplicates', 0),
                'message': result.get('error', error)
            }
        return {
            'status': status,
            'progress': task.get('progress', 0),
            'completed': 0,
            'total': 0,
            'message': error or task.get('message', '')
        }
    
    def update_task_progress(self, task_id: str, progress: int, message: str = ""):
        """更新任务进度（仅内存模式）"""
        if not self._use_redis and task_id in self.tasks:
            self.tasks[task_id]['progress'] = progress
            self.tasks[task_id]['message'] = message
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if self._use_redis:
            try:
                job = Job.fetch(task_id, connection=self.conn)
                if job.get_status() == 'queued':
                    job.cancel()
                    logger.info(f"Redis 任务已取消: {task_id}")
                    return True
            except NoSuchJobError:
                pass
        else:
            if task_id in self.tasks and self.tasks[task_id]['status'] == 'pending':
                self.tasks[task_id]['status'] = 'cancelled'
                logger.info(f"内存任务已取消: {task_id}")
                return True
        return False
    
    def is_task_running(self) -> bool:
        """检查是否有任务正在运行"""
        if self._use_redis:
            workers = Worker.all(connection=self.conn)
            for worker in workers:
                if worker.get_current_job():
                    return True
            return False
        else:
            return any(t['status'] == 'running' for t in self.tasks.values())
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        if self._use_redis:
            return len(self.queue)
        return sum(1 for t in self.tasks.values() if t['status'] == 'pending')

def crawl_task(params: Dict) -> Dict:
    """采集任务函数（在 RQ worker 中执行）"""
    from crawler import CrawlerManager
    from database import db
    
    search_query = params.get('search_query', '')
    selected_sources = params.get('selected_sources', [])
    max_results = params.get('max_results', 20)
    user_id = params.get('user_id', 1)
    
    try:
        manager = CrawlerManager(
            max_workers=4,
            search_query=search_query,
            enabled_sources=selected_sources,
            max_results_per_source=max_results
        )
        
        results = manager.crawl_all()
        manager.close()
        
        total_added = 0
        total_duplicates = 0
        
        for source_name, data in results.items():
            if data['papers']:
                added, duplicates = db.add_papers(data['papers'], user_id)
                total_added += added
                total_duplicates += duplicates
                db.add_crawl_history(user_id, source_name, added, 'success')
        
        return {'status': 'completed', 'added': total_added, 'duplicates': total_duplicates}
    
    except Exception as e:
        logger.error(f"采集任务失败: {e}")
        return {'status': 'failed', 'error': str(e)}
