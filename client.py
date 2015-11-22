#!/usr/bin/kivy
from kivy.config import Config
Config.set('kivy', 'log_level', 'debug')
Config.write()
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.widget import Widget
import itertools

from kivy.uix.gridlayout import GridLayout

from pytmx import TiledMap, TiledTileset
from kivy.uix.image import Image
from kivy.properties import StringProperty

from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty
from kivy.vector import Vector
from kivy.clock import Clock

from kivy.logger import Logger
from kivy.animation import Animation

import os
from functools import partial
from kivy.properties import (NumericProperty,
                             StringProperty,
                             BooleanProperty)

import json
import socket
from threading import Thread
import errno
import sys
from kivy.event import EventDispatcher

class KivyTiledMap(TiledMap):
    """Loads Kivy images. Make sure that there is an active OpenGL context
    (Kivy Window) before trying to load a map.
    Source : kivy wiki
    """

    def __init__(self, *args, **kwargs):
        super(KivyTiledMap, self).__init__(*args, **kwargs)

        # call load tile images for each tileset
        for tileset in self.tilesets:
            self.loadTileImages(tileset)

    def loadTileImages(self, ts):
        """Loads the images in filename into Kivy Images.
        :type ts: TiledTileset
        """
        # print ts.source
        image   = Image(source="map/" + ts.source)
        texture = image.texture
        ts.width, ts.height = texture.size

        # initialize the image array
        self.images = [0] * self.maxgid

        p = itertools.product(
            xrange(ts.margin, ts.height, ts.tileheight + ts.margin),
            xrange(ts.margin, ts.width, ts.tilewidth + ts.margin)
        )

        for real_gid, (y, x) in enumerate(p, ts.firstgid):
            if x + ts.tilewidth - ts.spacing > ts.width:
                continue

            gids = self.map_gid(real_gid)

            if gids:
                x = x - ts.spacing
                # convert the y coordinate to opengl (0 at bottom of texture)
                y = ts.height - y - ts.tileheight + ts.spacing

                tile = texture.get_region(x, y, ts.tilewidth, ts.tileheight)

                for gid, flags in gids:
                    self.images[gid] = tile


    def find_tile_with_property(self, property_name, layer_name='Ground'):
        layer = self.get_layer_by_name(layer_name)
        index = 0
        for tile in layer:
            try:
                properties = self.get_tile_properties((tile[0], tile[1], index))
                if properties.has_key(property_name):
                    return tile[0], tile[1]
            except:
                pass

        return None


    def tile_has_property(self, x, y, property_name, layer_name='Ground'):
        """Check if the tile coordinates passed in represent a collision.
        :return: Boolean representing whether or not there was a collision.
        """
        layer = self.get_layer_by_name(layer_name)
        index = 0

        try:
            properties = self.get_tile_properties((x, y, index))
            return properties.has_key(property_name)
        except:
            return False

class TileGrid(GridLayout):
    """Creates a Kivy grid and puts the tiles in a KivyTiledMap in it.
    Source : kivy wiki"""
    map_file = StringProperty('./map/desert.tmx')

    def __init__(self, **kwargs):
        self.map = KivyTiledMap(self.map_file)
        # print "yolo"

        super(TileGrid, self).__init__(
            rows=self.map.height, cols=self.map.width,
            row_force_default=True,
            row_default_height=self.map.tileheight,
            col_force_default=True,
            col_default_width=self.map.tilewidth,
            **kwargs
        )

        tilelayer_index = 0

        for tile in self.map.get_layer_by_name('Ground').tiles():
            self.add_widget(Image(texture=self.map.get_tile_image(tile[0], tile[1], 0), size=(32,32)))
            tilelayer_index += 1

    def valid_move(self, x, y):
        if x < 0 or x > self.map.width or y < 0 or y > self.map.height:
            Logger.debug('TileGrid: Move {},{} is out of bounds'.format(x, y))
            return False

        if self.map.tile_has_property(x, y, 'collision'):
            Logger.debug('TileGrid: Move {},{} collides with something'.format(x, y))
            return False

        return True

