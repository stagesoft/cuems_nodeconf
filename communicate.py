"""Utilites to call the hardware discovery tool."""
from cuemsutils.log import logged, Logger
from cuemsutils.tools.CommunicatorServices import Communicator
import threading
import asyncio
import json

NODECONF_IPC = '/tmp/nodeconf.ipc'
TIMEOUT = 15  # seconds




@logged
def get_nodeconf_comm():
    """
    Call the node configuration tool
    """
    return Communicator(NODECONF_IPC)



    

class AsyncCommsThread(threading.Thread):
    def __init__(self, command_callback: callable):
        Logger.debug('Initializing communications thread')
        self.command_callback = command_callback
        self.timeout = TIMEOUT * 1000
        self.stop_requested = False
        self.send_contexts= []
        threading.Thread.__init__(self, name='Communications', daemon=True)
        self.nodeconf = get_nodeconf_comm()
        
        
 

    def run(self):
        Logger.debug('Comms thread run called')
        self.event_loop = asyncio.new_event_loop()
        self.event_loop.create_task(self.run_asyncio_comms())
        self.event_loop.run_forever()
    def stop(self):
        stop_requested = True
        asyncio.run_coroutine_threadsafe(self.stop_async(), self.event_loop)
    
    async def stop_async(self):
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        Logger.info('event loop stoped')
                

    async def run_asyncio_comms(self):
        Logger.info('Starting asyncio communications')
        engine_task = asyncio.create_task(self.engine_listener())
        await engine_task

        Logger.debug('asyncio comms finished')
        #
    async def engine_listener(self):
        Logger.info('engine listener started')
        await self.nodeconf.responder_connect()
        while not self.stop_requested:
            Logger.debug(f'waiting for engine message')
            await self.nodeconf.responder_get_request(self.command_callback)

    async def respond_to_engine(self, message, context):
        Logger.debug(f'Sending to editengine: {message}, with context ')
        await context.asend(json.dumps(message).encode())           

