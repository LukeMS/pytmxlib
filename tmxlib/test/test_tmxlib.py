
from __future__ import division

import os
import tempfile
from StringIO import StringIO
import contextlib

from lxml import etree
from formencode.doctest_xml_compare import xml_compare
import pytest

import tmxlib

# test support code
def params(funcarglist):
    def wrapper(function):
        function.funcarglist = funcarglist
        return function
    return wrapper

def assert_color_tuple_eq(value, expected):
    assert len(value) == len(expected)
    for a, b in zip(value, expected):
        if abs(a - b) >= (1 / 256):
            assert value == expected

def pytest_generate_tests(metafunc):
    for funcargs in getattr(metafunc.function, 'funcarglist', ()):
        metafunc.addcall(funcargs=funcargs)

base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def get_test_filename(name):
    return os.path.join(base_path, name)

def file_contents(filename):
    with open(filename) as fileobj:
        return fileobj.read()

def desert():
    return tmxlib.Map.open(get_test_filename('desert.tmx'))

map_filenames = [
        dict(filename='desert.tmx'),
        dict(filename='perspective_walls.tmx'),
        dict(filename='sewers.tmx'),
        dict(filename='tilebmp-test.tmx'),
        dict(filename='desert_nocompress.tmx'),
        dict(filename='desert_and_walls.tmx'),
    ]

def assert_xml_compare(a, b):
    report = []
    def reporter(problem):
        report.append(problem)

    if not xml_compare(etree.XML(a), etree.XML(b), reporter=reporter):
        print a
        print
        print b
        print
        print 'XML compare report:'
        for r_line in report:
            print r_line
        assert False

# actual test code
@params(map_filenames)
def test_roundtrip_opensave(filename):
    serializer = tmxlib.fileio.TMXSerializer(image_backend='png')
    filename = get_test_filename(filename)
    map = tmxlib.Map.open(filename, serializer=serializer)
    for layer in map.layers:
        # normalize mtime, for Gzip
        layer.mtime = 0
    temporary_file = tempfile.NamedTemporaryFile(delete=False)
    map.check_consistency()
    try:
        temporary_file.close()
        map.save(temporary_file.name)
        assert_xml_compare(file_contents(filename),
                file_contents(temporary_file.name))
    finally:
        os.unlink(temporary_file.name)

@params(map_filenames)
def test_roundtrip_readwrite(filename):
    serializer = tmxlib.fileio.TMXSerializer(image_backend='png')
    xml = file_contents(get_test_filename(filename))
    map = tmxlib.Map.load(xml, base_path=base_path, serializer=serializer)
    for layer in map.layers:
        # normalize mtime, for Gzip
        layer.mtime = 0
    dumped = map.dump()
    assert_xml_compare(xml, dumped)

def test_get_layer_by_name():
    assert desert().layers['Ground'].name == 'Ground'

def test_get_layer_by_index():
    map = desert()
    assert map.layers[0].name == 'Ground'
    assert map.layers[0].index == 0

def test_bad_layer_by_name():
    with pytest.raises(KeyError):
        desert().layers['(nonexisting)']

def test_set_layer_by_name():
    map = desert()
    layer = tmxlib.ArrayMapLayer(map, 'Ground')
    map.layers['Ground'] = layer
    assert map.layers[0] is layer

def test_del_layer():
    map = desert()
    del map.layers['Ground']
    assert len(map.layers) == 0

def test_layers_contains_name():
    assert 'Ground' in desert().layers
    assert 'Sky' not in desert().layers

def test_layers_contains_layer():
    map = desert()
    assert map.layers[0] in map.layers
    assert tmxlib.ArrayMapLayer(map, 'Ground') not in map.layers

def test_explicit_layer_creation():
    map = desert()
    data = [0] * (map.width * map.height)
    data[5] = 1
    layer = tmxlib.ArrayMapLayer(map, 'New layer', data=data)
    assert list(layer.data) == data
    with pytest.raises(ValueError):
        tmxlib.ArrayMapLayer(map, 'New layer', data=[1, 2, 3])