class Character(Widget):
    """Manage the Character and draw it in the grid
    """
    ASSETS_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))
    _animation   = {
        'up': [os.path.join(ASSETS_DIR, 'green-up-0.png'),
            os.path.join(ASSETS_DIR, 'green-up-1.png'),
            os.path.join(ASSETS_DIR, 'green-up-2.png'),
            os.path.join(ASSETS_DIR, 'green-up-3.png')],

        'down': [os.path.join(ASSETS_DIR, 'green-down-0.png'),
            os.path.join(ASSETS_DIR, 'green-down-1.png'),
            os.path.join(ASSETS_DIR, 'green-down-2.png'),
            os.path.join(ASSETS_DIR, 'green-down-3.png')],

        'left': [os.path.join(ASSETS_DIR, 'green-left-0.png'),
            os.path.join(ASSETS_DIR, 'green-left-1.png'),
            os.path.join(ASSETS_DIR, 'green-left-2.png'),
            os.path.join(ASSETS_DIR, 'green-left-3.png')],

        'right': [os.path.join(ASSETS_DIR, 'green-right-0.png'),
            os.path.join(ASSETS_DIR, 'green-right-1.png'),
            os.path.join(ASSETS_DIR, 'green-right-2.png'),
            os.path.join(ASSETS_DIR, 'green-right-3.png')]
    }
    source     = StringProperty()         #The current image of the character
    _animframe = NumericProperty(0)       #The current frame of the animation
    _animating = BooleanProperty(False)   #Is the char animating ?
    direction  = StringProperty('down')   #Where the player is watching
    position_x = NumericProperty(5)       #Position of the char inside the camera
    position_y = NumericProperty(5)       #Position of the char inside the camera
    map_height = NumericProperty(18)      #Current windows size in number of tile
    map_width  = NumericProperty(40)      #Current windows size in number of tile

    def __init__(self, **kwargs):
        super(Character, self).__init__(**kwargs)
        self.source       = self._animation.get('down')[0]
        self.map_height   = (Window.height / 32 + 1) / 2
        self.map_width    = (Window.width / 32 + 1) / 2
        self.current_tile = Vector(5, 5)

    def update_position(self):
        self.map_width  = (Window.width / 32 + 1) / 2
        self.map_height = (Window.height / 32 + 1) / 2
        self.position_x = self.current_tile.x + camera.x
        self.position_y = self.current_tile.y - camera.y
        self.source     = self._animation.get(self.direction)[0]
        Logger.debug('Character: Moving to [{}, {}]'.format(self.position_x, self.position_y))

    def _animate(self, direction, dt):
        self._animframe -= 1
        animlist = self._animation.get(direction)
        if self._animframe > 0 and self.source in animlist:
            self.source = animlist[(animlist.index(self.source) + 1) % (len(animlist))]
            Clock.schedule_once(partial(self._animate, direction), dt)
        else:
            self._animating = False
            self.source = self._animation.get(direction)[0]

class Player(Character):
    """Inherits Character and add touch/keyboard event to move the char
    """
    ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))
    _animation = {
        'up': [os.path.join(ASSETS_DIR, 'red-up-0.png'),
            os.path.join(ASSETS_DIR, 'red-up-1.png'),
            os.path.join(ASSETS_DIR, 'red-up-2.png'),
            os.path.join(ASSETS_DIR, 'red-up-3.png')],

        'down': [os.path.join(ASSETS_DIR, 'red-down-0.png'),
            os.path.join(ASSETS_DIR, 'red-down-1.png'),
            os.path.join(ASSETS_DIR, 'red-down-2.png'),
            os.path.join(ASSETS_DIR, 'red-down-3.png')],

        'left': [os.path.join(ASSETS_DIR, 'red-left-0.png'),
            os.path.join(ASSETS_DIR, 'red-left-1.png'),
            os.path.join(ASSETS_DIR, 'red-left-2.png'),
            os.path.join(ASSETS_DIR, 'red-left-3.png')],

        'right': [os.path.join(ASSETS_DIR, 'red-right-0.png'),
            os.path.join(ASSETS_DIR, 'red-right-1.png'),
            os.path.join(ASSETS_DIR, 'red-right-2.png'),
            os.path.join(ASSETS_DIR, 'red-right-3.png')]
    }
    map_grid   = ObjectProperty(None)     #Grid object
    online     = BooleanProperty(True)    #Is the game playing online ?

    def __init__(self, **kwargs):
        super(Player, self).__init__(**kwargs)
        self.keyboard   = Window.request_keyboard(self.on_keyboard_closed, self, 'text')
        self.keyboard.bind(on_key_down=self.on_key_down)
        self.source     = self._animation.get('down')[0]
        self.map_height = (Window.height / 32 + 1) / 2
        self.map_width  = (Window.width / 32 + 1) / 2
        self.listener   = None

    def initListener (self,listener) : 
        self.listener = listener
        self.online   = listener.online
        if self.online:
            self.listener.sock.send(json.dumps((self.current_tile.x, self.current_tile.y, self.direction)) + "|")

    def on_touch_down(self, touch):
        Logger.debug('Input: touch')

    def on_key_down(self, keyboard, keycode, text, modifiers):
        value, key_name = keycode
        # Logger.debug('Input: {}'.format(key_name))

        if key_name in ['up', 'down', 'left', 'right']:
            dx = 0
            dy = 0
            new_dir = self.direction

            if key_name == 'up':
                # if the direction change, the char turn and don't move
                if new_dir != 'up':
                    new_dir = 'up'
                else:
                    dy = -1
                
            elif key_name == 'down':
                if new_dir != 'down':
                    new_dir = 'down'
                else:
                    dy = 1
                
            elif key_name == 'left':
                if new_dir != 'left':
                    new_dir = 'left'
                else:
                    dx = -1
                
            elif key_name == 'right':
                if new_dir != 'right':
                    new_dir = 'right'
                else:
                    dx = 1

            if self.map_grid.valid_move(self.current_tile.x + dx, self.current_tile.y + dy):
                cameraUpdate = False
                self.map_width = (Window.width / 32 + 1) / 2

                # if user is in camera zone : we only move the player position
                if (self.position_x + dx < self.map_width and self.current_tile.x < self.map_width) or self.current_tile.x + dx > self.map_grid.map.width - self.map_width:
                    self.position_x += dx
                else:
                # else we move only the camera
                    camera.x -= dx
                    cameraUpdate =  True
                self.current_tile.x += dx

                self.map_height = (Window.height / 32 + 1) / 2
                # if user move in camera zone, we only move the player position
                if (self.position_y + dy < self.map_height and self.current_tile.y < self.map_height) or self.current_tile.y + dy + 2 > self.map_grid.map.height - self.map_height:
                    self.position_y += dy
                else:
                # else we move only the camera
                    camera.y += dy
                    cameraUpdate =  True
                self.current_tile.y += dy

                #if the camera will move, we move all characters
                if cameraUpdate:
                    for player in players.values():
                        player.update_position()

                Logger.debug('Player: Moving to [{}, {}]'.format(self.position_x, self.position_y))
                Logger.debug('Position : Moving to {}'.format(self.current_tile))
                Logger.debug('Camera   : Moving to {}'.format(camera))

                #Move the camera
                coords = camera*32
                anim   = Animation(x=coords[0], y=coords[1], duration=0.2, transition="linear")
                anim.start(self.map_grid)
                # Logger.debug('Character: {} => {}'.format(self.direction, new_dir))

                #Move the char with animation
                if self.direction == new_dir:
                    self._animating = True
                    self._animframe = len(self._animation.get(new_dir, []))
                    anim_dt = 0.3 / self._animframe
                    Clock.schedule_once(partial(self._animate, new_dir), anim_dt)
                else:
                    self.source    = self._animation.get(new_dir)[0]
                    self.direction = new_dir

                if self.online:
                    self.listener.sock.send(json.dumps((self.current_tile.x, self.current_tile.y, self.direction)) + "|")

    def on_keyboard_closed(self):
        self.keyboard.unbind(on_key_down=self.on_keyboard_down)
        self.keyboard = None

