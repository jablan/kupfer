# vim: set noexpandtab ts=4 sw=4:
__kupfer_name__ = _("MPRIS")
__kupfer_sources__ = ("MPRISSource", )
__kupfer_actions__ = ("Enqueue", "EnqueueAndPlay", )
__description__ = _("Control MPRIS playback and playlist")
__version__ = "2011-05-06"
__author__ = "Mladen Jablanovic"

import subprocess
import dbus
import re

from kupfer.objects import Leaf, Source, Action
from kupfer.objects import FileLeaf, RunnableLeaf, SourceLeaf
from kupfer.obj.apps import AppLeafContentMixin
from kupfer.weaklib import DbusWeakCallback
from kupfer import icons, utils
from kupfer import plugin_support
from kupfer import kupferstring
from kupfer import pretty


__kupfer_settings__ = plugin_support.PluginSettings(
	{
		"key": "playlist_toplevel",
		"label": _("Include songs in top level"),
		"type": bool,
		"value": True,
	},
	{
		"key" : "client",
		"label": _("Preferred MPRIS client"),
		"type": str,
		"value": "Exaile",
		"alternatives": ("Exaile", "Audacious", "XMMS", "VLC")
	},
)

plugin_support.check_dbus_connection()

MPRIS_RE = re.compile('^org\.mpris\.([^.]+)$')

def _default_client():
	return str.lower(__kupfer_settings__['client'])

def enqueue_song(fileobj, play_now=False):
	tl = _get_tracklist()
	uri = "file://%s" % fileobj
	tl.AddTrack(uri, play_now)

def dequeue_song(info):
	tl = _get_tracklist()
	tl.DelTrack(info)

# this had to be a hack as MPRIS 1.0 doesn't support "jump to" (WTF!)
def play_song(info):
#	pretty.print_debug('Wanted: %d' % info)
	tl = _get_tracklist()
	pl = _get_player()
# has to be playing in order to get current track (exaile returns -1 if stopped)
	pl.Play()
	curr = tl.GetCurrentTrack()
#	pretty.print_debug('Current: %d' % curr)
	if info > curr:
		for i in range(info - curr):
			pl.Next()
	else:
		for i in range(curr - info):
			pl.Prev()
#	pl.Play()

def clear_queue():
	player = _get_player()
	tlist = _get_tracklist()
	player.Stop()
	for i in range(tlist.GetLength()):
		tlist.DelTrack(0)

def get_player_id():
	bus = dbus.SessionBus()
	players_running = [ name for name in bus.list_names() if MPRIS_RE.match(name) ]
	if not players_running:
		return None
	if 'org.mpris.%s' % _default_client() in players_running:
		handle = _default_client()
	else:
		handle = MPRIS_RE.match(players_running[0]).group(1)
#	pretty.print_debug("Handle: %s" % handle)
	return handle
  
def _get_player():
	bus = dbus.SessionBus()
	player_obj = bus.get_object('org.mpris.%s' % get_player_id(), '/Player')
	player = dbus.Interface(player_obj, dbus_interface='org.freedesktop.MediaPlayer')
	return player

def _get_tracklist():
	bus = dbus.SessionBus()
	tracklist_obj = bus.get_object('org.mpris.%s' % get_player_id(), '/TrackList')
	tracklist = dbus.Interface(tracklist_obj, dbus_interface='org.freedesktop.MediaPlayer')
	return tracklist

def get_shuffle():
	status = _get_player().GetStatus()
	return status[1] == 1

def toggle_shuffle():
	shuffle = get_shuffle()
	_get_tracklist().SetRandom(not shuffle)

def get_repeat():
	status = _get_player().GetStatus()
	return status[3] == 1

def toggle_repeat():
	repeat = get_repeat()
	_get_tracklist().SetLoop(not repeat)

def get_playlist_songs():
	"""Yield tuples of (position, name) for playlist songs"""
	tracklist = _get_tracklist()
	
	for i in range(tracklist.GetLength()):
		song = tracklist.GetMetadata(i)
		if 'title' in song:
			if 'artist' in song:
				res = "%s - %s" % (song['artist'], song['title'])
			else:
				res = song['title']
		elif 'location' in song:
			res = song['location']
		else:
			res = _('Unnamed')
		yield (i, res)

class Enqueue (Action):
	def __init__(self):
		Action.__init__(self, _("Enqueue"))
	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, fileobj):
		""" TODO: include other types, or determine sound files other way """
		return fileobj.object.endswith(".mp3")

	def activate(self, fileobj):
		enqueue_song(fileobj.object, False)
	def get_description(self):
		return _("Add track to the audio player's play queue")
	def get_gicon(self):
		return icons.ComposedIcon("gtk-execute", "media-playback-start")
	def get_icon_name(self):
		return "media-playback-start"

