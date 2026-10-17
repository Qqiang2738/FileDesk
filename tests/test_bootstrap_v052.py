"""Guard the frontend boot contract after 0.5.0's null addEventListener crash."""
from pathlib import Path
from html.parser import HTMLParser
import socket
import unittest

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
JS = (ROOT / 'web/app.js').read_text(encoding='utf-8')


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id':
                self.ids.add(value)


class BootstrapContract(unittest.TestCase):
    def test_javascript_references_exist_in_html(self):
        import re
        parser = IdParser()
        parser.feed(HTML)
        block = JS.split('const refs = Object.fromEntries([', 1)[1].split('].map(id =>', 1)[0]
        ids = re.findall(r"'([\w-]+)'", block)
        self.assertGreater(len(ids), 30)
        self.assertEqual(len(ids), len(set(ids)), 'duplicate JS ref IDs')
        self.assertEqual([], sorted(set(ids) - parser.ids), 'JS refs missing from HTML')

    def test_build_pinned_resources_and_deferred_script(self):
        self.assertIn('name="filedesk-build" content="1.0.0"', HTML)
        self.assertIn('styles.css?v=1.0.0', HTML)
        self.assertIn('<script defer src="/assets/app.js?v=1.0.0"></script>', HTML)
        self.assertIn("const BUILD = '1.0.0'", JS)
        self.assertIn("document.addEventListener('DOMContentLoaded', init", JS)

    def test_http_never_caches_html_or_assets(self):
        from filedesk.server import app
        with TestClient(app) as client:
            for url in ('/', '/assets/app.js?v=1.0.0', '/assets/styles.css?v=1.0.0'):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, url)
                self.assertIn('no-store', response.headers.get('cache-control', ''), url)
            self.assertEqual(client.get('/api/health').json()['version'], '1.0.0')

    def test_busy_port_chooses_another(self):
        from main import pick_available_port
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            busy_port = listener.getsockname()[1]
            self.assertNotEqual(pick_available_port(busy_port), busy_port)


if __name__ == '__main__':
    unittest.main()
