"""Foreground reconnect supervision; no capture or polling while disconnected."""
import asyncio
import ssl
import time
from websockets.exceptions import InvalidMessage

class ConnectionProblem(RuntimeError):
    def __init__(self,message,retryable=True):
        super().__init__(message)
        self.retryable=retryable

async def keep_connected(factory,url,key,log=print,sleep=asyncio.sleep,clock=time.monotonic):
    delay=2
    while True:
        started=clock()
        try:
            await factory().run(url,key)
        except ConnectionProblem as error:
            if not error.retryable:raise
            log(str(error))
        except ssl.SSLCertVerificationError:
            raise  # Do not repeatedly retry a certificate failure.
        except (OSError,TimeoutError,InvalidMessage) as error:
            log(f'Connection unavailable ({type(error).__name__}).')
        if clock()-started>=60:delay=2
        log(f'Reconnecting in {delay} seconds. Keep this window open; Ctrl+C stops access.')
        await sleep(delay)
        delay=min(60,delay*2)
