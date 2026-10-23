"""Fork pairing tests use synthetic keys and temporary files only."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from connection_address import viewer_address,websocket_url
from connection_setup import select_connection
from host_settings import load_settings,load_connections,save_settings

A='https://first-fork-123-3000.app.github.dev'
B='https://second-account-456-3000.app.github.dev'
KEY_A='synthetic-a-'+'a'*32
KEY_B='synthetic-b-'+'b'*32

class AddressTests(unittest.TestCase):
    def test_editor_links_resolve_without_an_account_or_repository_name(self):
        for name in ('first-fork-123','second-account-456'):
            self.assertEqual(viewer_address(f'https://{name}.github.dev/'),f'https://{name}-3000.app.github.dev')
            self.assertEqual(websocket_url(f'https://{name}.github.dev'),f'wss://{name}-3000.app.github.dev/ws')
    def test_viewer_custom_ports_and_non_codespaces_hosts_remain_supported(self):
        for address in (A,B,'https://fork-4000.app.github.dev','https://desktop.example:444'):
            self.assertEqual(viewer_address(address+'/'),address)
        self.assertEqual(websocket_url('http://localhost:3000'),'ws://localhost:3000/ws')
        self.assertEqual(websocket_url('http://[::1]:3000'),'ws://[::1]:3000/ws')
    def test_unsafe_or_wrong_links_are_rejected_before_key_entry(self):
        for value in ('http://remote.example','https://name:secret@example.com','https://example.com/path',
                      'https://example.com/?key=secret','https://example.com/#key',
                      'https://github.com/codespaces','https://github.dev',
                      'https://example.com:bad','https://example.com:99999','https://exa\nmple.com'):
            secret=Mock()
            with self.subTest(value=value),self.assertRaises(ValueError):
                select_connection(None,[],read=lambda _:value,secret=secret,write=lambda _:None)
            secret.assert_not_called()

class StoredConnectionsTests(unittest.TestCase):
    def test_legacy_connection_migrates_and_keys_stay_with_their_servers(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json'
            path.write_text(json.dumps({'url':A,'key':KEY_A}))
            self.assertEqual(load_connections(path),[{'url':A,'key':KEY_A}])
            save_settings(B,KEY_B,path)
            self.assertEqual(load_settings(path),{'url':B,'key':KEY_B})
            self.assertEqual(load_connections(path),[{'url':B,'key':KEY_B},{'url':A,'key':KEY_A}])
            self.assertEqual(os.stat(path).st_mode&0o777,0o600)
            raw=json.loads(path.read_text())
            self.assertEqual((raw['url'],raw['key']),(B,KEY_B),'Older hosts retain the active connection')
            save_settings('https://first-fork-123.github.dev',KEY_B,path)
            self.assertEqual(load_connections(path),[{'url':A,'key':KEY_B},{'url':B,'key':KEY_B}])
    def test_failed_atomic_save_keeps_previous_pairing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json';save_settings(A,KEY_A,path)
            before=path.read_bytes()
            with patch('host_settings.os.replace',side_effect=OSError('synthetic disk error')):
                with self.assertRaises(OSError):save_settings(B,KEY_B,path)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(folder).iterdir()),[path])
    def test_invalid_entries_do_not_hide_a_valid_saved_connection(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json'
            path.write_text(json.dumps({'connections':[None,{'url':A,'key':'short'},{'url':B,'key':KEY_B}]}))
            self.assertIsNone(load_settings(path))
            self.assertEqual(load_connections(path),[{'url':B,'key':KEY_B}])

class SelectionTests(unittest.TestCase):
    def setUp(self):self.entries=[{'url':A,'key':KEY_A},{'url':B,'key':KEY_B}]
    def test_ordinary_launch_keeps_current_connection_without_prompting(self):
        read=Mock();secret=Mock()
        self.assertEqual(select_connection(self.entries[0],self.entries,read=read,secret=secret,write=lambda _:None),(A,KEY_A))
        read.assert_not_called();secret.assert_not_called()
    def test_chooser_switches_without_printing_or_prompting_for_keys(self):
        outputs=[];secret=Mock();answers=iter(['wrong','9','2'])
        result=select_connection(self.entries[0],self.entries,choose=True,read=lambda _:next(answers),secret=secret,write=outputs.append)
        self.assertEqual(result,(B,KEY_B));secret.assert_not_called()
        self.assertNotIn(KEY_A,'\n'.join(outputs));self.assertNotIn(KEY_B,'\n'.join(outputs))
    def test_new_pair_and_explicit_key_update_prompt_without_mutating_entries(self):
        for options,answers in (({'choose':True},['n','https://second-account-456.github.dev']),({'setup':True},[B])):
            inputs=iter(answers)
            result=select_connection(self.entries[0],self.entries,read=lambda _:next(inputs),secret=lambda _:KEY_B,write=lambda _:None,**options)
            self.assertEqual(result,(B,KEY_B))
            self.assertEqual(self.entries[0],{'url':A,'key':KEY_A})
    def test_cancel_does_not_prompt_for_a_key(self):
        secret=Mock()
        with self.assertRaises(SystemExit) as stopped:
            select_connection(self.entries[0],self.entries,choose=True,read=lambda _:'q',secret=secret,write=lambda _:None)
        self.assertEqual(stopped.exception.code,0);secret.assert_not_called()

if __name__=='__main__':unittest.main()