class Camera(EventDispatcher):
    """Manage the Camera
    """
    x = NumericProperty(0)
    y = NumericProperty(0)

    def __str__(self):
        return '[' + str(self.x) + ', ' + str(self.y) + ']'

    def __mul__(self, other):
        return (self.x*other, self.y*other)

class ListenerServer(Thread):
    """Thread to listen to the server for update of online players
    """
    runThread = True
    sock      = None
    online    = True
    grid      = None

    def __init__(self, grid):
        Thread.__init__(self)
        # hote = "tpdrio.esiee.fr"
        # port = 8004
        hote = "localhost"
        port = 5000

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.grid = grid
        try:
            self.sock.connect((hote, port))
            self.sock.setblocking(0)
        except socket.error, e:
            self.online = False

        if self.online:
            Logger.debug("Listener: Connection on {}".format(port))
        else:
            Logger.debug("Listener: Offline play")


    def run(self):

        while self.runThread:
            try:
                # we wait for a message from server
                messages = self.sock.recv(2048)
            except socket.error, e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    continue
                else:
                    # a "real" error occurred
                    print e
                    sys.exit(1)
            else:
                Logger.debug("Listener: Message received from server {}".format(messages))

                for message in messages.split("|"):
                    if len(message) > 0:
                        player = json.loads(message)
                        if len(player) > 0:
                            #If the player just connected
                            if player[0] not in players:
                                players[player[0]] = Character()
                                self.grid.add_widget(players[player[0]])

                            #If the player just disconnected
                            if player[1] == 99 and player[2] == 99:
                                Logger.debug("Listener: Deconnection of player {}".format(player[0]))
                                self.grid.remove_widget(players[player[0]])
                                del players[player[0]]
                            else:
                                players[player[0]].current_tile.x = player[1]
                                players[player[0]].current_tile.y = player[2]
                                players[player[0]].direction      = player[3]
                                players[player[0]].update_position()
           
        Logger.debug("Listener: Closing thread")

#Global vars
players    = {}
camera     = Camera()

class ClientApp(App):
    listener = None

    def build(self):
        grid = TileGrid()

        self.listener = ListenerServer(grid)
        self.listener.start()

    	c = Player(map_grid=grid)
        c.initListener(self.listener)
    	grid.add_widget(c)

        return grid

    def on_stop(self):
        Logger.debug('App   : Closing the app')
        if self.listener.online:
            #Close the connection with the server
            self.listener.sock.send(json.dumps((99, 99, "down")) + "|")
            self.listener.sock.close()
            self.listener.runThread = False

if __name__ == '__main__':
    ClientApp().run()