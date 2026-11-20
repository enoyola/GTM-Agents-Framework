import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from gtm_agents.demo import seed
from gtm_agents.providers import FixtureProvider
from gtm_agents.server import LocalServer
from gtm_agents.store import Store


class HttpCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.store=Store(Path(cls.temp.name)/'http.sqlite3',demo=True)
        seed(cls.store)
        cls.server=LocalServer(('127.0.0.1',0),cls.store,FixtureProvider())
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def post(self,path,data,headers=None):
        request=urllib.request.Request(self.url+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json',**(headers or {})},method='POST')
        return urllib.request.urlopen(request)

    def test_ui_and_state_are_served_without_secrets(self):
        with urllib.request.urlopen(self.url) as response:
            self.assertIn(b'GTM Agents',response.read())
            self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
        with urllib.request.urlopen(self.url+'/api/state') as response:state=json.load(response)
        self.assertTrue(state['runtime']['csrf_token'])
        self.assertNotIn('_key',state['runtime'])
        self.assertFalse(state['outbound_enabled'])

    def test_csrf_and_cross_origin_writes_rejected(self):
        for headers in [{},{'X-GTM-Token':self.server.csrf_token,'Origin':'https://other.example'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/pause',{'paused':True},headers)
            self.assertEqual(error.exception.code,403)
            error.exception.close()
        self.assertFalse(self.store.config()['paused'])

    def test_valid_local_write_and_invalid_json_shape(self):
        with self.post('/api/pause',{'paused':False},{'X-GTM-Token':self.server.csrf_token}) as response:self.assertEqual(response.status,200)
        with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/pause',[],{'X-GTM-Token':self.server.csrf_token})
        self.assertEqual(error.exception.code,400)
        error.exception.close()

    def test_host_header_and_arbitrary_files_are_rejected(self):
        request=urllib.request.Request(self.url+'/api/state',headers={'Host':'untrusted.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)
        error.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(self.url+'/../../.env')
        self.assertEqual(error.exception.code,404)
        error.exception.close()


if __name__=='__main__':unittest.main()
