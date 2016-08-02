# -*- coding: utf-8 -*-

"""
Functions for interfacing Acoustid and Musicbrainz online databases, and helper
functions dealing with data returned from these services
"""
import logging, subprocess, os
from operator import itemgetter

import acoustid
from acoustid import *
import musicbrainzngs


def set_up_musicbrainzngs( user_agent_app, user_agent_version ):
    """
    Call this before running `mp3_tag_fixer.py`
    """
    musicbrainzngs.set_useragent( user_agent_app, user_agent_version )
    musicbrainzngs.set_rate_limit( limit_or_interval=1.0, new_requests=1 )


def _get_duration_and_fingerprint_from_audio_file(  absolute_path_to_mp3_file,
                                                    log,
                                                    DEVNULL ):
    """
    Given an absolute path to an mp3 file (other file types not tested), this 
    function returns <int: song duration in seconds>, <str: audio fingerprint
    value> on success, or None, None on failure
    """
    duration = None
    fingerprint = None
    try:
        # Send stderr to /dev/null because fpcalc will complain, for example,
        #   a mp3 header is missing, but still successfully generate fingerprint
        string_output = subprocess.check_output(
            ['fpcalc', absolute_path_to_mp3_file],
            stderr=DEVNULL )
        temp = string_output.split('DURATION=')[1].split('\nFINGERPRINT=')
        duration = int( temp[0] )
        fingerprint = temp[1][:-1]
    except Exception as e:
        log.warning('%s: %s: %s' % (absolute_path_to_mp3_file, type(e), str(e)))
        return None, None
    return duration, fingerprint


def _return_acoustid_response(  api_key, 
                                absolute_path_to_mp3_file,
                                log,
                                DEVNULL ):
    """
    Returns None on failure, else a dict containing data from Acoustid web service
    """ 
    file_duration, fingerprint = \
        _get_duration_and_fingerprint_from_audio_file(  absolute_path_to_mp3_file,
                                                        log,
                                                        DEVNULL )
    if file_duration is None or fingerprint is None:
        return None
    response = None
    try:        
        response = lookup( api_key, fingerprint, file_duration )
    except WebServiceError as wse:
        log.warning('WebServiceError thrown for %s, API key is %s: %s' % ( absolute_path_to_mp3_file, api_key, wse.message ) )        
    return response


def get_title_and_artist_from_audio_fingerprint(    absolute_path_to_mp3_file,
                                                    likely_artist,
                                                    likely_album,
                                                    CONFIG_DATA,
                                                    log,
                                                    DEVNULL ):
    """
    Queries Acoustid online database with an internally generated audio 
    fingerprint. This function is quite slow.
    `likely_artist` should be string value derived from mp3 file's grandparent
    directory or existing ID3 tag for artist
    `likely_album` should be string value derived from mp3 file's parent
    directory or existing ID3 tag for album
    Returns None, None, None, None if information can not be reliably retrieved, 
    or if not at all. Otherwise returns <str: track title value from online DB>,
    <str: track ID value (Musicbrainz) from online DB>,
    <str: artist name value from online DB>,
    <str: artist ID value (Musicbrainz) from online DB>
    """
    api_key = CONFIG_DATA['acoustid_web_service']['api_key']
    response = _return_acoustid_response(   api_key, 
                                            absolute_path_to_mp3_file,
                                            log,
                                            DEVNULL )
    if response is None or response['status'] != 'ok' or len( response['results'] ) == 0:
        return None, None, None, None
    highest_scoring_result = sorted(    response['results'], 
                                        key=itemgetter('score'), 
                                        reverse=True )[0]
    if highest_scoring_result['score'] < CONFIG_DATA['acoustid_web_service']['result_threshold'] \
    or 'recordings' not in highest_scoring_result:
        return None, None, None, None
    # Go through 'recordings', then 'artists', try to find the best value for
    #   'name' which matches `likely_artist`, then get value for 'title'
    #   corresponding to artist name
    for recording in highest_scoring_result['recordings']:
        if 'artists' not in recording:
            continue
        for artist in recording['artists']:
            if 'name' not in artist:
                continue
            if artist['name'].lower() == likely_artist.lower():
                return recording['title'], recording['id'], artist['name'], artist['id']
    return None, None, None, None


def get_album_name( recording_id,
                    log ):
    """
    `recording_id` should be a Musicbrainz ID value for a recording (track) as
    a string. Returns None on failure, else returns the recording's album's 
    name as it is most commonly known in the Musicbrainz DB as a string
    """
    try:
        result = musicbrainzngs.get_recording_by_id( recording_id, includes=['releases'] )
    except Exception as exc:
        log.warning("get_album_name(): web service call failed: %s" % exc)
        return None
    most_common_album_name = None
    try:
        # Find the most commonly occuring name for the release (album)
        release_name_occurences = dict()
        for release in result['recording']['release-list']:
            if release['title'] not in release_name_occurences:
                release_name_occurences[release['title']] = 1
            else:
                release_name_occurences[release['title']] += 1
        most_common_album_name = \
            max( release_name_occurences, key=release_name_occurences.get )        
    except Exception as e:
        log.warning("get_album_name(): result parsing failed: %s: %s\nresult was %s" % ( type(e), e, str(result) ))
        return None
    return most_common_album_name