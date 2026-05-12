"""Task Queue using Upstash Redis (Serverless)."""
import json
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Task queue using Upstash Redis (serverless Redis).
    Replaces local Redis for GCP Cloud Run deployment.
    """

    QUEUE_NAME = "jarvis:agent_tasks"
    RESULTS_PREFIX = "jarvis:results:"
    LOCK_PREFIX = "jarvis:locks:"

    def __init__(self):
        self._redis = None

    @property
    def redis(self):
        """Lazy initialization of Upstash Redis connection."""
        if self._redis is None:
            if not settings.UPSTASH_REDIS_REST_URL:
                raise ValueError("Upstash Redis not configured. Set UPSTASH_REDIS_REST_URL")
            from upstash_redis import Redis
            self._redis = Redis(
                url=settings.UPSTASH_REDIS_REST_URL,
                token=settings.UPSTASH_REDIS_REST_TOKEN,
            )
        return self._redis

    async def enqueue(self, task: Dict[str, Any], priority: int = 0) -> str:
        """
        Add a task to the queue.

        Args:
            task: Task dictionary with type, payload, etc.
            priority: Priority level (higher = more urgent)

        Returns:
            Task ID
        """
        import uuid
        task_id = str(uuid.uuid4())

        task_data = {
            "id": task_id,
            "priority": priority,
            "created_at": "now",
            **task
        }

        # Add to sorted set with priority as score
        # Higher priority = higher score = processed first
        score = 1000 + priority
        await self.redis.zadd(self.QUEUE_NAME, {json.dumps(task_data): score})

        logger.info(f"Task enqueued: {task_id} ({task.get('type', 'unknown')})")
        return task_id

    async def dequeue(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Get the next task from the queue (blocking pop).

        Args:
            timeout: Max seconds to wait for a task

        Returns:
            Task dictionary or None if timeout
        """
        # Use ZPOPMIN to get highest priority task
        result = await self.redis.zpopmin(self.QUEUE_NAME, count=1)

        if not result:
            return None

        task_data = json.loads(result[0][0])
        logger.info(f"Task dequeued: {task_data.get('id')} ({task_data.get('type')})")
        return task_data

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result/status."""
        result = await self.redis.get(f"{self.RESULTS_PREFIX}{task_id}")
        if result:
            return json.loads(result)
        return None

    async def set_task_result(
        self, task_id: str, result: Dict[str, Any], ttl: int = 3600
    ):
        """Store task result with TTL (default 1 hour)."""
        await self.redis.setex(
            f"{self.RESULTS_PREFIX}{task_id}",
            ttl,
            json.dumps(result)
        )

    async def acquire_lock(self, key: str, ttl: int = 300) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: Lock key
            ttl: Lock TTL in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        result = await self.redis.set(
            f"{self.LOCK_PREFIX}{key}",
            "1",
            nx=True,
            ex=ttl
        )
        return bool(result)

    async def release_lock(self, key: str):
        """Release a distributed lock."""
        await self.redis.delete(f"{self.LOCK_PREFIX}{key}")

    async def get_queue_length(self) -> int:
        """Get number of tasks in queue."""
        return await self.redis.zcard(self.QUEUE_NAME)

    async def clear_queue(self):
        """Clear all tasks from queue (for testing)."""
        await self.redis.delete(self.QUEUE_NAME)


# Singleton instance
task_queue = TaskQueue()