# -*- coding: utf-8 -*-

"""
mp3_tag_fixer.py
Version 2.0
"""

import sys, json, logging, os, pprint, subprocess, re, shutil, operator
from operator import itemgetter
from datetime import datetime

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TALB, TRCK

import online_resources

ILLEGAL_NTFS_FILENAME_CHARS = ('/', '?', '<', '>', '\\', ':', '*', '|', '"', '^')

log = None
LOG_FILE_HANDLER = None

CONFIG_DATA_FILENAME = "mp3_tag_fixer_config.json"
CONFIG_DATA = None

DEVNULL = None


def set_up_logging():
    global log
    log = logging.getLogger('MP3 Tag Fixer')
    log.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s() - %(lineno)d - %(levelname)s\n%(message)s')

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)  
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to log object
    log.addHandler(ch)

    if not os.path.exists('log'):
        os.makedirs('log')
    global LOG_FILE_HANDLER
    LOG_FILE_HANDLER = \
        logging.FileHandler( 'log/mp3_tag_fixer_%s.log' % str(datetime.now()).split('.')[0] )
    LOG_FILE_HANDLER.setLevel(logging.DEBUG)
    LOG_FILE_HANDLER.setFormatter(formatter)
    log.addHandler(LOG_FILE_HANDLER)


def load_config_data():
    global CONFIG_DATA
    with open(CONFIG_DATA_FILENAME) as config_file:
        try:
            CONFIG_DATA = json.load(config_file)
        except ValueError as ve:
            print("load_config_data(): " + str(ve))
    return False if CONFIG_DATA is None else True


def get_list_of_directory_content( absolute_path_directory, list_subdirectories=True ):
    """
    If `absolute_path_directory` exists, returns list of its content. Returned
    list will only contain subdirectories if `list_subdirectories` is True. If
    `list_subdirectories` is False, the returned list will only contain files.
    Each item in a returned list will only be the item's full absolute path.
    Returns None on failure, such as if `absolute_path_directory` does not
    exist.
    """
    # Strip trailing slash from absolute_path_directory if it exists
    apd = absolute_path_directory if absolute_path_directory[-1] != '/' else absolute_path_directory[:-1]
    try:
        all_content = os.listdir( apd )
        result = list()
        for child_item in all_content:
            child_item_absolute_path = apd + '/' + child_item
            if (list_subdirectories and os.path.isdir( child_item_absolute_path )) or \
            (not list_subdirectories and os.path.isfile( child_item_absolute_path )):
                result.append( child_item_absolute_path )            
        return result
    except (TypeError, OSError) as err:
        log.error('`absolute_path_directory` was "%s":\n%s' % (absolute_path_directory, str(err)))
    return None


def is_file_mp3( absolute_path_to_mp3_file ):
    return absolute_path_to_mp3_file[-4:].lower() == '.mp3'


def attempt_get_id3_values( absolute_path_to_mp3_file ):
    """
    In the best case scenario, this function returns <str: artist value>,
    <str: album value>, <str: track title value>, <str: track number>.
    If any of these values seem to be unavailable, the value None will be
    returned instead
    """
    artist, album, title, track_number = None, None, None, None
    try:
        audio = EasyID3( absolute_path_to_mp3_file )

        if 'performer' in audio and len(audio['performer']) > 0:
            artist = audio['performer'][0]
        if 'artist' in audio and len(audio['artist']) > 0:
            artist = audio['artist'][0]

        if 'album' in audio and len( audio['album'] ) > 0:
            album = audio['album'][0]

        if 'title' in audio and len(audio['title']) > 0:
            title = audio['title'][0]

        # Warning: track numbers seem to be strings, not numbers
        #   one example is '<track number>/<total tracks>', others
        #   are zero padded
        if 'tracknumber' in audio and len(audio['tracknumber']) > 0:
            track_number = audio['tracknumber'][0]
    except ID3NoHeaderError as inhe:
        log.debug('"%s" has no ID3 header.' % absolute_path_to_mp3_file)
    except Exception as e:
        log.error('"%s": <%s> %s' % (absolute_path_to_mp3_file, type(e), str(e)))
    return artist, album, title, track_number


