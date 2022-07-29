#!/usr/bin/python
import indigo
import logging
import os
import unicodedata
import threading
from Foundation import NSAppleScript
from ScriptingBridge import SBApplication

''' This module requires PyObjC to be installed in order to use the AppleScriptingBridge for Apple Music

    Module defining a MusicController class for Apple Music, enables:
        basic transport control of the player, 
        query of player status, 
        playing existing playlists,  
        running external appleScripts for more complex control, and
        reporting messages in the notification centre'''

PLAYSTATE = dict([
            (1800426320, "Play"),
            (1800426352, "Pause"),
            (1800426323, "Stop"),
            (1800426310, "Wind"),
            (1800426322, "Rewind")
        ])


class MusicController(object):

    def __init__(self):
        self.app = SBApplication.applicationWithBundleIdentifier_("com.apple.Music")


    # ########################################################################################
    # Player information
    def get_current_track_info(self):
        name = self.app.currentTrack().name()
        album = self.app.currentTrack().album()
        artist = self.app.currentTrack().artist()
        number = self.app.currentTrack().trackNumber()
        if name:
            # Deal with tracks with non-ascii characters such as accents
            name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore')
            album = unicodedata.normalize('NFD', album).encode('ascii', 'ignore')
            artist = unicodedata.normalize('NFD', artist).encode('ascii', 'ignore')
        return [name, album, artist, number]

    def get_current_play_state(self):
        return PLAYSTATE.get(self.app.playerState())

    def get_current_track_position(self):
        return self.app.playerPosition()

    # ########################################################################################
    # Transport Controls
    def playpause(self):
        self.app.playpause()

    def play(self, playlist_name):
        if PLAYSTATE.get(self.app.playerState()) in ['Wind', 'Rewind']:
            self.app.resume()
        elif PLAYSTATE.get(self.app.playerState()) == 'Pause':
            self.app.playpause()
        elif PLAYSTATE.get(self.app.playerState()) == 'Stop':
            self. app.setValue_forKey_('true', 'shuffleEnabled')
            # playlist = self.app.sources().objectWithName_("Library")
            playlist = self.app.sources().objectWithName_("Library").playlists().objectWithName_(playlist_name)
            playlist.playOnce_(None)

    def pause(self):
        if PLAYSTATE.get(self.app.playerState()) == 'Play':
            self.app.pause()

    def stop(self):
        if PLAYSTATE.get(self.app.playerState()) != 'Stop':
            self.app.stop()

    def next_track(self):
        self.app.nextTrack()

    def previous_track(self):
        self.app.previousTrack()

    def wind(self, time):
        # self.app.wind()

        # Native wind function can be a bit annoying
        # I provide an alternative below that skips a set number of seconds forwards
        self.set_current_track_position(time)

    def rewind(self, time):
        # self.app.rewind()

        # Native rewind function can be a bit annoying
        # I provide an alternative below that skips a set number of seconds back
        self.set_current_track_position(time)

    # ########################################################################################
    # More complex playback control functions
    def shuffle(self):
        if self.app.shuffleEnabled():
            self.app.setValue_forKey_('false', 'shuffleEnabled')
        else:
            self.app.setValue_forKey_('true', 'shuffleEnabled')

    def set_current_track_position(self, time, mode='Relative'):
        if mode == 'Relative':
            # Set playback position in seconds relative to current position
            self.app.setPlayerPosition_(self.app.playerPosition() + time)
        elif mode == 'Absolute':
            # Set playback position in seconds from the start of the track
            self.app.setPlayerPosition_(time)

    def play_playlist(self, playlist):
        self.app.stop()
        self.app.setValue_forKey_('true', 'shuffleEnabled')
        playlist = self.app.sources().objectWithName_("Library").playlists().objectWithName_(playlist)
        playlist.playOnce_(None)

    def get_playlist_names(self):
        playlists = ["None"]
        # Generate and return a list of playlists in Apple Music
        for playlist in self.app.sources().objectWithName_("Library").playlists():
            playlists.append(playlist.name())

        return playlists

    def set_rating(self, rate):
        # Set the rating of the track in %
        self.app.currentTrack().setValue_forKey_(str(rate), 'rating')

        if int(rate) == 100:
            # If rated 100% then set to loved and ensure the track is enabled
            self.app.currentTrack().setValue_forKey_('true', 'loved')
            self.app.currentTrack().setValue_forKey_('true', 'enabled')
        elif int(rate) == 0:
            # If rated 0% then set to disliked and disable the track so it will not be played in shuffle
            self.app.currentTrack().setValue_forKey_('true', 'disliked')
            self.app.currentTrack().setValue_forKey_('false', 'enabled')
        else:
            # else remove disliked/loved flags and check the track is enabled for playback
            self.app.currentTrack().setValue_forKey_('false', 'disliked')
            self.app.currentTrack().setValue_forKey_('false', 'loved')
            self.app.currentTrack().setValue_forKey_('true', 'enabled')

    # ########################################################################################
    # Accessory functions - threaded due to execution time
    @staticmethod
    def run_script(script, debug):
        script = 'run script ("' + script + '" as POSIX file)'
        if debug:
            indigo.server.log(script, level=logging.DEBUG)

        def applet(_script):
            # Run an external applescript file
            s = NSAppleScript.alloc().initWithSource_(_script)
            s.executeAndReturnError_(None)

        threading.Thread(target=applet, args=(script,)).start()

    @staticmethod
    def notify(message, subtitle):
        def applet(body, title):
            # Post message in notification center
            path = os.path.dirname(os.path.abspath(__file__))
            script = 'tell application "' + path + '/Notify.app" to notify("BeoGateway", "' + \
                     body + '", "' + title + '")'
            s = NSAppleScript.alloc().initWithSource_(script)
            s.executeAndReturnError_(None)

        threading.Thread(target=applet, args=(message, subtitle,)).start()
