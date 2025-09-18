import unittest
from qt_main import APP_NAME, get_default_download_dir

class TestQtMain(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(APP_NAME, "YouTube Downloader")

    def test_default_download_dir(self):
        path = get_default_download_dir()
        self.assertTrue(isinstance(path, str))
        self.assertTrue(len(path) > 0)

if __name__ == "__main__":
    unittest.main()
