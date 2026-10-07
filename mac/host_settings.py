"""Private, local connection memory; never part of a public download."""
import json
import os
from pathlib import Path
import tempfile

SETTINGS=Path.home()/'Library'/'Application Support'/'Codespace Desktop'/'connection.json'

def load_settings(path=SETTINGS):
    try:
        value=json.loads(path.read_text())
        if isinstance(value,dict) and isinstance(value.get('url'),str) and isinstance(value.get('key'),str) and len(value['key'])>=32:
            return value
    except (OSError,ValueError):pass
    return None

def save_settings(url,key,path=SETTINGS):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temporary=tempfile.mkstemp(prefix='.connection-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump({'url':url,'key':key},stream)
        os.chmod(temporary,0o600)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
