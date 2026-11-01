"""Run: python -m unittest discover -s application-backend-server -p 'test_*.py'."""
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import app as backend


class StudentViews(unittest.TestCase):
    def setUp(self):
        backend.app.testing = True
        self.client = backend.app.test_client()
        self.browser = {"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}

    def test_json_contract_and_negotiation(self):
        original = self.client.get('/student').json
        for accept in ('', '*/*', 'application/json', 'text/html;q=0.5,application/json',
                       'text/html,application/json'):
            with self.subTest(accept=accept):
                result = self.client.get('/student', headers={'Accept': accept})
                self.assertEqual(result.json, original)
                self.assertIn('Accept', result.vary)
        self.assertEqual(self.client.get('/student?format=json', headers=self.browser).json, original)

    def test_student_html(self):
        result = self.client.get('/student', headers=self.browser)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.mimetype, 'text/html')
        html = result.get_data(as_text=True)
        self.assertIn('Danh sách <em>sinh viên.</em>', html)
        for row in self.client.get('/student').json:
            self.assertIn(row['name'], html)
            self.assertIn('%.2f' % row['gpa'], html)

    def database(self, rows):
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = rows
        return patch.object(backend.pymysql, 'connect', return_value=connection)

    def test_database_html_dates_nulls_and_escaping(self):
        rows = [dict(id=1, student_id='SV001', fullname='<script>alert(1)</script>',
                     dob=date(2004, 5, 12), major='CNTT'),
                dict(id=2, student_id=None, fullname=None, dob=None, major=None)]
        with self.database(rows):
            response = self.client.get('/students-db', headers=self.browser)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('12/05/2004', html)
        self.assertIn('—', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)

    def test_database_json_and_empty_html(self):
        with self.database([dict(id=1, student_id='SV001', fullname='An', dob=date(2004, 5, 12), major='CNTT')]):
            response = self.client.get('/students-db')
        self.assertEqual(response.json[0]['dob'], '2004-05-12')
        with self.database([]):
            response = self.client.get('/students-db', headers=self.browser)
        self.assertIn('Chưa có sinh viên', response.get_data(as_text=True))

    def test_errors_keep_http_status_and_json(self):
        cases = [('/student', 500, 'Student data unavailable',
                  patch.object(backend, 'STUDENTS_FILE', Path('nonexistent-student-test.json'))),
                 ('/students-db', 503, 'Database unavailable',
                  patch.object(backend.pymysql, 'connect', side_effect=backend.pymysql.OperationalError('SECRET')))]
        for route, status, message, mock in cases:
            with self.subTest(route=route), mock:
                html = self.client.get(route, headers=self.browser)
                raw = self.client.get(route)
                self.assertEqual(html.status_code, status)
                self.assertIn('Chưa thể tải dữ liệu', html.get_data(as_text=True))
                self.assertNotIn('SECRET', html.get_data(as_text=True))
                self.assertEqual(raw.status_code, status)
                self.assertEqual(raw.json, {'error': message})


if __name__ == '__main__':
    unittest.main()
