import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, '/opt/arm')

from arm.ripper.utils import film_disc, has_film, length_mismatch, older_waiting  # noqa: E402
from arm.ripper.arm_ripper import move_bonus_disc  # noqa: E402


class TestFilmDisc(unittest.TestCase):
    def test_disc_number(self):
        self.assertEqual(film_disc("CRASH_DIRECTORS_CUT_D2"), 2)
        self.assertEqual(film_disc("FILM_DISC_3"), 3)
        self.assertEqual(film_disc("FILM_DISK2"), 2)
        self.assertEqual(film_disc("The_Fighter"), 1)
        self.assertEqual(film_disc("SISU_2"), 1)
        self.assertEqual(film_disc(None), 1)

    def test_has_film(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(has_film(folder, "mkv"))
            os.mkdir(os.path.join(folder, "extras"))
            open(os.path.join(folder, "poster.png"), "w").close()
            self.assertFalse(has_film(folder, "mkv"))
            open(os.path.join(folder, "Crash (2005).mkv"), "w").close()
            self.assertTrue(has_film(folder, "mkv"))
        self.assertFalse(has_film("/nonexistent", "mkv"))


    def test_move_bonus_disc(self):
        with tempfile.TemporaryDirectory() as root:
            film, out = os.path.join(root, "Crash (2005)"), os.path.join(root, "out")
            os.mkdir(film)
            os.mkdir(out)
            open(os.path.join(film, "Crash (2005).mkv"), "w").close()
            for f in ["B1_t10.mkv", "A1_t02.mkv", "notes.txt"]:
                open(os.path.join(out, f), "w").close()
            job = SimpleNamespace(path=film, label="CRASH_DIRECTORS_CUT_D2", tracks=[],
                                  config=SimpleNamespace(EXTRAS_SUB="extras", DEST_EXT="mkv"))
            move_bonus_disc(out, job)
            self.assertEqual(sorted(os.listdir(os.path.join(film, "extras"))),
                             ["Crash (2005) - disc 2 - 1.mkv", "Crash (2005) - disc 2 - 2.mkv"])
            self.assertEqual(os.listdir(out), ["notes.txt"])
            self.assertTrue(os.path.isfile(os.path.join(film, "Crash (2005).mkv")))


    def test_second_half_of_the_film(self):
        """Spartacus (1960): disc 1 has 1 h 46 min of the film, disc 2 the rest and a 25 min extra"""
        with tempfile.TemporaryDirectory() as root:
            film, out = os.path.join(root, "Spartacus (1960)"), os.path.join(root, "out")
            os.mkdir(film)
            os.mkdir(out)
            open(os.path.join(film, "Spartacus (1960).mkv"), "w").close()
            for f in ["B1_t00.mkv", "C1_t01.mkv"]:
                open(os.path.join(out, f), "w").close()
            job = SimpleNamespace(path=film, label="SPARTACUS_DISC_2",
                                  tracks=[SimpleNamespace(filename="B1_t00.mkv", length=5500),
                                          SimpleNamespace(filename="C1_t01.mkv", length=1500)],
                                  config=SimpleNamespace(EXTRAS_SUB="extras", DEST_EXT="mkv"))
            move_bonus_disc(out, job)
            self.assertEqual(sorted(os.listdir(film)),
                             ["Spartacus (1960) - part1.mkv", "Spartacus (1960) - part2.mkv", "extras"])
            self.assertEqual(os.listdir(os.path.join(film, "extras")), ["Spartacus (1960) - disc 2 - 1.mkv"])
            self.assertEqual(os.listdir(out), [])


if __name__ == '__main__':
    unittest.main()


class TestLengthMismatch(unittest.TestCase):
    def job(self, seconds, label="ARN", video_type="movie"):
        return SimpleNamespace(tracks=[SimpleNamespace(length=600), SimpleNamespace(length=seconds)],
                               video_type=video_type, title_manual=None, label=label,
                               title="Arn - The Knight Templar", year="2007")

    def test_pal_and_cinema_length_pass(self):
        self.assertIsNone(length_mismatch(self.job(7974), runtime_min=139))  # PAL DVD of the right film
        self.assertIsNone(length_mismatch(self.job(139 * 60 + 50), runtime_min=139))  # Blu-ray, 24 fps

    def test_another_film_is_flagged(self):
        message = length_mismatch(self.job(7352), runtime_min=139)  # the sequel, 2 h 03 min
        self.assertIn("122 min", message)
        self.assertIn("139 min", message)

    def test_not_checked(self):
        self.assertIsNone(length_mismatch(self.job(7352, video_type="series"), runtime_min=139))
        self.assertIsNone(length_mismatch(self.job(7352, label="SPARTACUS_DISC_2"), runtime_min=139))


class TestOlderWaiting(unittest.TestCase):
    def test_oldest_running_job_first(self):
        import subprocess
        gone = subprocess.Popen(["true"])
        gone.wait()
        me = os.getpid()
        self.assertEqual(older_waiting(59, [(55, me), (58, me), (59, me), (60, me)]), 55)
        self.assertIsNone(older_waiting(55, [(55, me), (58, me)]))
        self.assertIsNone(older_waiting(59, [(55, gone.pid), (57, None), (59, me)]))  # crashed jobs don't block