def test_size_get_set():
    map = desert()
    assert (map.width, map.height) == map.size == (40, 40)
    map.width = map.height = 1
    assert (map.width, map.height) == map.size == (1, 1)

def test_tile_size_get_set():
    map = desert()
    assert (map.tile_width, map.tile_height) == map.tile_size == (32, 32)
    map.tile_width = 1
    map.tile_height = 2
    assert (map.tile_width, map.tile_height) == map.tile_size == (1, 2)

def test_pixel_size_get_set():
    map = desert()
    assert (map.pixel_width, map.pixel_height) == map.pixel_size == (
            40 * 32, 40 * 32)
    map.width = map.height = 2
    map.tile_width = 3
    map.tile_height = 4
    assert (map.pixel_width, map.pixel_height) == map.pixel_size == (6, 8)


def test_tileset():
    tileset = desert().tilesets[0]

    assert len(tileset) == len(list(tileset))
    assert list(tileset)[0] == tileset[0]
    assert list(tileset)[0] != tileset[-1]


    assert tileset.tile_width == tileset.tile_height == 32
    tileset.tile_width, tileset.tile_height = 2, 3
    assert tileset.tile_width == 2
    assert tileset.tile_height == 3

def test_tileset_tiles():
    map = desert()
    assert map.tilesets[0][0].number == 0
    assert map.tilesets[0][0].gid(map) == 1

    assert map.tilesets[0][1].number == 1
    assert map.tilesets[0][1].gid(map) == 2

    assert map.tilesets[0][-1].number == len(map.tilesets[0]) - 1

def test_tileset_tile():
    tile = desert().tilesets[0][1]
    assert tile.tileset.name == 'Desert'
    assert tile.size == (32, 32)
    assert tile.properties == {}

    assert tile.width == tile.height == 32


def test_map_tile():
    map = desert()
    tile = map.layers[0][1, 2]
    assert tile.x == 1
    assert tile.y == 2
    assert tile.value == 30
    assert tile.map is map
    assert tile.tileset is map.tilesets[0]
    assert tile.tileset_tile == map.tilesets[0][29]
    assert tile.size == (32, 32)
    assert tile.properties == {}
    tile.value == 1
    map.layers[0].set_value_at((1, 2), 1)
    assert tile.value == tile.gid == 1
    assert map.layers[0][1, 2].value == 1
    map.layers[0][1, 2] = 2
    assert tile.value == tile.gid == 2
    assert map.layers[0][1, 2].value == 2

    tile.gid = 3
    assert tile.value == tile.gid == 3
    assert tile.flipped_horizontally == False
    assert tile.flipped_vertically == False
    assert tile.rotated == False

    tile.flipped_horizontally = True
    assert tile.value == 0x8003
    assert tile.flipped_horizontally == True
    assert tile.flipped_vertically == False
    assert tile.rotated == False
    assert tile.gid == 3

    tile.flipped_vertically = True
    assert tile.value == 0xC003
    assert tile.flipped_horizontally == True
    assert tile.flipped_vertically == True
    assert tile.rotated == False
    assert tile.gid == 3

    tile.rotated = True
    assert tile.value == 0xE003
    assert tile.flipped_horizontally == True
    assert tile.flipped_vertically == True
    assert tile.rotated == True
    assert tile.gid == 3

    tile.flipped_horizontally = False
    assert tile.value == 0x6003
    assert tile.flipped_horizontally == False
    assert tile.flipped_vertically == True
    assert tile.rotated == True
    assert tile.gid == 3

    assert map.layers[0][1, 2].value == 0x6003

    map.layers[0][1, 2] = map.tilesets[0][0]
    assert map.layers[0][1, 2].gid == 1

    map.layers[0][1, 2] = 0
    assert not map.layers[0][1, 2]

