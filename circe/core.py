""" This module contains the Profile class used by the package to interact with a Chrome Bookmarks file. """

from __future__ import annotations

import base64
import gzip
import io
import json
import os
import pathlib
import random
import shutil
import traceback
import urllib.parse

from typing import Dict, Iterator, List, Tuple, Union

from . import helpers


class Profile:
    """ A programmatic interface with a Google Chrome Profile and its underlying files.
    By default, a new object will use the "Default" profile from Chrome's OS-dependent install location.

    Class Attributes:
        _random_title (iter(str)): Iterator of one million random Wikipedia titles to use for fake Bookmark names

    Instance Attributes:
        _cid (int): Circe ID - identifier used to tag individual files and corresponding bookmarks for reassembly
        path (pathlib.Path): Filepath or alias (0 -> Default, 1 -> Profile 1, ...) to a Google Chrome profile directory
        bookmarks (dict): In-memory copy of the Bookmarks file (including any changes that were made)
        preferences (dict): In-memory copy of the Preferences file
    """
    # Read in a list of one million Wikipedia article titles to use as a source for authentic-looking bookmark names.
    # This iterator is shared across all Profile objects (as re-sorting something that's already random isn't valuable)
    with open(pathlib.Path(__file__).parent.joinpath("data", "articles.txt"), "r", encoding="utf-8") as f:
        _random_title: Iterator[str] = helpers.yield_infinite_random([name.strip("\n") for name in f])

    def __init__(self, path: Union[int, str, os.PathLike] = None) -> None:
        self._cid: int = 0
        self.bookmarks: Dict = {}
        self.preferences: Dict = {}

        if path is None or path == 0:
            self.path: pathlib.Path = helpers.dir_user_data().joinpath("Default")
        elif isinstance(path, int):
            self.path: pathlib.Path = helpers.dir_user_data().joinpath(f"Profile {path}")
        elif isinstance(path, (str, os.PathLike)):
            self.path: pathlib.Path = pathlib.Path(path).absolute()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.path})"

    def __str__(self) -> str:
        return str(self.__dict__)

    # https://stackoverflow.com/questions/33533148/how-do-i-type-hint-a-method-with-the-type-of-the-enclosing-class
    def __enter__(self) -> Profile:
        self.load()
        return self

    # https://docs.quantifiedcode.com/python-anti-patterns/correctness/exit_must_accept_three_arguments.html
    def __exit__(self, exception_type, exception_value, tb) -> None:
        if exception_type is not None:
            traceback.print_exception(exception_type, exception_value, tb)
            exit(1)
        self.save()

    @staticmethod
    def _decode(bookmarks: List[Dict]) -> bytes:
        """ Combines, decodes, and decompresses data from a list of randomly-ordered bookmark dictionaries. """
        buffer = []
        for entry in sorted(bookmarks, key=lambda b: int(b["url"].rsplit("&cc=", maxsplit=1)[-1])):
            b64_chunk = urllib.parse.parse_qs(entry["url"])["gs_lcp"][0].replace(" ", "+").encode()
            buffer.append(b64_chunk)
        return gzip.decompress(base64.b64decode(b"".join(buffer)))

    @staticmethod
    def _derive_min_max(min_len: int = None, avg_len: int = None, max_len: int = None, jitter: float = None) -> Tuple[int, int]:
        """ Calculates the [min_len, max_len] tuple based on any combination of min_len, max_len, avg_len, or jitter.
        This method will fallback to the suggested MIN_LEN and MAX_LEN values to avoid returning (None, None)
        """
        if min_len:
            if max_len:
                pass
            elif avg_len:
                max_len = avg_len + (avg_len - min_len)
            elif jitter:
                max_len = 2 * round(min_len / (1 - jitter)) - min_len
        elif avg_len:
            if jitter:
                difference = round(avg_len * jitter)
                min_len = avg_len - difference
                max_len = avg_len + difference
            elif max_len:
                min_len = avg_len - (max_len - avg_len)
        elif max_len and jitter:
            min_len = 2 * round(max_len / (1 + jitter)) - max_len
        else:
            min_len = helpers.MIN_LEN
            max_len = helpers.MAX_LEN

        return min_len, max_len

    def _encode(self, data: bytes, min_len: int, max_len: int) -> List[Dict]:
        """ Compresses, encodes, and chunks binary data into a list of randomly-ordered bookmark dictionaries. """

        self._compressed = gzip.compress(data)
        self.compressed_then_encoded = base64.b64encode(self._compressed)

        evilmarks = []
        obf_data = base64.b64encode(gzip.compress(data)).decode()

        self.chunks = [chunk for chunk in helpers.yield_chunk_randrange(obf_data, min_len, max_len)]

        for i, b64_chunk in enumerate(self.chunks):
            fake_search = next(self._random_title)
            evilmarks.append({
                "date_added": helpers.time_now_chrome(),
                "guid": "",
                "id": "",
                "name": fake_search,
                "type": "url",
                "url": helpers.rogue_search(urllib.parse.quote_plus(fake_search), b64_chunk, i)
            })

        random.shuffle(evilmarks)
        return evilmarks

    def _get_next_cid(self) -> int:
        """ Returns the current cid, then increments it. """
        self._cid += 1
        return self._cid - 1

    def add(self, data: Union[str, bytes], name: str = None, **kwargs) -> None:
        """ Adds string or bytes data to the Bookmarks file.

        Args:
            data (str, bytes): String or Bytes data to add to Bookmarks
            name (str): Name / identifier for the encapsulating bookmarks folder that will contain our URLs

            Optionally, any two of:
                min_len (int): The minimum desired length for a data chunk
                avg_len (int): The average desired length for a data chunk
                max_len (int): The maximum desired length for a data chunk
                jitter (float): Desired variance in the average length of a data chunk (expressed as a percentage)

            If two of the four optional keyword arguments are *not* supplied, then the suggested values for min_len
            (1636) and max_len (2000) will be used.
        """
        if isinstance(data, str):
            data = data.encode()
        if name is None:
            name = next(self._random_title)

        min_len, max_len = self._derive_min_max(**kwargs)
        bookmarks = self._encode(data, min_len, max_len)

        cid = self._get_next_cid()
        folder = {
            "children": bookmarks,
            "cid": f"{cid}/{base64.b64encode(name.encode()).decode()}",
            "date_added": helpers.time_now_chrome(),
            "date_modified": "0",
            "guid": "",
            "id": "",
            "name": next(self._random_title),
            "type": "folder"
        }

        # Add the new bookmarks to the "Other" category, which will not show up in the Bookmarks Toolbar by default.
        self.bookmarks["roots"]["other"]["children"].append(folder)

    def add_file(self, file: Union[str, os.PathLike, io.IOBase], name: str = None, **kwargs) -> None:
        """ Adds data from a file, filepath, or file-like object to Bookmarks.

        Args:
            file (str, os.PathLike, io.IOBase): A filename in a local directory, a path-like object pointing to a
                file on disk, or an in-memory file object in either text or binary mode.
            name (str): An optional filename to label the data

            Optionally, any two of:
                min_len (int): The minimum desired length for a data chunk
                avg_len (int): The average desired length for a data chunk
                max_len (int): The maximum desired length for a data chunk
                jitter (float): Desired variance in the average length of a data chunk (expressed as a percentage)

            If two of the four optional keyword arguments are *not* supplied, then the suggested values for min_len
            (1636) and max_len (2000) will be used.
        """
        if isinstance(file, (str, os.PathLike)):
            with open(file, "rb") as f:
                stream = f.read()
                name = f.name
        elif isinstance(file, io.TextIOBase):  # io.StringIO, io.TextIOWrapper
            stream = file.read().encode()
        else:  # io.BytesIO, io.BufferedReader
            stream = file.read()

        if name is None:  # If we don't specify a name and the file-like object has one available, use that
            if hasattr(file, "name"):
                name = file.name

        return self.add(stream, name, **kwargs)

    def backup(self) -> None:
        """ Saves a copy of Bookmarks to the custom Backups directory. """
        backup_dir = self.path.joinpath("Backups")
        if not backup_dir.exists():
            os.mkdir(backup_dir)
        file = backup_dir.joinpath(f"{helpers.time_now_chrome()}.bak")
        shutil.copy2(self.path.joinpath("Bookmarks"), file)

    def count(self) -> Tuple[int, int]:
        """ Returns the total number of Circe-encoded files and data chunks currently in the Bookmarks file. """
        files, bookmarks = 0, 0
        for folder in self.bookmarks["roots"]["other"]["children"]:
            if "cid" in folder:
                files += 1
                bookmarks += len(folder["children"])
        return files, bookmarks

    def delete(self, cid: int) -> bool:
        """ Deletes the folder with the specified CID and all of the URLs it contains from the Bookmarks file.

        Args:
            cid (int): The integer prefix of the CID of interest.

        Returns:
            bool: True if the specified prefix / corresponding CID is present in Bookmarks and False otherwise.
        """
        for i, folder in enumerate(self.bookmarks["roots"]["other"]["children"]):
            if "cid" in folder:
                identifier = folder["cid"].split("/", maxsplit=1)[0]
                if int(identifier) == cid:
                    del self.bookmarks["roots"]["other"]["children"][i]
                    return True
        return False

    def get(self, cid: int) -> Union[Tuple[str, bytes], Tuple[None, None]]:
        """ Retrieves the specified Circe-encoded file from Bookmarks.

        Args:
            cid (int): The integer prefix of the CID of interest.

        Returns:
            (str, bytes): If the specified prefix / corresponding CID is present in Bookmarks, (None, None) otherwise
        """
        for folder in self.bookmarks["roots"]["other"]["children"]:
            if "cid" in folder:
                identifier, encoded_name = folder["cid"].split('/', maxsplit=1)
                if int(identifier) == cid:
                    decoded_name = base64.b64decode(encoded_name.encode()).decode()
                    data = self._decode(folder["children"])
                    return decoded_name, data
        return None, None

    def info(self) -> Dict:
        """ Returns a dictionary of information about the current Chrome profile.

            profile (pathlib.Path): absolute file path to the Chrome profile
            name (str): profile name listed in the Preferences file
            has_bookmarks (true): whether the Bookmarks file exists
            circe_files (int): number of Circe-encoded files present in Bookmarks
            circe_bookmarks (int): number of data chunks present in Bookmarks
            size (int): size of Bookmarks
        """
        num_files, num_bookmarks = self.count()
        is_file = self.path.joinpath("Bookmarks").is_file()
        if is_file:
            size = os.stat(self.path.joinpath("Bookmarks")).st_size
        else:
            size = 0
        return {
            "profile": self.path,
            "name": self.preferences["profile"]["name"],
            "has_bookmarks": is_file,
            "circe_files": num_files,
            "circe_bookmarks": num_bookmarks,
            "size": size
        }

    def list(self) -> List[Tuple[int, str]]:
        """ Returns a list of (identifier, filename) tuples for all Circe-encoded files present in Bookmarks. """
        metadata = []
        for folder in self.bookmarks["roots"]["other"]["children"]:
            if "cid" in folder:
                identifier, encoded_name = folder["cid"].split("/", maxsplit=1)
                decoded_name = base64.b64decode(encoded_name.encode()).decode()
                metadata.append((int(identifier), decoded_name))
        return metadata

    def load(self) -> None:
        """ Loads Bookmarks and Preferences into object state. """
        bookmarks = self.path.joinpath("Bookmarks")
        if not bookmarks.exists() or os.stat(bookmarks).st_size == 0:
            self.bookmarks = helpers.SKELETON
        else:
            with open(bookmarks, "r", encoding="utf-8") as b:
                self.bookmarks = json.load(b)

        with open(self.path.joinpath("Preferences"), "r", encoding="utf-8") as p:
            self.preferences = json.load(p)

        # Update the current CID to avoid name collisions with any data that is still present in Bookmarks
        max_cid = -1
        for folder in self.bookmarks['roots']['bookmark_bar']['children']:
            if "cid" in folder:
                identifier = int(folder["cid"].split("/", maxsplit=1)[0])
                if identifier > max_cid:
                    max_cid = identifier
        self._cid = max_cid + 1

    def peek(self, cid: int) -> Dict:
        """ Returns information about the specified CID.

        Args:
            cid (int): The integer prefix of the CID of interest.

        Returns:
            Dict: If the prefix / corresponding CID is present in Bookmarks, this function will returns a small
                dictionary of metadata about the corresponding, Circe-encoded file. If the prefix / corresponding CID
                is *not* present, the dictionary will be blank.
        """
        for folder in self.bookmarks["roots"]["other"]["children"]:
            if folder.get("cid"):
                identifier, encoded_name = folder["cid"].split("/", maxsplit=1)
                if int(identifier) == cid:
                    decoded_name = base64.b64decode(encoded_name.encode()).decode()
                    return {
                        "file": decoded_name,
                        "title": folder["name"],
                        "num_data_chunks": len(folder["children"])
                    }
        return {}

    def save(self) -> None:
        """ Saves the Bookmarks and Preferences files back to disk. """
        with open(self.path.joinpath("Bookmarks"), "w", encoding="utf-8") as b:
            with open(self.path.joinpath("Preferences"), "w", encoding="utf-8") as p:
                json.dump(self.bookmarks, b, ensure_ascii=False, indent=2)
                json.dump(self.preferences, p, ensure_ascii=False)

    def wipe(self) -> None:
        """ Deletes all Circe-encoded data from the Bookmarks file. """
        # Mutating an object (in this case: self.bookmarks) while iterating over it is bad practice. Instead, we'll
        # iterate over a *copy* of self.bookmarks to safely delete pointers to any Circe folders that we find.
        # https://medium.com/datadriveninvestor/mutable-and-immutable-python-2093deeac8d9
        # https://stackoverflow.com/questions/2612802/list-changes-unexpectedly-after-assignment-how-do-i-clone-or-copy-it-to-prevent
        num_deletions = 0
        for i, folder in enumerate(self.bookmarks["roots"]["other"]["children"].copy()):
            if "cid" in folder:
                del self.bookmarks['roots']['other']['children'][i-num_deletions]
                num_deletions += 1
