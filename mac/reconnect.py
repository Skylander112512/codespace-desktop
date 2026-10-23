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


async def keep_available(factory,connections,log=print,sleep=asyncio.sleep,clock=time.monotonic):
    """Try saved endpoints serially; a live host session suspends all searching."""
    from connection_address import websocket_url
    delay=2
    rejected=set()
    while True:
        entries=connections()
        for entry in entries:
            identity=(entry['url'],entry['key'])
            if identity in rejected:continue
            started=clock()
            log(f"Checking saved Codespace: {entry['url']}")
            try:
                # run owns and closes its resources before another is created.
                # It returns only on disconnect: no other endpoint is polled
                # while this one is connected, including while waiting for a viewer.
                await factory(entry).run(websocket_url(entry['url']),entry['key'])
            except ConnectionProblem as error:
                if not error.retryable:
                    rejected.add(identity)
                    log('This saved Codespace rejected its host key. Update it with Add Codespace.command; trying the other saved connections.')
                else:log(str(error))
            except ssl.SSLCertVerificationError:
                rejected.add(identity)
                log('Certificate verification failed for this saved Codespace; trying the other saved connections.')
            except (OSError,TimeoutError,InvalidMessage) as error:
                log(f'Connection unavailable ({type(error).__name__}).')
            if clock()-started>=60:delay=2
        # Changes made with Add Codespace.command are picked up next round,
        # without keeping a watcher, another socket, or another capture running.
        rejected.intersection_update((entry['url'],entry['key']) for entry in entries)
        log(f'No saved Codespace connected. Checking again in {delay} seconds; Ctrl+C stops access.')
        await sleep(delay)
        delay=min(60,delay*2)
