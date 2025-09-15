"""
Async task queue for handling background operations
"""
from typing import Any, Dict, List, Optional, Callable, Awaitable
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
import traceback

logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Represents a task in the queue"""
    id: str
    coroutine: Awaitable
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = 'pending'

class TaskQueue:
    """Async task queue with priority and error handling"""
    
    def __init__(
        self,
        max_concurrent: int = 5,
        retry_delay: int = 5
    ):
        self.max_concurrent = max_concurrent
        self.retry_delay = retry_delay
        self.tasks: Dict[str, Task] = {}
        self.queue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._stop = False
        self._workers: List[asyncio.Task] = []
        
        # Callbacks
        self.on_success: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_retry: Optional[Callable] = None
    
    async def start(self):
        """Start the task queue workers"""
        self._stop = False
        self._workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.max_concurrent)
        ]
    
    async def stop(self):
        """Stop the task queue"""
        self._stop = True
        # Wait for running tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values())
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        self._workers = []
    
    async def add_task(
        self,
        task_id: str,
        coroutine: Awaitable,
        priority: int = 0
    ) -> str:
        """Add a task to the queue"""
        task = Task(
            id=task_id,
            coroutine=coroutine,
            priority=priority
        )
        self.tasks[task_id] = task
        await self.queue.put((priority, task_id))
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task"""
        task = self.tasks.get(task_id)
        if not task:
            return None
            
        return {
            'id': task.id,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'retries': task.retries,
            'last_error': task.last_error
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        # Remove from pending queue
        task = self.tasks.pop(task_id, None)
        if not task:
            return False
            
        # Cancel if running
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
            
        task.status = 'cancelled'
        return True
    
    async def _worker(self):
        """Worker process to execute tasks"""
        while not self._stop:
            try:
                # Get next task
                priority, task_id = await self.queue.get()
                task = self.tasks.get(task_id)
                
                if not task or task.status == 'cancelled':
                    self.queue.task_done()
                    continue
                
                # Execute task
                task.status = 'running'
                task.started_at = datetime.utcnow()
                
                try:
                    # Create task
                    coro = asyncio.create_task(task.coroutine)
                    self.running_tasks[task_id] = coro
                    
                    # Wait for completion
                    await coro
                    
                    # Mark as completed
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()
                    
                    # Trigger success callback
                    if self.on_success:
                        await self.on_success(task)
                    
                except Exception as e:
                    # Handle task error
                    error = str(e)
                    logger.error(
                        f"Task {task_id} failed: {error}\n"
                        f"{traceback.format_exc()}"
                    )
                    
                    task.last_error = error
                    task.retries += 1
                    
                    # Retry if not exceeded max retries
                    if task.retries < task.max_retries:
                        task.status = 'retry'
                        # Add back to queue with delay
                        await asyncio.sleep(self.retry_delay)
                        await self.queue.put((priority, task_id))
                        
                        # Trigger retry callback
                        if self.on_retry:
                            await self.on_retry(task)
                    else:
                        task.status = 'failed'
                        # Trigger error callback
                        if self.on_error:
                            await self.on_error(task)
                
                finally:
                    # Cleanup
                    if task_id in self.running_tasks:
                        del self.running_tasks[task_id]
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'retry': 0
        }
        
        for task in self.tasks.values():
            stats[task.status] = stats.get(task.status, 0) + 1
            
        return {
            **stats,
            'total': len(self.tasks),
            'queue_size': self.queue.qsize(),
            'workers': len(self._workers)
        }

# Example usage:
"""
async def example_task():
    # Task implementation
    pass

# Create queue
queue = TaskQueue(max_concurrent=5)

# Start queue
await queue.start()

# Add task
task_id = await queue.add_task('example', example_task())

# Get status
status = await queue.get_task_status(task_id)

# Stop queue
await queue.stop()
"""