def test_map_tiles():
    map = desert()
    assert len(list(map.get_tiles(0, 0))) == 1

    map = tmxlib.Map.open(get_test_filename('desert_and_walls.tmx'))
    tile_list = list(map.get_tiles(0, 0))
    assert len(tile_list) == 3
    assert tile_list[0] == map.layers[0][0, 0]
    assert tile_list[1] == map.layers[1][0, 0]

def test_empty_tile():
    map = desert()
    layer = map.layers[0] = tmxlib.ArrayMapLayer(map, 'Empty')
    tile = layer[0, 0]
    assert tile.value == 0
    assert tile.number == 0
    assert tile.size == (0, 0)
    assert tile.properties == {}


def test_properties():
    map = tmxlib.Map.open(get_test_filename('tilebmp-test.tmx'))

    assert map.properties['test'] == 'value'
    assert map.tilesets['Sewers'][0].properties['obstacle'] == '1'


def test_layer_list():
    map = desert()
    different_map = desert()
    def check_names(names_string):
        names = names_string.split()
        assert [l.name for l in map.layers] == names
    map.add_layer('Sky')
    map.add_layer('Underground', before='Ground')
    map.add_layer('Foliage', after='Ground')

    check_names('Underground Ground Foliage Sky')
    assert [l.name for l in map.layers[2:]] == 'Foliage Sky'.split()
    assert [l.name for l in map.layers[:2]] == 'Underground Ground'.split()
    assert [l.name for l in map.layers[::2]] == 'Underground Foliage'.split()
    assert [l.name for l in map.layers[1::2]] == 'Ground Sky'.split()
    assert [l.name for l in map.layers[:2:2]] == 'Underground'.split()
    assert [l.name for l in map.layers[1:3]] == 'Ground Foliage'.split()

    assert [l.name for l in map.layers[-2:]] == 'Foliage Sky'.split()
    assert [l.name for l in map.layers[:-2]] == 'Underground Ground'.split()
    assert [l.name for l in map.layers[::-2]] == 'Sky Ground'.split()
    assert [l.name for l in map.layers[-2::-2]] == 'Foliage Underground'.split()
    assert [l.name for l in map.layers[:-2:-2]] == 'Sky'.split()
    assert [l.name for l in map.layers[-3:-1]] == 'Ground Foliage'.split()

    ground = map.layers[1]
    assert ground.name == 'Ground'

    del map.layers[1::2]
    check_names('Underground Foliage')
    two_layers = list(map.layers)

    del map.layers[1]
    check_names('Underground')

    map.layers[0] = ground
    check_names('Ground')

    map.layers[1:] = two_layers
    check_names('Ground Underground Foliage')

    del map.layers[:1]
    map.layers[1:1] = [ground]
    check_names('Underground Ground Foliage')

    with pytest.raises(ValueError):
        map.layers[0] = different_map.layers[0]

    map.layers.move('Foliage', -2)
    check_names('Foliage Underground Ground')
    map.layers.move('Ground', -20)
    check_names('Ground Foliage Underground')
    map.layers.move('Underground', -1)
    check_names('Ground Underground Foliage')
    map.layers.move('Underground', 1)
    check_names('Ground Foliage Underground')
    map.layers.move('Ground', 20)
    check_names('Foliage Underground Ground')
    map.layers.move('Foliage', 2)
    check_names('Underground Ground Foliage')

def test_layer_list_empty():
    map = desert()
    ground = map.layers[0]
    def check_names(names_string):
        names = names_string.split()
        assert [l.name for l in map.layers] == names

    del map.layers[:]
    check_names('')

    map.add_layer('Sky')
    check_names('Sky')

    del map.layers[:]
    map.layers.append(ground)
    check_names('Ground')

    del map.layers[:]
    map.layers.insert(0, ground)
    check_names('Ground')

    del map.layers[:]
    map.layers.insert(1, ground)
    check_names('Ground')

    del map.layers[:]
    map.layers.insert(-1, ground)
    check_names('Ground')

