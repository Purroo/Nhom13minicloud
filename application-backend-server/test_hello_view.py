"""Check browser negotiation without breaking API consumers or health checks."""
import unittest
from unittest.mock import patch

import app as backend


class HelloView(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()

    def test_json_default_and_explicit_preferences(self):
        for accept in ('', '*/*', 'application/json', 'text/html,application/json',
                       'text/html;q=0.5,application/json;q=0.9'):
            with self.subTest(accept=accept):
                response = self.client.get('/hello', headers={'Accept': accept})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {'message': 'Hello from App Server!'})
                self.assertIn('Accept', response.vary)

    def test_browser_html_and_json_override(self):
        headers = {'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}
        response = self.client.get('/hello', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/html')
        self.assertIn('Hello from App Server!', response.get_data(as_text=True))
        self.assertIn('Accept', response.vary)
        raw = self.client.get('/hello?format=json', headers=headers)
        self.assertEqual(raw.json, {'message': 'Hello from App Server!'})

    def test_hello_does_not_require_database_or_identity_provider(self):
        with patch.object(backend.pymysql, 'connect', side_effect=AssertionError), \
             patch.object(backend.requests, 'get', side_effect=AssertionError):
            for accept in ('application/json', 'text/html'):
                self.assertEqual(self.client.get('/hello', headers={'Accept': accept}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
