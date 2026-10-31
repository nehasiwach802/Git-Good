from io import BytesIO
import unittest
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import app, MAX_IMAGE_BYTES


def png():
    stream = BytesIO()
    Image.new('RGB', (2, 3), 'red').save(stream, format='PNG')
    return stream.getvalue()


class BackendConnectionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_and_openapi(self):
        self.assertEqual(self.client.get('/health').json()['mode'], 'stub')
        schema = self.client.get('/openapi.json').json()
        self.assertIn('multipart/form-data', schema['paths']['/api/sessions']['post']['requestBody']['content'])

    def test_actual_multipart_upload(self):
        response = self.client.post('/api/sessions', data={'experiment_id':'led-circuit-001','description':'My LED is not glowing'},
                                    files={'image':('circuit.png', png(), 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['status'], 'connection_ok')
        self.assertEqual((result['image']['width'],result['image']['height']), (2,3))
        self.assertEqual(result['ml2']['diagnosis'], None)
        self.assertEqual(result['ml1']['status'], 'not_run')

    def test_missing_fields_and_json_instead_of_multipart(self):
        self.assertEqual(self.client.post('/api/sessions', json={'experiment_id':'test','description':'test'}).status_code, 422)
        response = self.client.post('/api/sessions', data={'experiment_id':'test'}, files={'image':('a.png',png(),'image/png')})
        self.assertEqual(response.status_code, 422)

    def test_bad_images_and_mismatched_content_type(self):
        for data, content in [(b'', 'image/png'),(b'not an image','image/png'),(png(),'image/jpeg'),(png(),'text/plain')]:
            response = self.client.post('/api/sessions', data={'experiment_id':'test','description':'test'}, files={'image':('a',data,content)})
            self.assertEqual(response.status_code,415)

    def test_oversize_image_and_blank_description(self):
        response = self.client.post('/api/sessions', data={'experiment_id':'test','description':'test'}, files={'image':('a.png',b'x'*(MAX_IMAGE_BYTES+1),'image/png')})
        self.assertEqual(response.status_code,413)
        response = self.client.post('/api/sessions', data={'experiment_id':'test','description':'   '}, files={'image':('a.png',png(),'image/png')})
        self.assertEqual(response.status_code,422)