def test_multiple_tilesets():
    map = tmxlib.Map.open(get_test_filename('desert_and_walls.tmx'))
    def check_names(names_string):
        names = names_string.split()
        assert [l.name for l in map.tilesets] == names
    check_names('Desert Walls')

    walls = map.tilesets[1]
    walls2 = tmxlib.ImageTileset('Walls2', tile_size=(20, 20),
        image=map.tilesets[0].image)
    map.tilesets.append(walls2)
    check_names('Desert Walls Walls2')

    with pytest.raises(ValueError):
        # Too many tiles to be represented in 2 bytes (along with their flags)
        map.tilesets.append(tmxlib.ImageTileset('Walls2', tile_size=(1, 1),
            image=map.tilesets[0].image))

    assert walls2.first_gid(map) == walls.first_gid(map) + len(walls) == 65
    assert any(t.tileset is walls for t in map.all_tiles())
    assert not any(t.tileset is walls2 for t in map.all_tiles())

    building = map.layers['Building']
    tile = building[1, 1]
    assert tile.tileset is walls
    assert tile.gid == walls.first_gid(map) + tile.number
    assert walls.first_gid(map) < building[1, 1].gid < walls2.first_gid(map)

    map.tilesets.move('Walls2', -1)
    check_names('Desert Walls2 Walls')
    print tile.gid, walls.first_gid(map)
    print tile.tileset_tile
    assert tile.tileset is walls
    assert tile.gid == walls.first_gid(map) + tile.number
    assert walls2.first_gid(map) < walls.first_gid(map) < building[1, 1].gid

    assert any(t.tileset is walls for t in map.all_tiles())
    assert not any(t.tileset is walls2 for t in map.all_tiles())

    map.tilesets.move('Walls2', 1)
    assert tile.tileset is walls
    assert tile.gid == walls.first_gid(map) + tile.number
    assert walls.first_gid(map) < building[1, 1].gid < walls2.first_gid(map)

    map.tilesets.move('Walls2', -1)
    del map.tilesets['Walls2']
    assert tile.tileset is walls
    assert tile.gid == walls.first_gid(map) + tile.number

def test_objects():
    map = tmxlib.Map.open(get_test_filename('desert_and_walls.tmx'))

    objects = map.layers['Objects']

    sign = objects['Sign']
    assert sign.size == (32, 32)
    sign.size = 32, 32
    with pytest.raises(ValueError):
        sign.size = 1, 1

    hole = objects['Hole A']
    assert hole.size == (53, 85)
    hole.size = 1, 1
    assert hole.width == 1

    assert hole.pos == (hole.x, hole.y) == (438, 246)
    hole.x = 10
    hole.y = 10
    assert hole.pos == (10, 10)

    # This map has all objects in one layer only
    all_map_objects = list(map.all_objects())
    assert all_map_objects == list(objects) == list(objects.all_objects())

@params([
        dict(image_backend=None),
        dict(image_backend='png'),
    ])
