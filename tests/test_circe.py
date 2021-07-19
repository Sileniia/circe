import json
import os
import pathlib
import platform
import shutil
import unittest

import circe

LOREM_IPSUM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore"
    "magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo"
    "consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."
    "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
)


class TestImport(unittest.TestCase):
    def test_version(self):
        self.assertEqual(circe.__version__, "0.1.0")

    def test_helpers_package_data(self):
        data_dir = circe.helpers.package_data()
        self.assertEqual(data_dir.name, "data")
        self.assertEqual(data_dir.parent.name, "circe")


class TestHelpersDirectories(unittest.TestCase):
    def test_dir_user_data(self):
        o = platform.system()
        if o == "Windows":
            self.assertEqual(circe.helpers.dir_user_data, pathlib.Path(f"C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data"))
        elif o == "Darwin":
            self.assertEqual(circe.helpers.dir_user_data, pathlib.Path(f"/Users/{os.getlogin()}/Library/Application Support/Google/Chrome/"))
        else:  # elif o == "Linux":
            self.assertEqual(circe.helpers.dir_user_data, pathlib.Path(f"/home/{os.getlogin()}/.config/google-chrome"))

    def test_downloads(self):
        o = platform.system()
        if o == "Windows":
            self.assertEqual(circe.helpers.dir_downloads, pathlib.Path(f"C:\\Users\\{os.getlogin()}\\Downloads"))
        elif o == "Darwin":
            self.assertEqual(circe.helpers.dir_downloads, pathlib.Path(f"/Users/{os.getlogin()}/Downloads"))
        else:  # elif o == "Linux":
            self.assertEqual(circe.helpers.dir_downloads, pathlib.Path(f"/home/{os.getlogin()}/Downloads"))


class TestHelpersProfiles(unittest.TestCase):
    def test_get_profiles(self):
        profile_1 = pathlib.Path("circe_temp", "Default")
        profile_2 = pathlib.Path("circe_temp", "Profile 1")
        os.makedirs(profile_1)
        os.makedirs(profile_2)
        self.assertEqual(circe.helpers.get_profiles("temp"), ["Default", "Profile 1"])
        shutil.rmtree("circe_temp")


class TestHelpersSearchStrings(unittest.TestCase):
    def test_rogue_search(self):
        self.assertEqual(circe.helpers.rogue_search("pancakes", "cGFuY2FrZXM="), circe.helpers.U_GOOGLE.format(q="pancakes", gs_lcp="cGFuY2FrZXM=", cc=0))


class TestHelpersTime(unittest.TestCase):
    def test_time_from_chrome(self):
        self.assertEqual(circe.helpers.time_from_chrome(13271165585000000), 1626691985)

    # def test_time_now_chrome(self):
    #     ...

    def test_time_to_chrome(self):
        self.assertEqual(circe.helpers.time_to_chrome(1626691985), 13271165585000000)


class TestHelpersGenerators(unittest.TestCase):
    def test_yield_chunk_randrage(self):
        chunks = set([len(c) for c in circe.helpers.yield_chunk_randrange(LOREM_IPSUM, 1, 20)])
        self.assertGreater(len(chunks), 2)  # A sufficiently-long passage should yield at least two chunk sizes

    def test_yield_chunk_jitter(self):
        chunks = set([len(c) for c in circe.helpers.yield_chunk_jitter(LOREM_IPSUM, 10, 0.5)])
        self.assertGreater(len(chunks), 2)

    def test_yield_infinite_random(self):
        sample = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        iterator = circe.helpers.yield_infinite_random(sample)

        test1 = []
        for _ in range(len(sample)):
            test1.append(next(iterator))

        test2 = []
        for _ in range(len(sample)):
            test1.append(next(iterator))

        self.assertNotEqual(test1, sample)
        self.assertNotEqual(test2, sample)


