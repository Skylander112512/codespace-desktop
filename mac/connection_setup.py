"""Explicit connection selection. Never writes settings or discovers servers."""
import getpass
from connection_address import viewer_address


def select_connection(saved,connections,*,setup=False,choose=False,read=None,secret=None,write=print):
    read=read or input
    secret=secret or getpass.getpass
    if choose and connections:
        write('Choose a saved Codespace. Its private key is not displayed.')
        for number,item in enumerate(connections,1):write(f"  {number}. {item['url']}")
        write('  N. Pair another Codespace\n  Q. Cancel')
        while True:
            choice=read('Choice [1]: ').strip().lower() or '1'
            if choice=='q':raise SystemExit(0)
            if choice=='n':saved=None;break
            if choice.isascii() and choice.isdigit() and 1<=int(choice)<=len(connections):
                saved=connections[int(choice)-1];break
            write('Choose a number from the list, N, or Q.')
    elif setup or choose:
        saved=None
    if saved:
        write(f"Connecting to {saved['url']}\nUse Choose Codespace.command to switch, or Change Connection.command to pair or update a key.")
        return saved['url'],saved['key']
    write('Pair this Codespace once. Successful connections are remembered privately on this Mac.')
    entered=read('Codespaces viewer or editor URL: ')
    address=viewer_address(entered)
    if address!=entered.strip().rstrip('/'):write(f'Viewer address: {address}')
    key=secret('Mac host key from this Codespace (hidden): ').strip()
    if len(key)<32:raise ValueError('Use the full Mac host key printed by npm start in this Codespace, not the Chromebook code.')
    return address,key
