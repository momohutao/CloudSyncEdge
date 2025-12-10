"""
批量写入器 - 实现状态批量写入机制
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict
import heapq

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from .models import (
    ECUStatusHistory, 
    HeartbeatLog, 
    CommandExecutionLog,
    AccessEventLog,
    RideRecord
)

logger = logging.getLogger(__name__)


class BatchWriter:
    """批量写入器 - 收集数据并批量写入数据库"""
    
    def __init__(self, session_factory, batch_size: int = 100, flush_interval: int = 5):
        """
        初始化批量写入器
        
        Args:
            session_factory: SQLAlchemy会话工厂
            batch_size: 批量大小
            flush_interval: 刷新间隔（秒）
        """
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # 批量队列
        self._status_queue = []
        self._heartbeat_queue = []
        self._command_queue = []
        self._event_queue = []
        self._ride_queue = []
        
        # 统计信息
        self._stats = {
            "total_written": 0,
            "status_written": 0,
            "heartbeat_written": 0,
            "command_written": 0,
            "event_written": 0,
            "ride_written": 0,
            "batch_operations": 0,
            "last_flush_time": None
        }
        
        # 定时刷新任务
        self._flush_task = None
        self._running = False
        
        logger.info(f"批量写入器初始化完成，批量大小: {batch_size}, 刷新间隔: {flush_interval}s")
    
    def start(self):
        """启动批量写入器"""
        if not self._running:
            self._running = True
            self._flush_task = asyncio.create_task(self._auto_flush_loop())
            logger.info("批量写入器已启动")
    
    async def stop(self):
        """停止批量写入器"""
        if self._running:
            self._running = False
            if self._flush_task:
                self._flush_task.cancel()
                try:
                    await self._flush_task
                except asyncio.CancelledError:
                    pass
            
            # 刷新所有剩余数据
            await self.flush_all()
            logger.info("批量写入器已停止")
    
    async def _auto_flush_loop(self):
        """自动刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                
                # 检查队列大小
                total_queued = (len(self._status_queue) + len(self._heartbeat_queue) + 
                              len(self._command_queue) + len(self._event_queue) + 
                              len(self._ride_queue))
                
                # 如果队列中有数据，执行刷新
                if total_queued > 0:
                    await self.flush_all()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动刷新循环异常: {e}")
                await asyncio.sleep(1)  # 错误后等待1秒
    
    async def add_status(self, status_data: Dict):
        """添加状态数据到批量队列"""
        self._status_queue.append(status_data)
        
        # 如果达到批量大小，立即刷新
        if len(self._status_queue) >= self.batch_size:
            await self.flush_status()
    
    async def add_heartbeat(self, heartbeat_data: Dict):
        """添加心跳数据到批量队列"""
        self._heartbeat_queue.append(heartbeat_data)
        
        if len(self._heartbeat_queue) >= self.batch_size:
            await self.flush_heartbeats()
    
    async def add_command_log(self, command_data: Dict):
        """添加命令日志到批量队列"""
        self._command_queue.append(command_data)
        
        if len(self._command_queue) >= self.batch_size:
            await self.flush_commands()
    
    async def add_event_log(self, event_data: Dict):
        """添加事件日志到批量队列"""
        self._event_queue.append(event_data)
        
        if len(self._event_queue) >= self.batch_size:
            await self.flush_events()
    
    async def add_ride_record(self, ride_data: Dict):
        """添加骑行记录到批量队列"""
        self._ride_queue.append(ride_data)
        
        if len(self._ride_queue) >= self.batch_size:
            await self.flush_rides()
    
    async def batch_save_statuses(self, statuses: List[Dict]):
        """批量保存状态数据"""
        self._status_queue.extend(statuses)
        await self.flush_status()
    
    async def batch_save_heartbeats(self, heartbeats: List[Dict]):
        """批量保存心跳数据"""
        self._heartbeat_queue.extend(heartbeats)
        await self.flush_heartbeats()
    
    async def batch_save_command_logs(self, commands: List[Dict]):
        """批量保存命令日志"""
        self._command_queue.extend(commands)
        await self.flush_commands()
    
    async def flush_status(self):
        """刷新状态队列"""
        if not self._status_queue:
            return
        
        try:
            async with self.session_factory() as session:
                # 使用批量插入
                await session.execute(
                    insert(ECUStatusHistory),
                    self._status_queue
                )
                await session.commit()
                
                written_count = len(self._status_queue)
                self._stats["status_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条状态记录")
                self._status_queue.clear()
                
        except Exception as e:
            logger.error(f"批量写入状态记录失败: {e}")
            # 失败时可以重试或记录到错误日志
    
    async def flush_heartbeats(self):
        """刷新心跳队列"""
        if not self._heartbeat_queue:
            return
        
        try:
            async with self.session_factory() as session:
                await session.execute(
                    insert(HeartbeatLog),
                    self._heartbeat_queue
                )
                await session.commit()
                
                written_count = len(self._heartbeat_queue)
                self._stats["heartbeat_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条心跳记录")
                self._heartbeat_queue.clear()
                
        except Exception as e:
            logger.error(f"批量写入心跳记录失败: {e}")
    
    async def flush_commands(self):
        """刷新命令队列"""
        if not self._command_queue:
            return
        
        try:
            async with self.session_factory() as session:
                await session.execute(
                    insert(CommandExecutionLog),
                    self._command_queue
                )
                await session.commit()
                
                written_count = len(self._command_queue)
                self._stats["command_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条命令记录")
                self._command_queue.clear()
                
        except Exception as e:
            logger.error(f"批量写入命令记录失败: {e}")
    
    async def flush_events(self):
        """刷新事件队列"""
        if not self._event_queue:
            return
        
        try:
            async with self.session_factory() as session:
                await session.execute(
                    insert(AccessEventLog),
                    self._event_queue
                )
                await session.commit()
                
                written_count = len(self._event_queue)
                self._stats["event_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条事件记录")
                self._event_queue.clear()
                
        except Exception as e:
            logger.error(f"批量写入事件记录失败: {e}")
    
    async def flush_rides(self):
        """刷新骑行队列"""
        if not self._ride_queue:
            return
        
        try:
            async with self.session_factory() as session:
                await session.execute(
                    insert(RideRecord),
                    self._ride_queue
                )
                await session.commit()
                
                written_count = len(self._ride_queue)
                self._stats["ride_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条骑行记录")
                self._ride_queue.clear()
                
        except Exception as e:
            logger.error(f"批量写入骑行记录失败: {e}")
    
    async def flush_all(self):
        """刷新所有队列"""
        if any([self._status_queue, self._heartbeat_queue, 
                self._command_queue, self._event_queue, 
                self._ride_queue]):
            
            logger.info(f"刷新所有队列，状态: {len(self._status_queue)}, "
                       f"心跳: {len(self._heartbeat_queue)}, "
                       f"命令: {len(self._command_queue)}, "
                       f"事件: {len(self._event_queue)}, "
                       f"骑行: {len(self._ride_queue)}")
            
            # 按优先级刷新：状态 > 心跳 > 命令 > 事件 > 骑行
            await self.flush_status()
            await self.flush_heartbeats()
            await self.flush_commands()
            await self.flush_events()
            await self.flush_rides()
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """获取队列大小"""
        return {
            "status_queue": len(self._status_queue),
            "heartbeat_queue": len(self._heartbeat_queue),
            "command_queue": len(self._command_queue),
            "event_queue": len(self._event_queue),
            "ride_queue": len(self._ride_queue),
            "total_queued": (len(self._status_queue) + len(self._heartbeat_queue) + 
                           len(self._command_queue) + len(self._event_queue) + 
                           len(self._ride_queue))
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        queue_sizes = self.get_queue_sizes()
        
        return {
            "batch_size": self.batch_size,
            "flush_interval": self.flush_interval,
            "queue_sizes": queue_sizes,
            "written_stats": self._stats.copy(),
            "is_running": self._running,
            "last_flush_time": self._stats["last_flush_time"].isoformat() if self._stats["last_flush_time"] else None
        }
    
    def clear_all_queues(self):
        """清除所有队列（谨慎使用）"""
        self._status_queue.clear()
        self._heartbeat_queue.clear()
        self._command_queue.clear()
        self._event_queue.clear()
        self._ride_queue.clear()
        
        logger.warning("所有批量队列已清空")


class PriorityBatchWriter(BatchWriter):
    """优先级批量写入器 - 支持按优先级批量写入"""
    
    def __init__(self, session_factory, batch_size: int = 100, flush_interval: int = 5):
        super().__init__(session_factory, batch_size, flush_interval)
        
        # 使用堆实现优先级队列
        self._priority_status_queue = []
        self._priority_heartbeat_queue = []
        self._priority_command_queue = []
        
        # 优先级映射
        self._priority_map = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3
        }
    
    async def add_priority_status(self, status_data: Dict, priority: str = "medium"):
        """添加优先级状态数据"""
        priority_level = self._priority_map.get(priority, 2)
        heapq.heappush(self._priority_status_queue, (priority_level, datetime.now(), status_data))
        
        if len(self._priority_status_queue) >= self.batch_size:
            await self.flush_priority_status()
    
    async def flush_priority_status(self):
        """刷新优先级状态队列"""
        if not self._priority_status_queue:
            return
        
        try:
            # 按优先级排序并提取数据
            sorted_items = []
            while self._priority_status_queue:
                priority, timestamp, data = heapq.heappop(self._priority_status_queue)
                sorted_items.append(data)
            
            # 批量写入
            async with self.session_factory() as session:
                await session.execute(
                    insert(ECUStatusHistory),
                    sorted_items
                )
                await session.commit()
                
                written_count = len(sorted_items)
                self._stats["status_written"] += written_count
                self._stats["total_written"] += written_count
                self._stats["batch_operations"] += 1
                self._stats["last_flush_time"] = datetime.now()
                
                logger.debug(f"批量写入 {written_count} 条优先级状态记录")
                
        except Exception as e:
            logger.error(f"批量写入优先级状态记录失败: {e}")
            # 失败时恢复数据到队列
            for data in sorted_items:
                heapq.heappush(self._priority_status_queue, (2, datetime.now(), data))