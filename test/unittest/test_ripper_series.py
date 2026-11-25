import sys
import unittest

sys.path.insert(0, '/opt/arm')

from arm.ripper.series import season_disc, title_number  # noqa: E402


class TestSeriesLabels(unittest.TestCase):

    def test_season_disc(self):
        self.assertEqual(season_disc("NORTHERN_EXPOSURE_S1D2"), (1, 2))
        self.assertEqual(season_disc("FRIENDS_SEASON_2_DISC_3"), (2, 3))
        self.assertEqual(season_disc("show_s10_d1"), (10, 1))
        self.assertIsNone(season_disc("CRASH_DIRECTORS_CUT_D2"))
        self.assertIsNone(season_disc(None))

    def test_title_number(self):
        self.assertEqual(title_number("C1_t04.mkv"), 4)
        self.assertEqual(title_number("D1_t00.mkv"), 0)
        self.assertEqual(title_number("title.mkv"), 999)


if __name__ == '__main__':
    unittest.main()