def set_mp3_file_id3_header_and_tag_data(   absolute_path_to_mp3_file,
                                            values,
                                            attempt_to_append_or_overwrite_data=True ):
    """
    Returns True if process seemed to go okay, otherwise False
    Attempts to set given ID3 tag data regardless of whether MP3 file has an 
    ID3 header or not.
    `values` should be a dict, optionally containing key mappings for 'artist',
    'album', 'track', or 'track_number'. Mutative operations may be performed
    on `values`.
    If `attempt_to_append_or_overwrite_data` is False, will delete any existing ID3 header 
    and existing tag data, and only assign provided values from `values`.
    If `attempt_to_append_or_overwrite_data` is True, will attempt to overwrite or preserve 
    existing values and append values supplied in `values` if they don't already
    exist.
    """
    if attempt_to_append_or_overwrite_data:
        artist, album, title, track_number = \
            attempt_get_id3_values( absolute_path_to_mp3_file )
        if 'artist' not in values and artist is not None:
            values['artist'] = artist
        if 'album' not in values and album is not None:
            values['album'] = album
        if 'track' not in values and title is not None:
            values['track'] = title
        if 'track_number' not in values and track_number is not None:
            values['track_number'] = track_number  
    try:
        old_audio = ID3( absolute_path_to_mp3_file )
        old_audio.delete()
    except ID3NoHeaderError as inhe:
        log.debug('%s seemed to have no ID3 header' % absolute_path_to_mp3_file)
    except Exception as e:
        log.error('Failed: %s: <%s> %s' % (absolute_path_to_mp3_file, type(e), str(e)))
        return False
    try:        
        audio = ID3()
        if 'artist' in values:
            audio.add( TPE1( encoding=3, text=unicode( values['artist'] ) ) )
        if 'album' in values:
            audio.add( TALB( encoding=3, text=unicode( values['album'] ) ) )
        if 'track' in values:
            audio.add( TIT2( encoding=3, text=unicode( values['track'] ) ) )       
        if 'track_number' in values:
            audio.add( TRCK( encoding=3, text=unicode( values['track_number'] ) ) )
        audio.save( absolute_path_to_mp3_file )
        return True
    except Exception as e:
        log.error('Failed: %s: <%s> %s' % (absolute_path_to_mp3_file, type(e), str(e)))
    return False


def attempt_get_track_number_from_filename( absolute_path_to_mp3_file ):
    """
    Tries to find track number near beginning of file name of mp3 file. Returns
    None if nothing likely was found or any internal error ocurred, otherwise
    returns an int value.
    It's advised to check: 1) this function returns unique results over all
    mp3 files in a given directory, 2) results are in range [1, number_of_mp3_files]
    and 3) results are consecutive.
    """
    track_number = None
    try:
        # Strip '.mp3' suffix from filename
        filename = os.path.split( absolute_path_to_mp3_file )[1][:-4]
        first_candidate = re.findall(r'\d+', filename)
        if len(first_candidate) > 0:
            first_candidate = first_candidate[0]
            if 0 < len(first_candidate) < 3:
                track_number = int(first_candidate)
    except Exception as e:
        log.debug('"%s": <%s> %s' % (absolute_path_to_mp3_file, type(e), str(e)))
    return track_number


def attempt_get_track_number_as_int(    tag_value,
                                        absolute_path_to_mp3_file ):
    """
    If track number can't be converted into an int, returns None, else returns
    int value
    """
    result = tag_value
    if type(result) in (str, unicode):
        # try to convert tag_value into integer object
        try:
            result = int(result)
        except (TypeError, ValueError):
            # If `result` is a string in the form '<number>/<number>',
            #   try to extract first numerical value
            post_split = result.split('/')
            if len(post_split) == 2:
                try:
                    result = int(post_split[0])
                except (TypeError, ValueError):
                    result = None
            else:
                result = None
        except Exception as e:
            result = None
    elif result is None:
        result = attempt_get_track_number_from_filename( absolute_path_to_mp3_file )
    return result if type(result) is int else None


