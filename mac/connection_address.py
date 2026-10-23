"""Resolve a user-supplied viewer address without contacting any server."""
import re
from urllib.parse import urlsplit


def viewer_address(value):
    value=value.strip()
    if any(ord(char)<32 or ord(char)==127 for char in value):
        raise ValueError('Paste just the viewer or Codespace editor address.')
    parsed=urlsplit(value)
    local=parsed.hostname in ('localhost','127.0.0.1','::1')
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Enter an https:// viewer or Codespace editor address.')
    if parsed.scheme=='http' and not local:
        raise ValueError('Remote connections require HTTPS.')
    port=parsed.port  # Reject malformed ports before prompting for a private key.
    if parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Use the address without extra paths or parameters.')
    name=parsed.hostname.removesuffix('.github.dev')
    if parsed.hostname.endswith('.github.dev') and '.' not in name:
        if port is not None or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',name):
            raise ValueError('Use the public port 3000 viewer address from Codespaces.')
        return f'https://{name}-3000.app.github.dev'
    if parsed.hostname in ('github.com','www.github.com','github.dev'):
        raise ValueError('Open your Codespace and copy its editor address or the public port 3000 address, not the GitHub repository page.')
    hostname=f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
    return f'{parsed.scheme}://{hostname}'+(f':{port}' if port is not None else '')


def websocket_url(value):
    address=viewer_address(value)
    return ('wss'+address[5:] if address.startswith('https:') else 'ws'+address[4:])+'/ws'
