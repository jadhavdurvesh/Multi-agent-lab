import unittest
from app import app # Assuming app.py is in the same directory

class FlaskAppTest(unittest.TestCase):

    def setUp(self):
        # Set up a test client
        self.app = app.test_client()
        # Propagate exceptions to the test client
        self.app.testing = True

    def test_my_string_endpoint(self):
        # Send a GET request to the /my-string endpoint
        response = self.app.get('/my-string')

        # Check if the response status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check if the response data matches the expected string
        # Flask returns bytes, so decode it
        self.assertEqual(response.data.decode('utf-8'), "Hello from Flask!")

if __name__ == '__main__':
    unittest.main()
