import unittest
from qt_main import get_default_download_dir, CookieCollector, MainWindow, DownloadWorker, FfmpegConvertWorker, APP_NAME, DEFAULT_DOWNLOAD_DIR
import os
import tempfile
from PyQt5.QtWidgets import QApplication

class TestQtMainFull(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])

    def test_app_name_and_dir(self):
        self.assertEqual(APP_NAME, "YouTube Downloader")
        self.assertTrue(os.path.isdir(DEFAULT_DOWNLOAD_DIR))

    def test_get_default_download_dir(self):
        path = get_default_download_dir()
        self.assertTrue(isinstance(path, str))
        self.assertTrue(len(path) > 0)

    def test_cookie_collector_paths(self):
        cc = CookieCollector()
        self.assertIsInstance(cc.browser_paths, dict)

    def test_cookie_collection(self):
        cc = CookieCollector()
        count = cc.collect_all_cookies()
        self.assertIsInstance(count, int)
        # Should not raise, but may be zero if no cookies found

    def test_mainwindow_settings(self):
        mw = MainWindow()
        mw.settings.setValue('test_key', 'test_value')
        self.assertEqual(mw.settings.value('test_key'), 'test_value')

    def test_downloadworker_init(self):
        dw = DownloadWorker(
            url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            mode='Video',
            selected_indices=[1],
            quality_selector='best',
            download_dir=tempfile.gettempdir(),
            cookies_path=None,
            captions_lang='en',
            use_archive=False
        )
        self.assertEqual(dw.url, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertEqual(dw.mode, 'Video')

    def test_ffmpegconvertworker_init(self):
        fcw = FfmpegConvertWorker(files=[])
        self.assertEqual(fcw.files, [])

if __name__ == "__main__":
    unittest.main()
