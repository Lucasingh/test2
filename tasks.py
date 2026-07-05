"""
任务队列模块 - 支持 Redis + RQ 和内存双模式
用于异步执行数据采集任务，支持进度跟踪
"""
import logging
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, Optional, List

from config import CONFIG

logger = logging.getLogger(__name__)


class RedisTaskManager:
    """任务管理器 - 支持Redis + RQ和内存双模式

    内存模式下使用类级共享变量（_shared_tasks、_shared_worker、_shared_lock），
    确保 Streamlit 每次重渲染新建实例后仍能找到之前创建的任务。
    """

    # 类级共享变量（跨实例共享）
    _shared_tasks: Dict[str, Dict] = {}
    _shared_worker: Optional[threading.Thread] = None
    _shared_lock = threading.Lock()

    def __init__(self):
        self._use_redis = False

        # 尝试连接Redis
        redis_config = CONFIG.get('redis', {})
        if redis_config.get('enabled', False):
            try:
                import redis as redis_lib
                from rq import Queue
                self.conn = redis_lib.Redis(
                    host=redis_config.get('host', 'localhost'),
                    port=redis_config.get('port', 6379),
                    db=redis_config.get('db', 0),
                )
                self.conn.ping()
                self.queue = Queue('crawl', connection=self.conn)
                self._use_redis = True
                logger.info("Redis连接成功，使用RQ任务队列")
            except Exception as e:
                logger.warning(f"Redis连接失败: {e}，使用内存队列")

        # 确保内存工作线程已启动（首次启动时会在 _ensure_memory_worker 中打印日志）
        if not self._use_redis:
            self._ensure_memory_worker()

    @classmethod
    def _run_memory_worker(cls):
        """内存模式后台工作线程（类方法，使用类级共享变量）"""
        while True:
            try:
                pending_task = None
                with cls._shared_lock:
                    for task_id, task in cls._shared_tasks.items():
                        if task['status'] == 'pending':
                            pending_task = task
                            break

                if pending_task:
                    task_id = pending_task['task_id']
                    params = pending_task['params']

                    with cls._shared_lock:
                        if task_id in cls._shared_tasks:
                            cls._shared_tasks[task_id]['status'] = 'running'

                    logger.info(f"开始执行内存任务: {task_id}")
                    try:
                        result = crawl_task(params)
                        with cls._shared_lock:
                            if task_id in cls._shared_tasks:
                                cls._shared_tasks[task_id]['status'] = 'completed'
                                cls._shared_tasks[task_id]['progress'] = 100
                                cls._shared_tasks[task_id]['result'] = result
                        logger.info(f"内存任务完成: {task_id}, 新增 {result.get('added', 0)} 条")
                    except Exception as e:
                        logger.error(f"内存任务失败: {task_id}: {e}")
                        with cls._shared_lock:
                            if task_id in cls._shared_tasks:
                                cls._shared_tasks[task_id]['status'] = 'failed'
                                cls._shared_tasks[task_id]['error'] = str(e)
                else:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"内存工作线程异常: {e}")
                time.sleep(5)

    def _ensure_memory_worker(self):
        """确保内存工作线程在运行（类级线程）"""
        if RedisTaskManager._shared_worker is None or not RedisTaskManager._shared_worker.is_alive():
            RedisTaskManager._shared_worker = threading.Thread(
                target=RedisTaskManager._run_memory_worker, daemon=True
            )
            RedisTaskManager._shared_worker.start()
            logger.info("内存工作线程已启动")

    def create_task(self, task_type: str, params: Dict) -> str:
        """创建新任务"""
        if self._use_redis:
            from rq.job import Job
            job = self.queue.enqueue('tasks.crawl_task', params)
            logger.info(f"创建Redis任务: {job.id}, 类型: {task_type}")
            return job.id
        else:
            task_id = str(uuid.uuid4())
            with self._shared_lock:
                self._shared_tasks[task_id] = {
                    'task_id': task_id,
                    'task_type': task_type,
                    'params': params,
                    'status': 'pending',
                    'created_at': datetime.now(),
                    'progress': 0,
                    'message': '',
                }
            logger.info(f"创建内存任务: {task_id}, 类型: {task_type}")
            return task_id

    def create_crawl_task(self, user_id: int, sources: List[str], query: str, max_results: int = 20) -> str:
        """创建数据采集任务"""
        params = {
            'user_id': user_id,
            'selected_sources': sources,
            'search_query': query,
            'max_results': max_results,
        }
        return self.create_task('crawl', params)

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        if self._use_redis:
            try:
                from rq.job import Job
                from rq.exceptions import NoSuchJobError
                job = Job.fetch(task_id, connection=self.conn)
                return {
                    'task_id': task_id,
                    'status': job.get_status(),
                    'result': job.result if job.is_finished else None,
                    'error': job.exc_info if job.is_failed else None,
                }
            except NoSuchJobError:
                return None
        else:
            with self._shared_lock:
                task = self._shared_tasks.get(task_id)
                return dict(task) if task else None

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态详情（兼容旧接口）"""
        task = self.get_task(task_id)
        if not task:
            return None

        status = task.get('status', 'unknown')
        result = task.get('result')
        error = task.get('error', '')

        # 统一状态名称
        if status == 'finished':
            status = 'completed'

        if result and isinstance(result, dict):
            return {
                'status': status,
                'progress': 100 if status == 'completed' else task.get('progress', 0),
                'completed': result.get('added', 0),
                'total': result.get('added', 0) + result.get('duplicates', 0),
                'message': result.get('error', error),
            }

        return {
            'status': status,
            'progress': task.get('progress', 0),
            'completed': 0,
            'total': 0,
            'message': error or task.get('message', ''),
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if self._use_redis:
            try:
                from rq.job import Job
                job = Job.fetch(task_id, connection=self.conn)
                if job.get_status() == 'queued':
                    job.cancel()
                    return True
            except Exception:
                pass
        else:
            with self._shared_lock:
                if task_id in self._shared_tasks and self._shared_tasks[task_id]['status'] == 'pending':
                    self._shared_tasks[task_id]['status'] = 'cancelled'
                    return True
        return False

    def is_task_running(self) -> bool:
        """是否有任务正在运行"""
        if self._use_redis:
            try:
                from rq import Worker
                workers = Worker.all(connection=self.conn)
                for worker in workers:
                    if worker.get_current_job():
                        return True
                return False
            except Exception:
                return False
        else:
            with self._shared_lock:
                return any(t['status'] == 'running' for t in self._shared_tasks.values())

    def get_queue_size(self) -> int:
        """获取队列大小"""
        if self._use_redis:
            return len(self.queue)
        with self._shared_lock:
            return sum(1 for t in self._shared_tasks.values() if t['status'] == 'pending')

    def clear_completed(self):
        """清除已完成的任务"""
        with self._shared_lock:
            self._shared_tasks = {k: v for k, v in self._shared_tasks.items()
                                  if v['status'] in ('pending', 'running')}


def crawl_task(params: Dict) -> Dict:
    """数据采集任务函数（在worker线程/RQ worker中执行）"""
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
            max_results_per_source=max_results,
        )

        results = manager.crawl_all()
        manager.close()

        total_added = 0
        total_duplicates = 0

        for source_name, data in results.items():
            papers = data.get('papers', [])
            if papers:
                added, duplicates = db.add_papers(papers, user_id)
                total_added += added
                total_duplicates += duplicates
                db.add_crawl_history(user_id, source_name, added, 'success')

        logger.info(f"采集任务完成: 用户={user_id}, 新增={total_added}, 重复={total_duplicates}")
        return {'status': 'completed', 'added': total_added, 'duplicates': total_duplicates}

    except Exception as e:
        logger.error(f"采集任务失败: {e}")
        return {'status': 'failed', 'error': str(e)}
