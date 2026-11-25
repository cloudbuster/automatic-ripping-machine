import sys
import unittest

sys.path.insert(0, '/opt/arm')

from arm.ripper.utils import find_play_all  # noqa: E402


class TestFindPlayAll(unittest.TestCase):
    """Lengths from real series DVDs (Northern Exposure, seasons 1 and 2)"""

    def test_episodes_only(self):
        disc = {"t00.mkv": 2876, "t01.mkv": 2867, "t02.mkv": 2877, "t03.mkv": 2881, "t04.mkv": 11503}
        self.assertEqual(find_play_all(disc), ("t04.mkv", {"t00.mkv", "t01.mkv", "t02.mkv", "t03.mkv"}))

    def test_episodes_and_extras(self):
        disc = {"t00.mkv": 2810, "t01.mkv": 2826, "t02.mkv": 2765, "t03.mkv": 8400, "t04.mkv": 2096, "t05.mkv": 1815}
        self.assertEqual(find_play_all(disc), ("t03.mkv", {"t00.mkv", "t01.mkv", "t02.mkv"}))

    def test_no_play_all(self):
        self.assertIsNone(find_play_all({"t00.mkv": 2876, "t01.mkv": 2867, "t02.mkv": 2877, "t03.mkv": 2881}))
        self.assertIsNone(find_play_all({"t00.mkv": 6615, "t01.mkv": 1693}))
        self.assertIsNone(find_play_all({}))


if __name__ == '__main__':
    unittest.main()
