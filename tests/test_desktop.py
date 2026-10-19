import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from desktop import SingleInstance, run_tray, icon_image


@unittest.skipUnless(os.name=='nt','Windows desktop integration')
class DesktopTests(unittest.TestCase):
    def test_mutex_and_metadata_cleanup(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'LOCALAPPDATA':root}),patch('desktop.Path.home',return_value=Path(root)):
            first=SingleInstance()
            second=None
            try:
                self.assertTrue(first.owner)
                first.publish('http://127.0.0.1:18733','example')
                second=SingleInstance();self.assertFalse(second.owner)
                self.assertTrue(first.path.exists())
                second.close();self.assertTrue(first.path.exists())
                first.close();self.assertFalse(first.path.exists())
                third=SingleInstance();self.assertTrue(third.owner);third.close()
            finally:
                if second:second.close()
                first.close()

    def test_tray_open_and_confirmed_exit(self):
        stop=Mock()
        tray=run_tray('http://127.0.0.1:12345',stop,lambda:True)
        items=list(tray.menu.items)
        self.assertEqual(items[0].text,'Abrir Instante')
        self.assertTrue(items[0].default)
        with patch('desktop.webbrowser.open') as open_browser:
            items[0](tray)
            open_browser.assert_called_once_with('http://127.0.0.1:12345')
        with patch('desktop.confirm_shutdown',return_value=False):items[2](tray)
        stop.assert_not_called()
        with patch('desktop.confirm_shutdown',return_value=True):items[2](tray)
        stop.assert_called_once()

    def test_icon(self):
        image=icon_image();self.assertEqual(image.size,(64,64));self.assertEqual(image.mode,'RGBA')


if __name__=='__main__':unittest.main()
