import sys
import unittest

sys.path.insert(0, '/opt/arm')

from arm.ripper.utils import clean_for_filename  # noqa: E402


class TestCleanForFilename(unittest.TestCase):
    """Folder names must match what the web UI writes and what media servers look up"""

    def test_spaces_kept(self):
        self.assertEqual(clean_for_filename("The Fighter"), "The Fighter")
        self.assertEqual(clean_for_filename("Donnie  Darko"), "Donnie Darko")

    def test_colon_becomes_dash(self):
        self.assertEqual(clean_for_filename("Sisu: Road to Revenge"), "Sisu - Road to Revenge")
        self.assertEqual(clean_for_filename("Mission: Impossible - Fallout"), "Mission - Impossible - Fallout")
        self.assertEqual(clean_for_filename("Star Wars : Episode IV"), "Star Wars - Episode IV")
        self.assertEqual(clean_for_filename("10:30"), "10-30")

    def test_other_characters(self):
        self.assertEqual(clean_for_filename("Fast & Furious"), "Fast and Furious")
        self.assertEqual(clean_for_filename("Movie [Blu-ray]"), "Movie")
        self.assertEqual(clean_for_filename("Who? Me!"), "Who Me")


if __name__ == '__main__':
    unittest.main()
