"""Private, local connection memory; never part of a public download."""
import json
import os
from pathlib import Path
import tempfile
from connection_address import viewer_address

SETTINGS=Path.home()/'Library'/'Application Support'/'Codespace Desktop'/'connection.json'

def _connection(value):
    if not isinstance(value,dict) or not isinstance(value.get('url'),str) or not isinstance(value.get('key'),str) or len(value['key'])<32:
        return None
    try:return {'url':viewer_address(value['url']),'key':value['key']}
    except ValueError:return None


def _read(path):
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def load_settings(path=SETTINGS):
    return _connection(_read(path))


def load_connections(path=SETTINGS):
    value=_read(path)
    candidates=value.get('connections',[])
    if not isinstance(candidates,list):candidates=[]
    result=[];seen=set()
    # The legacy top-level connection remains first and works with older hosts.
    for candidate in [value,*candidates]:
        entry=_connection(candidate)
        if entry and entry['url'] not in seen:
            result.append(entry);seen.add(entry['url'])
    return result


def _write(value,path):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temporary=tempfile.mkstemp(prefix='.connection-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream)
        os.chmod(temporary,0o600)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def _valid(url,key):
    current=_connection({'url':url,'key':key})
    if current is None:raise ValueError('A valid viewer URL and full host key are required.')
    return current


def save_settings(url,key,path=SETTINGS):
    current=_valid(url,key)
    connections=[current]+[item for item in load_connections(path) if item['url']!=current['url']]
    _write({**current,'connections':connections},path)


def save_backup(url,key,path=SETTINGS):
    """Explicitly save an untested alternative without changing the active pair."""
    backup=_valid(url,key)
    active=load_settings(path)
    # Updating the active address also updates its key, rather than preserving
    # a stale top-level key that would shadow the corrected list entry.
    if active and active['url']==backup['url']:active=backup
    entries=[item for item in load_connections(path) if item['url']!=backup['url']]+[backup]
    _write({**(active or {}),'connections':entries},path)