def move_non_mp3_file_procedure(    artist_directory_value,
                                    album_directory_value,
                                    absolute_path_to_file_to_move ):
    """
    """
    destination_directory = os.path.join(
        CONFIG_DATA['non_mp3_file_directory'],
        artist_directory_value,
        album_directory_value )
    if not os.path.exists( destination_directory ):
        os.makedirs( destination_directory )
    shutil.move( absolute_path_to_file_to_move, destination_directory )
    return 'Moved "%s" to "%s"\n' % (os.path.split(absolute_path_to_file_to_move)[1], destination_directory)


def do_remove_album_release_year_procedure( tag_values,
                                            existing_album_tag_value ):
    """
    Check if album tag value candidate in `tag_values` (which is the directory 
    name) has a year released prefix. If so, try to reassign a value which does
    not have the year released prefix.
    Called as a procedure for `process_album_directory()`, which should append
    the returned string `report` to its own `report`
    """
    report = ''
    re_find_year_result = re.findall( r'\d{4}', tag_values['album'] )
    if len(re_find_year_result) > 0:
        # Album directory name has a year released prefix, so check if tag
        # value for album exists and lacks a year released prefix. If so, use
        # it for the album tag value
        if existing_album_tag_value is not None \
        and len( re.findall( r'\d{4}', existing_album_tag_value ) ) == 0:
            tag_values['album'] = existing_album_tag_value
            report = 'Setting album tag value to "%s"\n' % tag_values['album']
        else:
            # Attempt to extract album name without year released prefix
            album_name_extract_result = \
                re.findall( r'[a-zA-Z].+|[a-zA-Z]', tag_values['album'] )
            if len(album_name_extract_result) > 0:
                tag_values['album'] = album_name_extract_result[0]
                report = 'Setting album tag value to "%s"\n' % tag_values['album']
    return report


def do_track_number_procedure( dict_mp3_file_track_number ):
    """
    Called as a procedure for `process_album_directory()`, which should append
    the returned string `report` to its own `report`
    """
    report = ''
    track_numbers_seem_valid = len(dict_mp3_file_track_number) > 0
    if track_numbers_seem_valid:
        # Create a list of tuples which corresponds to dict_mp3_file_track_number
        #   but sorted by the values (track numbers)
        dict_mp3_file_track_number_sorted = sorted( dict_mp3_file_track_number.items(), 
                                                    key=operator.itemgetter(1) )
        try:
            # Check that track numbers start with 1 and are consecutive
            for i in xrange( len( dict_mp3_file_track_number_sorted ) ):
                if int(dict_mp3_file_track_number_sorted[i][1]) != (i+1):
                    log.debug('Bad track number: %s' % str(dict_mp3_file_track_number_sorted[i]))
                    track_numbers_seem_valid = False
                    break
        except TypeError:
            log.debug('Bad track numbers: %s' % str(dict_mp3_file_track_number_sorted))
            track_numbers_seem_valid = False
    if track_numbers_seem_valid:
        report += 'Track numbers seem valid, so adding them to files\' ID3 data\n'
        for mapping in dict_mp3_file_track_number.items():
            tag_attempt = set_mp3_file_id3_header_and_tag_data( 
                mapping[0], # absolute path to MP3 file
                {'track_number': int(mapping[1])} )     
            report += '"%s": %s adding track number to ID3 data\n' % (os.path.split(mapping[0])[1], 'Succeeded' if tag_attempt else 'Failed')
    return report


