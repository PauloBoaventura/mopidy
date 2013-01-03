from __future__ import unicode_literals

import logging
import functools

from spotify import Link, SpotifyError

from mopidy import audio
from mopidy.backends import base


logger = logging.getLogger('mopidy.backends.spotify')


def seek_data_callback(spotify_backend, time_position):
    logger.debug('seek_data_callback(%d) called', time_position)
    spotify_backend.playback.on_seek_data(time_position)


class SpotifyPlaybackProvider(base.BasePlaybackProvider):
    # These GStreamer caps matches the audio data provided by libspotify
    _caps = (
        'audio/x-raw-int, endianness=(int)1234, channels=(int)2, '
        'width=(int)16, depth=(int)16, signed=(boolean)true, '
        'rate=(int)44100')

    def __init__(self, *args, **kwargs):
        super(SpotifyPlaybackProvider, self).__init__(*args, **kwargs)
        self._first_seek = False

    def play(self, track):
        if track.uri is None:
            return False

        spotify_backend = self.backend.actor_ref.proxy()
        seek_data_callback_bound = functools.partial(
            seek_data_callback, spotify_backend)

        self._first_seek = True

        try:
            self.backend.spotify.session.load(
                Link.from_string(track.uri).as_track())
            self.backend.spotify.session.play(1)
            self.backend.spotify.buffer_timestamp = 0

            self.audio.prepare_change()
            self.audio.set_appsrc(
                self._caps,
                seek_data=seek_data_callback_bound)
            self.audio.start_playback()
            self.audio.set_metadata(track)

            return True
        except SpotifyError as e:
            logger.info('Playback of %s failed: %s', track.uri, e)
            return False

    def stop(self):
        self.backend.spotify.session.play(0)
        return super(SpotifyPlaybackProvider, self).stop()

    def on_seek_data(self, time_position):
        logger.debug('playback.on_seek_data(%d) called', time_position)

        if time_position == 0 and self._first_seek:
            self._first_seek = False
            logger.debug('Skipping seek due to issue #300')
            return

        self.backend.spotify.buffer_timestamp = audio.millisecond_to_clocktime(
            time_position)
        self.backend.spotify.session.seek(time_position)
