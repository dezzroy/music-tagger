# music-tagger
Python 2.X software which automatically fixes metadata tags of music files


This software attempts to ensure each music file processed ends up having
tag values for artist, album, track name, and maybe track number set correctly.

Dependencies
------------

Recent release of Debian-based Linux distribution
    Tested on Ubuntu 16.04 desktop x86-64

Python >= 2.7, but < 3.0

(Included) Mutagen >= v.1.30 (Python library for managing ID3 tags)
    https://bitbucket.org/lazka/mutagen

pyacoustid >= v.1.1.0 (Python interface for Acoustid web service)
    https://pypi.python.org/pypi/pyacoustid
    https://acoustid.org/
`pip install pyacoustid`

fpcalc Linux command line tool

musicbrainzngs >= 0.6 (Python interface for Musicbrainz web service)
    http://python-musicbrainzngs.readthedocs.org/en/latest/
`apt-get install python-musicbrainzngs`

Program Behavior
----------------

`mp3_tag_fixer.py`: main executable
`mp3_tag_fixer_config.json`: configuration data in JSON format. This should be
set by the user before running the application.

All processed album directories will be moved to either the directory specified
as `output_directory_success` if its files are found to be tagged satisfactorily,
or the directory specified as `output_directory_not_success` if at least one
file is not tagged satisfactorily.

**Assumptions**

- Each directory in `root_directories` exists, and is expressed as an
absolute UNIX path
- Each child directory of each specified root directory is the name of a music
artist, and the child directory's name is the desired value for all recursively
contained mp3 file's artist ID3 tag value
- Each grandchild directory of each specified root directory is the name of an 
album, and the grandchild directory's name is the desired value for all 
contained mp3 file's album ID3 tag value

