#!/usr/bin/python
import os
from Foundation import NSAppleScript
from ScriptingBridge import SBApplication

''' Module defining a MusicController class for Apple Music, enables:
        basic transport control of the player, 
        query of player status, 
        playing existing playlists, and 
        running external appleScripts for more complex control
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

    # Player information
    def get_current_track_info(self):
        name = str(self.app.currentTrack().name())
        album = str(self.app.currentTrack().album())
        artist = str(self.app.currentTrack().artist())
        return [name, album, artist]

    def get_current_play_state(self):
        return PLAYSTATE.get(self.app.playerState())

    def get_current_track_position(self):
        return self.app.playerPosition()

    # ########################################################################################
    # Transport Controls
    def playpause(self):
        self.app.playpause()

    def play(self):
        if PLAYSTATE.get(self.app.playerState()) in ['Wind', 'Rewind']:
            self.app.resume()
        elif PLAYSTATE.get(self.app.playerState()) == 'Pause':
            self.app.playpause()
        elif PLAYSTATE.get(self.app.playerState()) == 'Stop':
            playlist = self.app.sources().objectWithName_("Library")
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
        # Native wind function can be a bit annoying
        # I provide an alternative below that skips a set number of seconds forwards
        # self.app.wind()
        self.set_current_track_position(time)

    def rewind(self, time):
        # Native rewind function can be a bit annoying
        # I provide an alternative below that skips a set number of seconds back
        # self.app.rewind()
        self.set_current_track_position(time)

    # ########################################################################################
    # More complex playback control functions
    def set_current_track_position(self, time, mode='Relative'):
        if mode == 'Relative':
            # Set playback position in seconds relative to current position
            self.app.setPlayerPosition_(self.app.playerPosition() + time)
        elif mode == 'Absolute':
            # Set playback position in seconds from the start of the track
            self.app.setPlayerPosition_(time)

    def play_playlist(self, playlist):
        self.app.stop()
        playlist = self.app.sources().objectWithName_("Library").playlists().objectWithName_(playlist)
        playlist.playOnce_(None)

    # ########################################################################################
    # Accessory functions
    @staticmethod
    def run_script(script):
        # Run an external applescript file
        script = 'run script ("' + script + '" as POSIX file)'
        s = NSAppleScript.alloc().initWithSource_(script)
        s.executeAndReturnError_(None)

    @staticmethod
    def notify(message):
        # Post message in notification center
        path = os.path.dirname(os.path.abspath(__file__))
        script = 'tell application "' + path + '/Notify.app" to notify("BeoGateway", "' + \
                 message + '")'
        s = NSAppleScript.alloc().initWithSource_(script)
        s.executeAndReturnError_(None)