class EnqueueAndPlay (Action):
	def __init__(self):
		Action.__init__(self, _("Play"))
	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, fileobj):
		return fileobj.object.endswith(".mp3")

	def activate(self, fileobj):
		enqueue_song(fileobj.object, True)
	def get_description(self):
		return _("Add track to the play queue and start playing")
	def get_gicon(self):
		return icons.ComposedIcon("gtk-execute", "media-playback-start")
	def get_icon_name(self):
		return "media-playback-start"

class Dequeue (Action):
	def __init__(self):
		Action.__init__(self, _("Dequeue"))
	def activate(self, leaf):
		dequeue_song(leaf.object)
	def get_description(self):
		return _("Remove track from %s play queue") % get_player_id()
	def get_gicon(self):
		return icons.ComposedIcon("gtk-execute", "media-playback-stop")
	def get_icon_name(self):
		return "media-playback-stop"

class JumpToSong(Action):
	def __init__(self):
		Action.__init__(self, _("Play"))
	def activate(self, leaf):
		play_song(leaf.object)
	def get_description(self):
		return _("Jump to track in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playback-start"

class Play (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Play"))
	def run(self):
		_get_player().Play()
	def get_description(self):
		return _("Resume playback in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playback-start"

class Stop (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Stop"))
	def run(self):
		_get_player().Stop()
	def get_description(self):
		return _("Stops playback in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playback-stop"

class Pause (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Pause"))
	def run(self):
		_get_player().Pause()
	def get_description(self):
		return _("Pause playback in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playback-pause"

class Next (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Next"))
	def run(self):
		_get_player().Next()
	def get_description(self):
		return _("Jump to next track in %s") % get_player_id()
	def get_icon_name(self):
		return "media-skip-forward"

class Previous (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Previous"))
	def run(self):
		_get_player().Prev()
	def get_description(self):
		return _("Jump to previous track in %s") % get_player_id()
	def get_icon_name(self):
		return "media-skip-backward"

class ClearQueue (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Clear Queue"))
	def run(self):
		clear_queue()
	def get_description(self):
		return _("Clear the %s play queue") % get_player_id()
	def get_icon_name(self):
		return "edit-clear"
		
class Shuffle (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Shuffle"))
	def run(self):
		toggle_shuffle()
	def get_description(self):
		return _("Toggle shuffle in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playlist-shuffle"

class Repeat (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Repeat"))
	def run(self):
		toggle_repeat()
	def get_description(self):
		return _("Toggle repeat in %s") % get_player_id()
	def get_icon_name(self):
		return "media-playlist-repeat"

class SongLeaf (Leaf):
	"""The SongLeaf's represented object is the Playlist index"""
	def get_actions(self):
		yield JumpToSong()
#		yield Enqueue()
		yield Dequeue()
	def get_icon_name(self):
		return "audio-x-generic"

class MPRISSongsSource (Source):
	def __init__(self, library):
		Source.__init__(self, _("Playlist"))
		self.library = library
	def get_items(self):
		for song in self.library:
			yield SongLeaf(*song)
	def get_gicon(self):
		return icons.ComposedIcon(get_player_id(), "audio-x-generic",
			emblem_is_fallback=True)
	def provides(self):
		yield SongLeaf

class MPRISSource (AppLeafContentMixin, Source):
	appleaf_content_id = "mpris"
#	source_user_reloadable = True

	def __init__(self):
		Source.__init__(self, _("MPRIS"))
	def initialize(self):
		session_bus = dbus.SessionBus()
		callback = DbusWeakCallback(self.list_changed)
		callback.token = session_bus.add_signal_receiver(
			callback,
			"TrackListChange",
			dbus_interface="org.freedesktop.MediaPlayer",
			path="/TrackList")
		nbo_callback = DbusWeakCallback(self._new_bus_object_callback)
		nbo_callback.token = session_bus.add_signal_receiver(
			nbo_callback,
			"NameOwnerChanged",
			dbus_interface="org.freedesktop.DBus",
			path="/org/freedesktop/DBus")

#		pretty.print_debug('end of initialize')
		self.mark_for_update()
	def list_changed(self, obj):
		"""Callback for tracklist change event"""
#		pretty.print_debug("Signal received!")
#		pretty.print_debug(obj)
		self.mark_for_update()
	def _new_bus_object_callback(self, name, old_owner, new_owner):
		"""Callback for new dbus object (starting and stopping players)"""
		if MPRIS_RE.match(name):
			# MPRIS-supporting player started or stopped
			pretty.print_debug('new dbus object')
			self.mark_for_update()
	def get_items(self):
		if get_player_id():
			yield Play()
			yield Stop()
			yield Pause()
			yield Next()
			yield Previous() 
			yield ClearQueue()
			# Commented as these seem to have no effect
			#yield Shuffle()
			#yield Repeat()
			songs = list(get_playlist_songs())
			songs_source = MPRISSongsSource(songs)
			yield SourceLeaf(songs_source)
			if __kupfer_settings__["playlist_toplevel"]:
				for leaf in songs_source.get_leaves():
					yield leaf
	def get_description(self):
		return __description__
	def get_icon_name(self):
		return get_player_id()
	def provides(self):
		yield RunnableLeaf
