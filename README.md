# Circe
Data exfiltration with bookmarks

The purpose of this package is to demonstrate how browser profile syncing mechanisms can be taken advantage of to
perform data exfiltration and other post-exploitation activities. Circe may provide value to (1) red teamers and
penetration testers as an unusual tool and (2) to blue / purple teams looking to harden their browser security posture.

All major browsers support a feature called "Profiles". Profiles are used to separate users that may be sharing a
computer and/or different types of accounts (work, personal, etc.) from each other. Profiles contain information such
as browser settings, extensions / add-ons, passwords, history, and bookmarks. However, in addition to being saved
locally, this information can be shared between devices over the cloud, which presents researchers, red teamers, and
bad actors with an interesting two-way communication channel.

For the time being, Circe focuses on data exfiltration using the Bookmarks file in Google Chrome.

### Installation
This project is currently *not* on PyPI -- please clone the repository and install locally or use pip (there are no external dependencies):
    pip install git+git://github.com/Sileniia/circe.git

### Usage
    import circe
    profile = circe.Profile()
    profile.load()
    profile.add_file("path_to_file")
    profile.save()

We can also use a `circe.Profile()` object as a context manager to let Python handle `load()` and `save()` for us:
###
    
    with circe.Profile() as profile:
        # Add a file
        profile.add_file("path_to_file")
        
        # Retrieve the file content
        _, data = profile.get(0)

In order to actually move data, you will need to turn on profile syncing in Chrome:

https://support.google.com/chrome/answer/185277

### Advantages:
    1. "Low-tech" -- tools are easy to use and likely available in the environment (web browser, profile syncing)
    2. Less obvious than other exfiltration methods (email, file-sharing services, flash drives, remote management
        software, cloud infrastructure, DNS tunneling, etc.) and hides in common traffic.
    3. Ideal for insider threat data exfiltration

### Disadvantages:
    1. Hands-on-keyboard (or at least initially to turn on profile syncing)
    2. Python + Circe setup will generate network and host artifacts
    3. Easily addressed by turning off profile syncing in AD environments

### Terminology:
    - The "User Data" directory is the top-level directory in the Chrome file structure that encapsulates Profiles.
        https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md
    - A "Profile" is a User Data subdirectory and contains information such as History, Preferences, and Bookmarks.
    - "Bookmarks" refers to the Bookmarks file from the selected profile.
    - A "Circe-encoded" file refers to a file hidden by this package in Bookmarks.
    - Bookmarks may contain two types of entries -- folders and URLs. Folders are used to organize URLs. To Circe-encode
        a file, we break it down into data chunks, stuff those inside URL entries, and organize the URLs under folders.
        (one Circe-encoded file per folder). Consequently, a Bookmarks folder and a Circe-encoded file are analogous.
    - Each file is identified by a unique "Circe Identifier", or CID, composed of an integer concatenated with a
        Base64-encoded filename. They are separated by a single "/" character. Example: "0/ZXhhbXBsZQ=="

### Encoding:
    Simply stuffing encoded data into the Bookmarks file is poor OPSEC. To improve our odds and slow down analysis,
    Circe will hide encoded data inside otherwise-legitimate Google search URLs, which often have a large number of URL
    parameters that can be co-opted.
    https://moz.com/blog/the-ultimate-guide-to-the-google-search-parameters
    https://github.com/obsidianforensics/unfurl
    https://www.quora.com/Doing-a-Google-search-I-see-an-operator-in-the-query-gs_l-psy-ab-What-is-it

    Advantages - Obfuscation:
        1. Using "real" URLs for Bookmarks will look more legitimate than simply storing encoded data
        2. Plugging the "URL" into the address bar will result in a legitimate redirect to the cover query
        3. The gs_lcp parameter is not well-understood and already uses lengthy Base64 strings (good hiding candidate)

    Disadvantages - Increased complexity:
        1. We will need a good source of search strings; using the same one over and over again will draw scrutiny
        2. We are limited to <= 2000 characters per bookmark due to legacy browser restrictions
            Forward-looking adaptation in the event that Google chrome or profile syncing are not available
        3. Increased code complexity (although this could be viewed as a good thing for an attacker)
            If we simply stored our data in a single Bookmark, we wouldn't need to chunk, reorder, or obfuscate it

    A typical Google search URL will look like this, with the search string / query stored in the "q" parameter:
    https://www.google.com/search?q=[query]...&gs_lcp=[Base64_string]...

    A Circe-fied Google search URL will hide data in the "gs_lcp" parameter, which does not appear to be well-understood
    and is already in Base64 format. Circe also adds a new "cc" parameter to track chunk order for later reassembly.
    https://www.google.com/search?q=[query]...&gs_lcp=[Base64_encoded_data]...&cc=[chunk_number]

    Each encoded file will be given its own folder in the Bookmarks file:
        {
            "children": dictionary of URL bookmarks to store under this folder (encoded data hidden in Google searches)
            "cid": An integer concatenated to a Base64-encoded filename -- ex: 0/abc
            "data_added": Google Chrome timestamp of when this bookmark was added
            "data_modified": Google Chrome timestamp of when this bookmark was last modified
            "guid": unique identifier for every entry in the Bookmarks file (can be left blank as Chrome will self-heal)
            "id": simply integer identifier for every in the Bookmarks file (Chrome will also self-heal this)
            "name": name / label for the folder
            "type": "folder"
        }

    Then, Circe will compress, encode, and chunk the file; hide each chunk chunk inside a Google search, and save the
    result as a URL bookmark. These URLs will be stored in the encapsulating folder above.
        {
            "date_added": Google Chrome timestamp of when this bookmark was added
            "guid": unique identifier for every entry in the Bookmarks file (can be left blank as Chrome will self-heal)
            "id": simply integer identifier for every in the Bookmarks file (Chrome will also self-heal this)
            "name": name / label for the bookmark
            "type": "url",
            "url": Rogue Google search containing our encoded data chunk
        }

### Decoding:
    To decode one of our files:
        1. Scan Bookmarks for folders containing the "cid" attribute / key
        2. Check whether the attribute contains our specified integer prefix
        3. Put the URLs inside the folder into the correct (ascending) order using the "cc" parameter
        4. Extract the encoded data chunks
        5. Place the data chunks into the correct order
        6. Un-encode the data stream
        6. Decompress the resulting data stream into its original format
