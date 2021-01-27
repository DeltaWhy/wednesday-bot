import asyncio
import datetime
from dataclasses import dataclass, field
from typing import Any, List, Dict
import heapq
import traceback


class Scheduler:
    def __init__(self, interval=60):
        self.interval = interval
        self.heap = []

    def schedule(self, time, fn, *args, **kwargs):
        task = ScheduledTask(time, fn, args, kwargs)
        print(task)
        heapq.heappush(self.heap, task)

    async def tick(self):
        print(datetime.datetime.now(tz=datetime.timezone.utc))
        while len(self.heap) > 0 and self.heap[0].time <= datetime.datetime.now(tz=datetime.timezone.utc):
            try:
                task = heapq.heappop(self.heap)
                res = task.fn(*task.args, **task.kwargs)
                if asyncio.iscoroutine(res):
                    await res
            except:
                traceback.print_exc()



    async def run(self):
        while True:
            await asyncio.gather(
                self.tick(),
                asyncio.sleep(60),
            )


@dataclass(order=True)
class ScheduledTask:
    time: datetime.datetime
    fn: Any = field(compare=False)
    args: List[Any] = field(compare=False)
    kwargs: Dict[str, Any] = field(compare=False)
