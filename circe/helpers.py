""" This module contains variables and helper functions used by the core.Profile class. """

from typing import Any, Iterator, List, Sequence, Union
import os
import pathlib
import platform
import random
import time

# Unix stores timestamps as the number of seconds since 1-1-1970, while Google Chrome stores timestamps as the number
# of *microseconds* since 1-1-1601. Since the difference between these two dates will never change, we can express
# that difference as a constant and convert between the two formats freely.
# https://stackoverflow.com/questions/539900/google-bookmark-export-date-format
# https://stackoverflow.com/questions/19074423/how-to-parse-the-date-added-field-in-chrome-bookmarks-file
EPOCH_DELTA_S = 134774 * 86400  # Epoch delta expressed in seconds: 134774 days * 86400 seconds / day
EPOCH_DELTA_US = 134774 * 86400 * 1000000  # Epoch delta expressed in microseconds:  1 second = 1000000 microseconds

# Minimum, average, maximum, and variance in length of an encoded data chunk, which will be treated as a "URL".
# Stack Overflow suggests using <= 2000 characters for legacy browser support (which may be useful in the future.)
# https://stackoverflow.com/questions/417142/what-is-the-maximum-length-of-a-url-in-different-browsers
MIN_LEN = 1636
AVG_LEN = 1818
MAX_LEN = 2000
JITTER = 0.1

# An otherwise-legitimate Google URL that will hide our encoded data. See core.py docstring for more information.
U_GOOGLE = "https://www.google.com/search?q={q}&source=hp&oq={q}&gs_lcp={gs_lcp}&sclient=gws-wiz&ved=0ahUKEwiYmerCm-nxAhUPJTQIHTDqCS4Q4dUDCAg&uact=5&cc={cc}"

# If you've never bookmarked something in Chrome, the Bookmarks file won't exist yet (in which case we can use the
# SKELETON template to set one up).
SKELETON = {
   "checksum": "de860e456a2777a737153e98fe21cf68",
   "roots": {
      "bookmark_bar": {
         "children": [],
         "date_added": "13251097668578454",
         "date_modified": "13251097679994640",
         "guid": "00000000-0000-4000-a000-000000000002",
         "id": "1",
         "name": "Bookmarks bar",
         "type": "folder"
      },
      "other": {
         # "children" is supposed to be list of dictionaries, but a *dictionary* of dictionaries would be better
         # for our in-memory data structure to provide O(1) access to specific files or to files in a specific order.
         # So far, testing seems to indicate that Chrome will self-heal such a change.
         "children": [],
         "date_added": "13251097668578458",
         "date_modified": "0",
         "guid": "00000000-0000-4000-a000-000000000003",
         "id": "2",
         "name": "Other bookmarks",
         "type": "folder"
      },
      "synced": {
         "children": [],
         "date_added": "13251097668578459",
         "date_modified": "0",
         "guid": "00000000-0000-4000-a000-000000000004",
         "id": "3",
         "name": "Mobile bookmarks",
         "type": "folder"
      }
   },
   "version": 1
}


def dir_user_data() -> pathlib.Path:
    """ Returns the default path to the Chrome User Data directory. """
    o = platform.system()
    if o == "Windows":
        return pathlib.Path(f"C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data")
    elif o == "Darwin":
        return pathlib.Path(f"/Users/{os.getlogin()}/Library/Application Support/Google/Chrome/")
    else:  # elif o == "Linux":
        return pathlib.Path(f"/home/{os.getlogin()}/.config/google-chrome")


def dir_downloads() -> pathlib.Path:
    """ Returns the filepath to the current user's Downloads folder. """
    o = platform.system()
    if o == "Windows":
        return pathlib.Path(f"C:\\Users\\{os.getlogin()}\\Downloads")
    elif o == "Darwin":
        return pathlib.Path(f"/Users/{os.getlogin()}/Downloads")
    else:  # elif o == "Linux":
        return pathlib.Path(f"/home/{os.getlogin()}/Downloads")