def test_get_pixel(image_backend):
    serializer = tmxlib.fileio.TMXSerializer(image_backend=image_backend)
    map = tmxlib.Map.open(get_test_filename('desert_and_walls.tmx'),
            serializer=serializer)

    pixel_value = 255 / 255, 208 / 255, 148 / 255, 1

    if image_backend is None:
        def context():
            return pytest.raises(TypeError)
    else:
        @contextlib.contextmanager
        def context():
            yield

    with context():
        assert map.layers['Ground'][0, 0].get_pixel(0, 0) == pixel_value
    with context():
        assert map.tilesets['Desert'][0].get_pixel(0, 0) == pixel_value

    with context():
        assert map.layers['Ground'][0, 0].image[0, 0] == pixel_value
    with context():
        assert map.tilesets['Desert'][0].image[0, 0] == pixel_value

    assert map.tilesets[0].image.data

    with context():
        expected = 0.5, 0.6, 0.7, 0
        map.tilesets['Desert'][0].image[0, 0] = expected
        value = map.tilesets['Desert'][0].image[0, 0]
        assert len(value) == len(expected)
        for a, b in zip(value, expected):
            assert abs(a - b) < (1 / 256)

    empty_tile = map.layers['Building'][0, 0]
    assert not empty_tile
    assert empty_tile.get_pixel(0, 0) == (0, 0, 0, 0)

    tile = map.layers['Ground'][0, 0]

    top_left = 98 / 255, 88 / 255, 56 / 255, 1
    top_right = 98 / 255, 88 / 255, 56 / 255, 1
    bottom_left = 209 / 255, 189 / 255, 158 / 255, 1
    bottom_right = 162 / 255, 152 / 255, 98 / 255, 1

    tile.value = map.tilesets['Desert'][9]
    with context():
        assert_color_tuple_eq(tile.get_pixel(0, 0), top_left)
        assert_color_tuple_eq(tile.get_pixel(0, -1), bottom_left)
        assert_color_tuple_eq(tile.get_pixel(-1, 0), top_right)
        assert_color_tuple_eq(tile.get_pixel(-1, -1), bottom_right)

    tile.value = map.tilesets['Desert'][9]
    tile.flipped_horizontally = True
    with context():
        assert_color_tuple_eq(tile.get_pixel(0, 0), bottom_left)
        assert_color_tuple_eq(tile.get_pixel(0, -1), top_left)
        assert_color_tuple_eq(tile.get_pixel(-1, 0), bottom_right)
        assert_color_tuple_eq(tile.get_pixel(-1, -1), top_right)

    tile.value = map.tilesets['Desert'][9]
    tile.flipped_vertically = True
    with context():
        assert_color_tuple_eq(tile.get_pixel(0, 0), top_right)
        assert_color_tuple_eq(tile.get_pixel(0, -1), bottom_right)
        assert_color_tuple_eq(tile.get_pixel(-1, 0), top_left)
        assert_color_tuple_eq(tile.get_pixel(-1, -1), bottom_left)

    tile.value = map.tilesets['Desert'][9]
    tile.rotated = True
    with context():
        assert_color_tuple_eq(tile.get_pixel(0, 0), top_right)
        assert_color_tuple_eq(tile.get_pixel(0, -1), top_left)
        assert_color_tuple_eq(tile.get_pixel(-1, 0), bottom_right)
        assert_color_tuple_eq(tile.get_pixel(-1, -1), bottom_left)

    tile.value = map.tilesets['Desert'][9]
    tile.flipped_horizontally = True
    tile.flipped_vertically = True
    tile.rotated = True
    with context():
        assert_color_tuple_eq(tile.get_pixel(0, 0), bottom_left)
        assert_color_tuple_eq(tile.get_pixel(0, -1), bottom_right)
        assert_color_tuple_eq(tile.get_pixel(-1, 0), top_left)
        assert_color_tuple_eq(tile.get_pixel(-1, -1),  top_right)

def test_shared_tilesets():
    serializer = tmxlib.fileio.TMXSerializer(image_backend='png')
    map1 = tmxlib.Map.open(get_test_filename('perspective_walls.tmx'),
            serializer=serializer)
    map2 = tmxlib.Map.open(get_test_filename('perspective_walls.tmx'),
            serializer=serializer)

    assert map1.tilesets[0] is map2.tilesets[0]

def test_autoadd_tileset():
    serializer = tmxlib.fileio.TMXSerializer(image_backend='png')
    map = desert()
    tileset = tmxlib.ImageTileset.open(
            get_test_filename('perspective_walls.tsx'), serializer=serializer)

    assert tileset not in map.tilesets

    map.layers[0][0, 0] = tileset[0]

    assert tileset in map.tilesets