def process_album_directory( absolute_path_album_dir ):
    """
    Returns True if all contained mp3 files are tagged satisfactorily and the
    specified album directory contains no subdirectories, else returns False.
    `absolute_path_album_dir` is assumed to exist.
    Will move non mp3 files out of `absolute_path_album_dir` to appropriate
    subdirectory of directory specified in `mp3_tag_fixer_config.json`.
    """
    report = 'Album directory "%s":\n' % absolute_path_album_dir

    # Check if the given album directory contains any subdirectories (it should not)
    subdir_list = get_list_of_directory_content( absolute_path_album_dir )
    if len( subdir_list ) > 0:
        report += 'contains the following subdirectories:' 
        for sub_dir in subdir_list:
            report += '\n    "%s"' % os.path.split(sub_dir)[1]
        log.info( report )
        return False

    contents_are_good = True
    file_list = get_list_of_directory_content(  absolute_path_album_dir, 
                                                list_subdirectories=False )
    dict_mp3_file_track_number = dict() # Maps absolute path to candidate track number
    dict_mp3_file_new_filename = dict() # Maps absolute path to desired new filename
    album_directory_value = os.path.split(absolute_path_album_dir)[1]
    artist_directory_value = os.path.split(os.path.split(absolute_path_album_dir)[0])[1]

    for each_file in file_list:        
        file_name = os.path.split(each_file)[1]
        if not is_file_mp3(each_file):
            # Move non MP3 file to <non_mp3_file_directory>/<artist>/<album>/
            report += move_non_mp3_file_procedure(  artist_directory_value,
                                                    album_directory_value,
                                                    each_file )
            continue

        artist, album, title, track_number = attempt_get_id3_values( each_file )

        track_number = attempt_get_track_number_as_int( track_number, each_file )

        if type(track_number) is int:
            dict_mp3_file_track_number[each_file] = track_number

        tag_values = {
            'artist': artist_directory_value,
            'album': album_directory_value,
            'track': title
        }

        if tag_values['track'] is None or 'track' in tag_values['track'].lower():
            # Check remote music DB for Musicbrainz (mb) data about this track
            report += '"%s": attempting to fingerprint file and query web service...\n' % file_name
            mb_track_name, mb_track_id, mb_artist_name, mb_artist_id = \
                online_resources.get_title_and_artist_from_audio_fingerprint(    
                    each_file,
                    artist_directory_value,
                    album_directory_value,
                    CONFIG_DATA,
                    log,
                    DEVNULL )
            if None in (mb_track_name, mb_track_id, mb_artist_name, mb_artist_id):
                contents_are_good = False
                report += '"%s": track title not available from ID3 tag, and no good data retrieved from remote music DB\n' % file_name
                continue
            tag_values['track'] = mb_track_name  

        # Check if album directory name has a year released prefix, attempt removal
        report += do_remove_album_release_year_procedure( tag_values, album )

        tag_attempt = set_mp3_file_id3_header_and_tag_data( 
            each_file, tag_values, attempt_to_append_or_overwrite_data=False )
        report += '"%s": %s tagging: %s\n' % (file_name, 'Succeeded' if tag_attempt else 'Failed', str(tag_values))
        
        # Mark MP3 file as needing to be renamed if track name doesn't seem to be in filename
        if tag_attempt and not tag_values['track'].lower() in file_name.lower():
            dict_mp3_file_new_filename[each_file] = \
                os.path.join( os.path.split(each_file)[0], tag_values['track'] + '.mp3' )
            
        contents_are_good = contents_are_good and tag_attempt  

    # Check if candidate track numbers seem valid
    report += do_track_number_procedure( dict_mp3_file_track_number )

    # Rename MP3 files for each mapping in dict_mp3_file_new_filename. If the
    # file has a track number available, prepend it to the new filename (new
    # filename is just the track name with '.mp3' file suffix)
    # NB: `existing_filename` and `new_filename` are both absolute paths
    for existing_filename, new_filename in dict_mp3_file_new_filename.items():
        try:     
            filename_to_use = new_filename
            parent_dir = os.path.split(existing_filename)[0]
            if existing_filename in dict_mp3_file_track_number:                
                just_filename = os.path.split(new_filename)[1]                
                track_number = dict_mp3_file_track_number[existing_filename]
                filename_to_use = os.path.join( parent_dir, '{0:02} - '.format(track_number) + just_filename )          
            # Remove any NTFS illegal characters that may occur in `just_filename`
            just_filename = os.path.split(filename_to_use)[1]
            for illegal_char in ILLEGAL_NTFS_FILENAME_CHARS:
                just_filename = just_filename.replace( illegal_char, '' )
            filename_to_use = os.path.join( parent_dir, just_filename )
            os.rename( existing_filename, filename_to_use )
            report += 'Renamed "%s" to "%s"\n' % ( os.path.split(existing_filename)[1], os.path.split(filename_to_use)[1] )
        except Exception as e:
            report += 'Failed to rename "%s": %s: %s\n' % (existing_filename, type(e), e)

    log.info( report )
    return contents_are_good


