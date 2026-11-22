"""Original campaign, maps and characters. Python 3.9; no external art required."""
from dataclasses import dataclass, asdict
import random

MAP_W, MAP_H = 48, 34
NAMES = ['黎明の村', '翠緑の森', '鉄火の山道', '星影の湿原', '白銀の王城']
SUBTITLES = ['THE LAST HEARTH', 'FOREST OF THE OATH', 'EMBER MOUNTAINS', 'THE STARFALL MARSH', 'THE HOLLOW THRONE']
COLORS = ['#91b85e', '#4b8c64', '#a49a82', '#697b90', '#889cab']
SPAWNS = [(23, 26), (23, 30), (23, 30), (23, 30), (23, 30)]
GOALS = [(24, 5), (24, 5), (24, 5), (24, 5), (24, 5)]
RECRUITS = {
    1: ('リーフ', 'エルフ', '森の声があなたを呼んでいる。私の弓を、帰還の旅に。'),
    2: ('ボルグ', 'ドワーフ', '王とは冠ではない。民のために立つ者だ。わしの斧も連れていけ。'),
    3: ('ピピン', 'ハーフフット', '小さな足でも王城へ届くよ。星の道は、ぼくに任せて！'),
}

@dataclass
class Hero:
    name: str
    race: str
    level: int = 1
    xp: int = 0
    hp: int = 70
    mp: int = 18
    weapon: int = 0
    armor: int = 0

    @property
    def max_hp(self):
        return {'人間': 70, 'エルフ': 55, 'ドワーフ': 95, 'ハーフフット': 60}[self.race] + (self.level - 1) * 16

    @property
    def max_mp(self):
        return {'人間': 18, 'エルフ': 30, 'ドワーフ': 14, 'ハーフフット': 24}[self.race] + (self.level - 1) * 5

    @property
    def attack(self):
        return {'人間': 15, 'エルフ': 17, 'ドワーフ': 22, 'ハーフフット': 16}[self.race] + self.level * 4 + self.weapon * 7

    @property
    def defense(self):
        return {'人間': 5, 'エルフ': 3, 'ドワーフ': 9, 'ハーフフット': 4}[self.race] + self.level * 2 + self.armor * 4

    def restore(self):
        self.hp, self.mp = self.max_hp, self.max_mp

    def gain(self, amount):
        self.xp += amount
        levels = 0
        while self.xp >= self.level * 35:
            self.xp -= self.level * 35
            self.level += 1
            levels += 1
        if levels:
            self.restore()
        return levels

    def dump(self):
        return asdict(self)


def make_map(zone):
    """Seeded tiles, with a guaranteed connected road between every landmark."""
    rng = random.Random(831 + zone)
    tiles = [['.' for _ in range(MAP_W)] for _ in range(MAP_H)]
    for y in range(MAP_H):
        for x in range(MAP_W):
            if x < 2 or x >= MAP_W - 2 or y < 2 or y >= MAP_H - 2:
                tiles[y][x] = 'T' if zone < 2 else 'R'
            elif rng.random() < .17:
                tiles[y][x] = 'T' if zone < 2 else ('R' if zone in (2, 4) else '~')
            elif rng.random() < .13:
                tiles[y][x] = ','
    for y in range(3, 32):
        for x in range(22, 27):
            tiles[y][x] = ':'
    for y in (11, 22, 27):
        for x in range(7, 41):
            tiles[y][x] = ':'
    for x in (8, 13, 35, 39):
        for y in range(9, 29):
            tiles[y][x] = ':'
    if zone == 0:
        for hx, hy in [(9, 10), (31, 10), (9, 19), (31, 19)]:
            for y in range(hy, hy + 3):
                for x in range(hx, hx + 5):
                    tiles[y][x] = 'H'
        for x in range(17, 21):
            for y in range(15, 19):
                tiles[y][x] = '~'
    if zone == 4:
        for y in range(3, 19):
            for x in range(17, 32):
                tiles[y][x] = ':'
        for y in range(3, 20):
            tiles[y][17] = tiles[y][31] = 'R'
    for x, y in [(24, 5), (24, 29), (24, 30), (23, 26), (24, 23), (13, 22), (35, 22), (8, 11), (39, 11)]:
        tiles[y][x] = ':'
    return tiles


ENEMIES = [
    [('苔スライム', 40, 12, 3, 'slime'), ('野の牙狼', 52, 16, 4, 'wolf')],
    [('蔓の精', 65, 20, 5, 'plant'), ('森の牙狼', 72, 23, 6, 'wolf')],
    [('岩の番人', 100, 27, 10, 'golem'), ('火の精', 72, 30, 6, 'flame')],
    [('夜の亡霊', 105, 32, 8, 'ghost'), ('星喰らい', 125, 34, 10, 'plant')],
    [('空虚の騎士', 145, 38, 13, 'knight'), ('影の亡霊', 120, 36, 10, 'ghost')],
]
BOSSES = {
    1: ('茨の守護獣', 290, 25, 8, 'plant'),
    2: ('熔炉の巨人', 480, 32, 14, 'golem'),
    3: ('星を呑む竜', 650, 38, 12, 'dragon'),
    4: ('空王ヴァルド', 1100, 43, 16, 'king'),
}

JOURNAL = [
    '村の北にいる長老と話し、王家の使命を聞こう。',
    '翠緑の森でリーフと出会い、北の守護獣から森の誓印を取り戻す。',
    '鉄火の山道へ。ボルグと共に熔炉の巨人を倒し、炎の誓印を得る。',
    '星影の湿原でピピンを仲間に。星を呑む竜から星の誓印を取り戻す。',
    '三つの誓印が揃った。白銀の王城へ進み、空王ヴァルドを倒そう。',
    '王は帰還した。仲間と共に、再びこの世界を歩こう。',
]