def get_profiles(ud: Union[str, pathlib.Path] = None) -> List[str]:
    """ Scans the specified directory and returns any directories named "Default" or starting with "Profile".
    By default, get_profiles will scan the "User Data" directory for the target operating system.

    Args:
        ud (str, pathlib.Path): An absolute filepath to a Chrome User Data directory

    Returns:
        [str]: A list of strings corresponding to each profile in the specified User Data directory.
            If no profiles exist, this function will return an empty list.
    """
    if ud is None:
        ud = dir_user_data()
    elif isinstance(ud, str):
        ud = pathlib.Path(ud)

    profiles = []
    if ud.joinpath("Default").exists():  # The Default profile is not guaranteed to exist - people sometimes delete it
        profiles.append("Default")
    profiles.extend([file for file in os.listdir(ud) if file.startswith("Profile")])

    return profiles


def package_data() -> pathlib.Path:
    """ Returns the absolute path to the circe/data directory. """
    return pathlib.Path(__file__).parents[1].joinpath("data")


def rogue_search(q: str, data: str, cc: int = 0) -> str:
    """ Emits a rogue Google search URL where the gs_lcp parameter is stuffed with encoded data.

    Args:
        q (str): The "cover" Google query that will be searched for if the URL is ever entered into an address bar
        data (str): Encoded data to hide inside the URL
        cc (int): Identifier used to track order and reassemble data chunks into the original stream

    Returns:
        str: A "real" Google search URL hiding a chunk of encoded data
    """
    return U_GOOGLE.format(q=q, gs_lcp=data, cc=cc)


def time_from_chrome(ct: int) -> int:
    """ Converts a Chrome timestamp to a Unix timestamp. """
    return int(ct / 1000000) - EPOCH_DELTA_S


def time_now_chrome() -> int:
    """ Emits the current time as a Chrome timestamp. """
    return int(time.time_ns() / 1000) + EPOCH_DELTA_US


def time_to_chrome(ut: int) -> int:
    """ Converts a Unix timestamp to a Chrome timestamp.

    Expressing a large number in terms of smaller numbers often leads to a loss of precision, as is the case here.
    While Chrome timestamps are expressed in microseconds, Unix timestamps are expressed in seconds, which means the
    microsecond-level information is lost to us. Consequently, the last six digits from to_chrome_time will always be 0.
    """
    return 1000000 * (EPOCH_DELTA_S + ut)


def yield_chunk_randrange(obj: Sequence, min_len: int, max_len: int) -> Iterator:
    """ Yields slices of randomly-selected lengths on [_min, _max] from a sized iterable.

    "Jitter is the introduction of randomness into beacon timing. Imagine we have a beacon signal that is set to call
    home once per minute... [If we introduce a jitter of +/- 50%], the beacon would call home at time intervals
    varying from 30 seconds to 90 seconds." [https://www.activecountermeasures.com/detecting-beacons-with-jitter/]

    This variance makes beaconing more difficult to detect. We re-apply the jitter to the length of our encoded data
    chunks / URLs to confuse cursory analysis.

    Args:
        obj (sequence): An subscriptable object supporting __len__ and __getitem__ (lists, tuple, string, set, etc)
        min_len (int): The minimum desired length for a slice of obj
        max_len (int): The maximum desired length for a slice of obj

    Yields:
        Slices of varying length from the obj iterable
    """
    i = 0
    obj_len = len(obj)

    while 1:
        length = random.randint(min_len, max_len)
        if i + length > obj_len:  # If the next slice runs past the end of the iterable, take what's available
            yield obj[i: obj_len + 1]
            break

        yield obj[i:i+length]
        i += length


def yield_chunk_jitter(obj: Sequence, avg_len: int, jitter: float) -> Iterator:
    """ Yields slices of varying lengths on [length - jitter%, length + jitter%] from a sized iterable.

    This function is simply a front-end for yield_chunk_randrange to re-express the idea with a different API.

    Args:
        obj (sequence): An subscriptable object supporting __len__ and __getitem__ (list, tuple, string, bytes, etc.)
        avg_len (int): The desired average length of a data chunk / slice
        jitter (float): Desired variance in the length of a data chunk / slice expressed as a float / percentage
            Ex: if length is 1000 and jitter is 0.2, this function will yield slices between 800 and 1200 elements.

    Yields:
        Slices of varying length from the obj iterable
    """
    difference = int(avg_len * jitter)
    _min = avg_len - difference
    _max = avg_len + difference
    return yield_chunk_randrange(obj, _min, _max)


def yield_infinite_random(lst: List[Any]) -> Iterator[Any]:
    """ Yields infinite elements from a list of elements in random order. """
    while 1:  # Once the list has been exhausted, re-shuffle it and keep yielding elements
        random.shuffle(lst)
        for element in lst:
            yield element
