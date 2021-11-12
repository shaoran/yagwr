import asyncio
import threading
import logging

from .logger import NamedLogger

module_logger = logging.getLogger(__name__)
"""
The default logger of this module
"""


class AsyncInThread:
    """
    This class allows to execute an asyncio loop in a thread.

    Sometimes you need to execute asynchronous code in a seprate thread
    inside a synchronous program. Starting the ioloop in a thread
    is a chore. This class allows you to do that.

    Inside your main task, you can get the running loop via
    :py:func:`asyncio.get_running_loop`. The ``loop`` will have an extra
    attribute ``thread_controller`` with a reference to the
    ``AsyncInThread`` object.

    Example:

    .. code-block:: python

        import asyncio
        from yagwr.async_in_thread import AsyncInThread

        async def main_task():
            print("This is the main task")
            while True:
                print("Doing stuff")
                await some_other_function()
                await asyncio.sleep(1)

        ath = AsyncInThread(main_task())

        ath.start()
        try:
            while True:
                execute_task()
                if should_quit():
                    break
        finally:
            ath.stop()
    """

    def __init__(self, coro, name="AsyncThread", log=module_logger):
        """
        :param coroutine coro: a coroutine, the main task. When :py:meth:`stop` is executed,
            the task is cancelled. The task is responsible to cancel other tasks
            that it might have spawned.
        :param str name: a string used in logging and for the name of the
            thread
        :param logging.Logger log: the logger where debug info is logged to.
        """
        self.loop = None
        self.coro = coro
        self.name = name
        self.main_task = None
        self.th = None
        self.log = NamedLogger(log, {"name": name})

    def start(self):
        self.log.debug("Starting thread to boot up the asyncio loop")
        self.th = threading.Thread(target=self.__running_app__, name=self.name)
        self.th.start()

    def stop(self):
        self.log.debug("Stopping thread that runs the asyncio loop")
        if self.loop is None:
            return

        self.log.debug("Scheduling __stop_main_task()")
        self.loop.call_soon_threadsafe(
            lambda: self.loop.create_task(self.__stop_main_task__())
        )
        self.log.debug("Joing thread")
        self.th.join()

        self.log.debug("Closing asyncio loop")
        self.loop.close()
        self.loop = None

    def __running_app__(self):
        """
        This is the thread that starts the new IO loop
        """
        self.log.debug("In thread: creating and starting new asyncio loop")
        self.loop = asyncio.new_event_loop()
        self.loop.thread_controller = self
        asyncio.set_event_loop(self.loop)
        self.main_task = self.loop.create_task(self.coro)
        try:
            self.loop.run_forever()
        except:
            self.log.error("asyncio loop stopped running", exc_info=True)
            pass

    async def __stop_main_task__(self):
        """
        Coroutine that cancels the main tasks and awaits it
        """
        self.log.debug("Cancelling the main task")
        if self.main_task is None:
            return

        if self.loop is None:
            return

        self.main_task.cancel()

        try:
            await self.main_task
        except asyncio.CancelledError:
            # expected, task was cancelled
            pass
        except:
            self.log.error("Unable to cancel main task", exc_info=True)
        finally:
            self.loop.stop()