def process_root_directories():
    """
    """
    for root_dir in CONFIG_DATA['root_directories']:
        log.debug('Processing root directory "%s"...' % root_dir)
        for artist_dir in get_list_of_directory_content( root_dir ):
            for album_dir in get_list_of_directory_content( artist_dir ):
                result = process_album_directory( album_dir )
                if result:
                    destination_directory = os.path.join( 
                        CONFIG_DATA['output_directory_success'],
                        os.path.split(artist_dir)[1] )
                    if not os.path.exists( destination_directory ):
                        os.makedirs( destination_directory )
                    shutil.move( album_dir, destination_directory )
                else:
                    destination_directory = os.path.join( 
                        CONFIG_DATA['output_directory_not_success'],
                        os.path.split(artist_dir)[1] )
                    if not os.path.exists( destination_directory ):
                        os.makedirs( destination_directory )
                    shutil.move( album_dir, destination_directory )
            # If `artist_dir` is now empty, delete `artist_dir`
            if len(os.listdir( artist_dir )) == 0:
                os.rmdir( artist_dir )


def set_up_input_and_output_directories():
    """
    """
    if not os.path.exists( CONFIG_DATA['output_directory_success'] ):
        os.makedirs( CONFIG_DATA['output_directory_success'] )
    if not os.path.exists( CONFIG_DATA['output_directory_not_success'] ):
        os.makedirs( CONFIG_DATA['output_directory_not_success'] )
    if not os.path.exists( CONFIG_DATA['non_mp3_file_directory'] ):
        os.makedirs( CONFIG_DATA['non_mp3_file_directory'] )
    for root_dir in CONFIG_DATA['root_directories']:
        if not os.path.exists( root_dir ):
            raise RuntimeError('"%s" does not exist.' % root_dir)


def cleanup_procedure():
    """
    Call this before program exits
    """
    if LOG_FILE_HANDLER is not None:
        LOG_FILE_HANDLER.close()
    if DEVNULL is not None:
        DEVNULL.close()


if __name__ == '__main__':
    set_up_logging()
    log.debug("\n\n\nStarting...")    

    if load_config_data() is False:
        log.error("Error loading configuration file or parsing its content, Aborting.")
        cleanup_procedure()
        sys.exit(1)    

    global DEVNULL
    DEVNULL = open( os.devnull, 'wb' )

    try:
        set_up_input_and_output_directories()

        online_resources.set_up_musicbrainzngs(  
            CONFIG_DATA['musicbrainz_web_service']['user_agent_app'], 
            CONFIG_DATA['musicbrainz_web_service']['user_agent_version'] )

        process_root_directories()

    except KeyboardInterrupt:
        log.info('Process terminated by user.')
    except Exception as e:
        log.error('Unexpected error: <%s> %s' % (type(e), str(e)))
    
    cleanup_procedure()

    log.debug("Finished.")