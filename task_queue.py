"""
Brown V2 | task_queue.py
Приоритетная очередь задач: премиум-пользователи идут первыми.

Priority: 0 = premium (выше), 1 = обычный пользователь.
Очередь неблокирующая — добавление не ждёт выполнения.
Лимит параллельных задач задаётся через MAX_WORKERS.
"""

import asyncio
import heapq
import time
import logging

logger = logging.getLogger("task_queue")

MAX_WORKERS = 8  # Максимум параллельных задач

PRIORITY_PREMIUM = 0
PRIORITY_NORMAL = 1

_queue: list = []          # heapq: (priority, sequence, coroutine_factory, args, kwargs)
_queue_lock = asyncio.Lock()
_seq = 0                   # для сохранения FIFO внутри одного приоритета
_sem: asyncio.Semaphore | None = None
_worker_task: asyncio.Task | None = None
_running = False


def _get_sem() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(MAX_WORKERS)
    return _sem


async def _worker():
    """Фоновый воркер — достаёт задачи из очереди и запускает их."""
    global _running
    _running = True
    while True:
        async with _queue_lock:
            if not _queue:
                item = None
            else:
                item = heapq.heappop(_queue)

        if item is None:
            await asyncio.sleep(0.2)
            continue

        _priority, _seq_num, factory, args, kwargs = item
        priority_label = "PREMIUM" if _priority == PRIORITY_PREMIUM else "обычный"
        logger.info(f"[QUEUE] Запускаю задачу ({priority_label}), осталось в очереди: {len(_queue)}")

        async def _run(f, a, kw):
            async with _get_sem():
                try:
                    await f(*a, **kw)
                except Exception as e:
                    logger.error(f"[QUEUE] Ошибка в задаче: {e}")

        asyncio.create_task(_run(factory, args, kwargs))


async def start_worker():
    """Запускает фоновый воркер очереди (вызывается один раз при старте бота)."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())
        logger.info("[QUEUE] Воркер запущен")


async def enqueue(coro_factory, *args, premium: bool = False, **kwargs):
    """
    Добавляет задачу в очередь.

    coro_factory — async-функция (не корутина!), будет вызвана с *args, **kwargs.
    premium=True — задача идёт в начало очереди.

    Пример:
        await enqueue(botnet_main, chat_username, msg_id, uid, uname, url, premium=is_premium)
    """
    global _seq
    priority = PRIORITY_PREMIUM if premium else PRIORITY_NORMAL
    async with _queue_lock:
        _seq += 1
        heapq.heappush(_queue, (priority, _seq, coro_factory, args, kwargs))
        logger.info(f"[QUEUE] Добавлена задача {'PREMIUM' if premium else 'обычный'}, очередь: {len(_queue)}")


async def queue_status() -> dict:
    """Возвращает текущее состояние очереди."""
    async with _queue_lock:
        premium_count = sum(1 for item in _queue if item[0] == PRIORITY_PREMIUM)
        normal_count = sum(1 for item in _queue if item[0] == PRIORITY_NORMAL)
    return {
        "total": premium_count + normal_count,
        "premium": premium_count,
        "normal": normal_count,
        "workers": MAX_WORKERS,
    }