class TestCoreProfile(unittest.TestCase):
    def setUp(self):
        self.default_path = circe.helpers.dir_user_data().joinpath("Default")
        self.profile1_path = circe.helpers.dir_user_data().joinpath("Profile 1")

        self.temp_default_path = pathlib.Path("circe_temp", "Default")
        self.profile2_path = pathlib.Path("circe_temp", "Profile 2").absolute()
        self.profile3_path = str(pathlib.Path("circe_temp", "Profile 3").absolute())
        os.makedirs(self.temp_default_path)
        os.makedirs(self.profile2_path)
        os.makedirs(self.profile3_path)

        with open(self.temp_default_path.joinpath("Preferences"), "w") as f:
            json.dump({}, f)

        self.default = circe.Profile()
        self.profile0 = circe.Profile(0)
        self.profile1 = circe.Profile(1)
        self.profile2 = circe.Profile(self.profile2_path)  # string
        self.profile3 = circe.Profile(self.profile3_path)  # path-like object

    def tearDown(self):
        shutil.rmtree("circe_temp")

    def test_core_profile_dunder_init(self):
        self.assertEqual(self.default._cid, 0)
        self.assertEqual(self.default.bookmarks, {})
        self.assertEqual(self.default.preferences, {})

        self.assertEqual(self.default.path, self.default_path)
        self.assertEqual(self.profile0.path, self.default_path)
        self.assertEqual(self.profile1.path, self.profile1_path)
        self.assertEqual(self.profile2.path, self.profile2_path)
        self.assertEqual(self.profile3.path, pathlib.Path(self.profile3_path))

    def test_core_profile_dunder_repr(self):
        self.assertEqual(repr(self.default), f"Profile({self.default_path})")
        self.assertEqual(repr(self.profile0), f"Profile({self.default_path})")
        self.assertEqual(repr(self.profile1), f"Profile({self.profile1_path})")

    # Mostly redundant -- we've already tested the individual components individually
    # def test_core_profile_dunder_str(self):
    #     ...

    def test_core_profile_dunder_enter(self):
        bookmarks_path = pathlib.Path("circe_temp", "Default", "Bookmarks")
        with open(bookmarks_path, "w") as f:
            json.dump(circe.helpers.SKELETON, f)

        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            self.assertEqual(p.bookmarks, circe.helpers.SKELETON)

    def test_core_profile_dunder_exit(self):
        bookmarks_path = pathlib.Path("circe_temp", "Default", "Bookmarks")
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            pass
        self.assertTrue(bookmarks_path.exists())

    # Implicitly tested by test_core_profile_get
    # def test_core_profile__decode(self):
    #     ...

    def test_core_profile__derive_min_max(self):
        min_len, max_len = self.default._derive_min_max(min_len=1636, avg_len=1818)
        self.assertEqual((min_len, max_len), (1636, 2000))

        min_len, max_len = self.default._derive_min_max(min_len=1636, max_len=2000)
        self.assertEqual((min_len, max_len), (1636, 2000))

        min_len, max_len = self.default._derive_min_max(min_len=1636, jitter=0.1)
        self.assertEqual((min_len, max_len), (1636, 2000))

        min_len, max_len = self.default._derive_min_max(avg_len=1818, max_len=2000)
        self.assertEqual((min_len, max_len), (1636, 2000))

        min_len, max_len = self.default._derive_min_max(avg_len=1818, jitter=0.1)
        self.assertEqual((min_len, max_len), (1636, 2000))

        min_len, max_len = self.default._derive_min_max(max_len=2000, jitter=0.1)
        self.assertEqual((min_len, max_len), (1636, 2000))

    # implicitly tested by test_core_profile_get
    # def test_core_profile__encode(self):
    #     ...

    def test_core_profile__get_next_cid(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            self.assertEqual(p._cid, 0)
            p.add("this is a test")
            self.assertEqual(p._cid, 1)

    def test_core_profile_add(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("this is a test")
            self.assertEqual(len(p.list()), 1)
            p.add("this is another test")
            self.assertEqual(len(p.list()), 2)

    def test_core_profile_add_file(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add_file("test.txt")
            self.assertEqual(len(p.list()), 1)
            p.add_file("test.txt")
            self.assertEqual(len(p.list()), 2)

    def test_core_profile_backup(self):
        bookmarks_path = pathlib.Path("circe_temp", "Default", "Bookmarks")
        with open(bookmarks_path, "w") as f:
            json.dump(circe.helpers.SKELETON, f)

        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.backup()
        backups_path = pathlib.Path("circe_temp", "Default", "Backups")
        self.assertTrue(backups_path, True)
        self.assertEqual(len(os.listdir(backups_path)), 1)

    def test_core_profile_count(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("test string 1")
            p.add("test string 2")
            p.add("test string 3")
            self.assertEqual(p.count()[0], 3)

    def test_core_profile_delete(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("test string 1")
            p.delete(0)
            self.assertEqual(p.count()[0], 0)

    def test_core_profile_get(self):
        initial_content = "this is a test"
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add(initial_content)
            retrieved_content = p.get(0)[1].decode()
            self.assertEqual(initial_content, retrieved_content)

    def test_core_profile_info(self):
        preferences_path = self.temp_default_path.joinpath("Preferences")
        with open(preferences_path, "w") as f:
            json.dump({"profile": {"name": "test"}}, f)

        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.load()
            p.add("test string 1")
            info = p.info()
            self.assertEqual(self.temp_default_path.absolute(), info["profile"])
            self.assertEqual(info["has_bookmarks"], False)
            self.assertEqual(info["circe_files"], 1)
            p.save()
            self.assertEqual(p.info()["has_bookmarks"], True)

    def test_core_profile_list(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("test string 1")
            p.delete(0)
            self.assertEqual(p.count()[0], 0)

    def test_core_profile_load(self):
        bookmarks_path = pathlib.Path("circe_temp", "Default", "Bookmarks")
        with open(bookmarks_path, "w") as f:
            json.dump(circe.helpers.SKELETON, f)

        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            self.assertEqual(p.bookmarks, circe.helpers.SKELETON)

    # TODO need a better test for here
    def test_core_profile_peek(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("test string please ignore")
            peek = p.peek(0)
            self.assertIn("file", peek)
            self.assertIn("title", peek)
            self.assertIn("num_data_chunks", peek)

    def test_core_profile_save(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.save()
            with open(p.path.joinpath("Bookmarks"), "r") as f:
                bookmarks1 = json.load(f)
            p.add("this is a test")
            p.save()
            with open(p.path.joinpath("Bookmarks"), "r") as f:
                bookmarks2 = json.load(f)
            self.assertNotEqual(bookmarks1, bookmarks2)

    def test_core_profile_wipe(self):
        with circe.Profile(pathlib.Path("circe_temp", "Default")) as p:
            p.add("this is a test")
            p.add("this is another test")
            p.add("this is yet another test")
            p.wipe()
            self.assertEqual(len(p.list()), 0)


if __name__ == "__main__":
    unittest.main()
