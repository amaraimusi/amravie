"""王の帰還 / The Return of the King — an original, self-contained pixel RPG."""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import argparse
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

import pygame
from world import (Hero, make_map, MAP_W, MAP_H, NAMES, SUBTITLES, SPAWNS,
                   ENEMIES, BOSSES, RECRUITS, JOURNAL)

ROOT = Path(__file__).resolve().parent
W, H, TILE = 960, 640, 32
INK, GOLD, WHITE, MUTED = '#101a29', '#e5c889', '#f1eee2', '#9baec1'
PALETTES = [('#638b52', '#739958', '#427449', '#326255'),
            ('#315948', '#3e6951', '#27473e', '#193d38'),
            ('#756653', '#87765d', '#5e554d', '#504b49'),
            ('#425866', '#506675', '#344955', '#253f50'),
            ('#63767a', '#718587', '#485d68', '#344958')]


class Game:
    def __init__(self, headless=False):
        pygame.init()
        pygame.display.set_caption('王の帰還 | The Return of the King')
        self.screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        fonts = [Path('C:/Windows/Fonts/meiryo.ttc'), Path('C:/Windows/Fonts/YuGothM.ttc'),
                 Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
        self.fontpath = next((str(p) for p in fonts if p.exists()), None)
        self.fonts = {}
        self.tile_cache = {}
        self.running = True
        self.state = 'title'
        self.choice = 0
        self.tick = 0
        self.move_timer = 0
        self.dialog = []
        self.dialog_after = None
        self.notice = ''
        self.notice_time = 0
        self.music_track = None
        self.muted = False
        self.audio = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.audio = True
        except pygame.error:
            pass
        self.new_data()
        if not headless:
            self.music(0)

    def new_data(self):
        self.party = [Hero('アルト', '人間')]
        self.zone = 0
        self.x, self.y = SPAWNS[0]
        self.facing = (0, -1)
        self.stage = 0
        self.gold = 100
        self.potions = 6
        self.ethers = 3
        self.seals = []
        self.chests = []
        self.steps = 0
        self.encounter_at = random.randint(22, 34)
        self.playtime = 0
        self.tiles = make_map(0)
        self.battle = None
        self.menu = 'main'
        self.menu_return = 'field'

    def text(self, value, x, y, size=18, color=WHITE, center=False, surface=None):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(self.fontpath, size)
        s = self.fonts[size].render(str(value), True, pygame.Color(color))
        (surface or self.canvas).blit(s, (x - s.get_width() // 2 if center else x, y))

    def panel(self, rect, color='#142335', border='#667c87'):
        pygame.draw.rect(self.canvas, color, rect, border_radius=7)
        pygame.draw.rect(self.canvas, border, rect, 1, border_radius=7)

    def wrapped(self, s, x, y, width, size=18, color=WHITE):
        line = ''
        for char in s:
            trial = line + char
            if self.fonts.get(size) is None:
                self.text('', 0, 0, size)
            if char == '\n' or self.fonts[size].size(trial)[0] > width:
                self.text(line, x, y, size, color)
                y += size + 10
                line = '' if char == '\n' else char
            else:
                line = trial
        self.text(line, x, y, size, color)
        return y + size + 10

    def toast(self, s):
        self.notice, self.notice_time = s, 3.5

    def say(self, *lines, after=None):
        self.dialog = list(lines)
        self.dialog_after = after

    def advance_dialog(self):
        self.dialog.pop(0)
        if not self.dialog:
            callback, self.dialog_after = self.dialog_after, None
            if callback:
                callback()

    def music(self, zone, battle=False):
        if not self.audio:
            return
        tracks = sorted((ROOT / 'BGM').glob('*.mp3'))
        if not tracks:
            return
        preferred = ['Sous le', 'アゲハ', '鉄と火', '波打ち際', 'Über']
        prefix = '空のレース' if battle else preferred[zone]
        track = next((p for p in tracks if p.name.startswith(prefix)), tracks[zone % len(tracks)])
        if track == self.music_track:
            return
        try:
            pygame.mixer.music.load(str(track))
            pygame.mixer.music.set_volume(0 if self.muted else .35)
            pygame.mixer.music.play(-1, fade_ms=650)
            self.music_track = track
        except (pygame.error, OSError):
            self.audio = False

    def sound(self, pitch=660):
        if not self.audio or self.muted:
            return
        # Tiny original UI chime, generated in memory rather than a downloaded asset.
        import array
        rate, _, channels = pygame.mixer.get_init()
        samples = array.array('h')
        for i in range(int(rate * .055)):
            value = int(1600 * math.sin(i * pitch * math.tau / rate) * (1 - i / (rate * .055)))
            samples.extend([value] * channels)
        pygame.mixer.Sound(buffer=samples).play()

    def change_zone(self, zone, north=False):
        self.zone = zone
        self.tiles = make_map(zone)
        self.x, self.y = (24, 8) if north else SPAWNS[zone]
        self.steps = 0
        self.music(zone)
        self.autosave()
        self.toast(NAMES[zone])

    def save_path(self, slot):
        return ROOT / 'saves' / ('autosave.json' if slot == 0 else 'slot%d.json' % slot)

    def save(self, slot):
        data = dict(version=1, party=[h.dump() for h in self.party], zone=self.zone,
                    x=self.x, y=self.y, stage=self.stage, gold=self.gold,
                    potions=self.potions, ethers=self.ethers, seals=self.seals,
                    chests=self.chests, playtime=int(self.playtime),
                    date=datetime.now().strftime('%Y-%m-%d %H:%M'))
        path = self.save_path(slot)
        path.parent.mkdir(exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)

    def autosave(self):
        try:
            self.save(0)
        except OSError:
            self.toast('自動セーブできません。フォルダの書き込み権限を確認してください。')

    def load(self, slot):
        try:
            d = json.loads(self.save_path(slot).read_text(encoding='utf-8'))
            if d['version'] != 1 or not 0 <= d['zone'] < 5 or not 0 <= d['stage'] <= 5:
                raise ValueError('version/zone')
            party = [Hero(**h) for h in d['party']]
            if not 1 <= len(party) <= 4 or any(h.race not in ['人間', 'エルフ', 'ドワーフ', 'ハーフフット'] or not 1 <= h.level <= 999 or not 0 <= h.hp <= h.max_hp or not 0 <= h.mp <= h.max_mp for h in party):
                raise ValueError('party')
            tiles = make_map(d['zone'])
            x, y = d['x'], d['y']
            if not isinstance(x, int) or not isinstance(y, int) or not 0 <= x < MAP_W or not 0 <= y < MAP_H or tiles[y][x] not in '.:,':
                raise ValueError('position')
            for key in ['gold', 'potions', 'ethers', 'playtime']:
                if not isinstance(d[key], (int, float)) or d[key] < 0:
                    raise ValueError(key)
            if not isinstance(d['seals'], list) or not isinstance(d['chests'], list):
                raise ValueError('flags')
            self.party = party
            for key in ['zone', 'x', 'y', 'stage', 'gold', 'potions', 'ethers', 'seals', 'chests', 'playtime']:
                setattr(self, key, d[key])
            self.tiles, self.state, self.dialog = tiles, 'field', []
            self.menu_return = 'field'
            self.steps = 0
            self.music(self.zone)
            self.toast('旅の記録を読み込みました')
            return True
        except (OSError, ValueError, KeyError, TypeError):
            self.toast('記録がないか、読み込めないデータです。別の枠を選んでください。')
            return False

    def objects(self):
        objs = [(13, 22, 'chest', '宝箱'), (39, 11, 'chest', '宝箱'), (35, 22, 'crystal', '祈りの泉')]
        if self.zone == 0:
            objs += [(24, 5, 'elder', '長老'), (13, 14, 'inn', '宿屋'),
                     (35, 14, 'shop', '道具屋'), (8, 22, 'villager', '村人')]
        else:
            objs += [(24, 23, 'recruit', RECRUITS.get(self.zone, ('古い碑',))[0]),
                     (24, 5, 'boss', '玉座' if self.zone == 4 else '誓印の祭壇')]
        objs += [(24, 29, 'exit', '南へ'), (24, 3, 'exit', '北へ')]
        return objs

    def interact(self):
        candidates = [(abs(x - self.x) + abs(y - self.y), x, y, kind, name)
                      for x, y, kind, name in self.objects() if abs(x - self.x) + abs(y - self.y) <= 1]
        if not candidates:
            self.toast('人・宝箱・祭壇のそばで決定。冒険手帳は Esc / X。')
            return
        _, x, y, kind, name = min(candidates)
        if kind == 'elder':
            if self.stage == 0:
                self.stage = 1
                self.say('長老：アルトよ。王城が空王に奪われてから十年。民は今も、王家の帰還を待っている。',
                         '長老：森・炎・星。三つの誓印は、人と異なる種族がかつて結んだ約束だ。北の道を進み、彼らの声を聞くのだ。',
                         'アルト：冠を取り戻すためじゃない。みんなが帰れる場所を、取り戻してみせる。', after=self.autosave)
            else:
                self.say('長老：' + JOURNAL[self.stage])
        elif kind == 'inn' or kind == 'crystal':
            for h in self.party:
                h.restore()
            self.autosave()
            self.say(('宿屋：旅人はいつでも歓迎だ。今夜は村のおごりだよ。' if kind == 'inn' else '祈りの泉が、仲間全員の傷と魔力を癒やした。') + ' HP・MP全回復。旅を自動セーブした。')
        elif kind == 'shop':
            self.state, self.menu, self.choice = 'menu', 'shop', 0
        elif kind == 'villager':
            self.say('村人：泉はどこでも無料で回復してくれるよ。森にはエルフの弓使いがいる。祭壇の戦いでは、仲間の力が必要だ。',
                     '村人：敵の大技の予兆が見えたら「防御」。技「王家の光」は、倒れた仲間も助けてくれるんだって。')
        elif kind == 'chest':
            key = '%d:%d:%d' % (self.zone, x, y)
            if key in self.chests:
                self.say('宝箱は空だ。')
            else:
                self.chests.append(key)
                self.gold += 65 + self.zone * 30
                self.potions += 2
                self.say('宝箱を開けた！ 薬草 ×2 と %d G を手に入れた。' % (65 + self.zone * 30))
        elif kind == 'recruit':
            if self.zone in RECRUITS:
                n, race, line = RECRUITS[self.zone]
                if any(h.name == n for h in self.party):
                    self.say(n + '：' + line)
                else:
                    hero = Hero(n, race, level=max(2, max(h.level for h in self.party)))
                    hero.weapon, hero.armor = self.party[0].weapon, self.party[0].armor
                    hero.restore()
                    self.party.append(hero)
                    self.say(n + '：' + line, n + 'が仲間になった！ メニューの「仲間」で能力を確認できる。', after=self.autosave)
            else:
                self.say('古い碑：王の名は、民の記憶に宿る。共に歩んだ者こそ、その帰還を証す。')
        elif kind == 'boss':
            if self.zone in self.seals or self.stage == 5:
                self.say('祭壇には穏やかな光が戻っている。北の道が開かれた。')
            elif len(self.party) < min(self.zone + 1, 4):
                self.say('祭壇の結界はまだ強い。この土地の仲間に、力を借りよう。南の道に誰かが待っている。')
            else:
                self.say(['', '茨の守護獣：古き盟約を問う。あなたは、他者のために剣を取れるか。',
                          '熔炉の巨人：王の剣に、民を守る熱はあるか！',
                          '星を呑む竜：夜は終わらない。おまえたちの希望も、星と共に呑み込もう。',
                          'ヴァルド：民は王を忘れた。空の玉座に何を捧げる？\nアルト：一人では戻らなかった。それが答えだ。'][self.zone],
                         after=lambda: self.start_battle(True))
        elif kind == 'exit':
            self.travel(y < 10)

    def travel(self, north):
        if north:
            if self.zone == 4:
                self.say('この先は玉座の間。祭壇のそばで決定しよう。')
            elif self.stage <= self.zone:
                self.say('北の道はまだ開かれていない。' + JOURNAL[self.stage])
            else:
                self.change_zone(self.zone + 1)
        elif self.zone > 0:
            self.change_zone(self.zone - 1, north=True)
        else:
            self.say('南には、王家が守ってきた人々の暮らしが続いている。旅路は北へ。')

    def move(self, dx, dy):
        self.facing = (dx, dy)
        nx, ny = self.x + dx, self.y + dy
        if not 0 <= nx < MAP_W or not 0 <= ny < MAP_H or self.tiles[ny][nx] not in '.:,':
            return
        if any(ox == nx and oy == ny and k not in ('exit',) for ox, oy, k, _ in self.objects()):
            return
        self.x, self.y = nx, ny
        if ny <= 3 and 22 <= nx <= 26:
            self.travel(True)
            if self.y <= 3:
                self.y = 4
            return
        if ny >= 30 and self.zone > 0 and 22 <= nx <= 26:
            self.travel(False)
            return
        if self.zone and self.stage != 5:
            self.steps += 1
            if self.steps >= self.encounter_at:
                self.start_battle()

    def start_battle(self, boss=False):
        self.steps, self.encounter_at = 0, random.randint(25, 40)
        templates = [BOSSES[self.zone]] if boss else random.choices(ENEMIES[self.zone], k=1 if self.zone == 1 else 2)
        enemies = [dict(name=n, hp=hp, max_hp=hp, atk=atk, defense=df, kind=k) for n, hp, atk, df, k in templates]
        self.battle = dict(enemies=enemies, boss=boss, actor=0, log=['敵が現れた！'],
                           guard=[], turn=1, target=0, phase='command', action=0)
        self.state, self.choice = 'battle', 0
        self.music(self.zone, True)
        self.next_actor(-1)

    def log(self, s):
        self.battle['log'].append(s)
        self.battle['log'] = self.battle['log'][-4:]

    def next_actor(self, current):
        alive = [i for i in range(current + 1, len(self.party)) if self.party[i].hp > 0]
        self.battle['phase'] = 'command'
        self.choice = 0
        if alive:
            self.battle['actor'] = alive[0]
        else:
            self.enemy_turn()

    def battle_action(self, action, target=0):
        b = self.battle
        h = self.party[b['actor']]
        enemies = b['enemies']
        if action == 0 or (action == 1 and h.race in ('エルフ', 'ドワーフ')):
            cost = 5 if action == 1 else 0
            if h.mp < cost:
                self.toast('MPが足りない'); return
            h.mp -= cost
            e = enemies[target]
            damage = max(2, int(h.attack * (1.9 if action else 1) - e['defense']) + random.randint(-3, 4))
            e['hp'] = max(0, e['hp'] - damage)
            self.log('%sの%s！ %sに%dダメージ。' % (h.name, '技' if action else '攻撃', e['name'], damage))
            self.sound(260)
        elif action == 1:
            if h.mp < 6:
                self.toast('MPが足りない'); return
            h.mp -= 6
            if h.race == '人間':
                for ally in self.party:
                    ally.hp = min(ally.max_hp, ally.hp + 24 + h.level * 5)
                self.log('王家の光！ 全員のHPを回復。倒れた仲間も復帰！')
            else:
                for ally in self.party:
                    ally.mp = min(ally.max_mp, ally.mp + 8 + h.level)
                self.log('星の歌！ 仲間全員のMPが回復した。')
        elif action == 2:
            b['guard'].append(b['actor'])
            self.log(h.name + 'は身を守っている。次の被害を大きく軽減。')
        elif action == 3:
            if self.potions <= 0:
                self.toast('薬草がない'); return
            self.potions -= 1
            ally = self.party[target]
            ally.hp = min(ally.max_hp, ally.hp + 65)
            self.log(ally.name + 'に薬草。HPが65回復した！')
        elif action == 4:
            if self.ethers <= 0:
                self.toast('魔力の雫がない'); return
            self.ethers -= 1
            ally = self.party[target]
            ally.mp = min(ally.max_mp, ally.mp + 24)
            self.log(ally.name + 'のMPが24回復した！')
        elif action == 5:
            if b['boss']:
                self.toast('この戦いからは逃げられない'); return
            self.state = 'field'
            self.music(self.zone)
            self.toast('無事に逃げ切った。')
            return
        if all(e['hp'] <= 0 for e in enemies):
            self.victory()
        else:
            self.next_actor(b['actor'])

    def enemy_turn(self):
        b = self.battle
        for e in b['enemies']:
            if e['hp'] <= 0:
                continue
            living = [i for i, h in enumerate(self.party) if h.hp > 0]
            if not living:
                break
            heavy = b['boss'] and b['turn'] % 3 == 0
            targets = living if heavy else [random.choice(living)]
            for i in targets:
                h = self.party[i]
                damage = max(3, int(e['atk'] * (1.5 if heavy else 1)) - h.defense + random.randint(-2, 3))
                if i in b['guard']:
                    damage = max(1, damage // 4)
                h.hp = max(0, h.hp - damage)
                self.log('%sの%s → %sに%d。' % (e['name'], '全体大技' if heavy else '攻撃', h.name, damage))
        b['guard'] = []
        if all(h.hp <= 0 for h in self.party):
            self.state = 'defeat'
            self.choice = 0
        else:
            b['turn'] += 1
            b['phase'] = 'round'

    def victory(self):
        b = self.battle
        xp = (32 + self.zone * 16) if b['boss'] else (12 + self.zone * 7)
        gold = (120 + self.zone * 80) if b['boss'] else (20 + self.zone * 12)
        self.gold += gold
        lines = ['勝利！ 一人あたり経験値 %d / %d G を獲得。' % (xp, gold)]
        for h in self.party:
            levels = h.gain(xp)
            if levels:
                lines.append('%s は Lv.%d に！ HP・MPが全回復した。' % (h.name, h.level))
        if b['boss']:
            if self.zone < 4:
                self.seals.append(self.zone)
                self.stage = self.zone + 1
                self.potions += 3
                for h in self.party:
                    h.restore()
                lines += [['森', '炎', '星'][self.zone - 1] + 'の誓印を手に入れた！ 全員のHP・MPが回復。北の道が開かれた。']
            else:
                self.stage = 5
        self.state = 'field'
        self.music(self.zone)
        self.autosave()
        self.say(*lines, after=self.ending if self.stage == 5 and b['boss'] else None)

    def ending(self):
        self.state = 'ending'
        self.choice = 0

    def recover(self):
        self.gold = max(0, self.gold - self.gold // 5)
        for h in self.party:
            h.restore()
        self.state = 'field'
        self.change_zone(0)
        self.say('長老：まだ、帰る場所はここにある。何度でも立ち上がればよい。\n所持金の20%を失った。仲間・経験・誓印は失われない。')

    def open_menu(self, kind='main', origin='field'):
        self.state, self.menu, self.choice, self.menu_return = 'menu', kind, 0, origin

    def menu_options(self):
        if self.menu == 'main':
            return ['仲間と能力', '薬草で回復（%d）' % self.potions, '魔力の雫（%d）' % self.ethers,
                    '冒険手帳', 'セーブ', 'ロード', 'BGM：' + ('OFF' if self.muted else 'ON'), 'タイトルへ', '戻る']
        if self.menu in ('save', 'load'):
            opts = []
            for slot in ([1, 2, 3] if self.menu == 'save' else [0, 1, 2, 3]):
                label = '自動' if slot == 0 else '記録 %d' % slot
                try:
                    d = json.loads(self.save_path(slot).read_text(encoding='utf-8'))
                    label += '  %s / %s' % (NAMES[d['zone']], d['date'])
                except (OSError, ValueError, KeyError, TypeError, IndexError):
                    label += '  ― 記録なし'
                opts.append(label)
            return opts + ['戻る']
        if self.menu == 'shop':
            return ['薬草  25 G（HP65・戦闘不能回復）', '魔力の雫  40 G（MP24）',
                    '全員の武器を強化  %d G' % (120 + self.party[0].weapon * 100),
                    '全員の防具を強化  %d G' % (100 + self.party[0].armor * 100), '戻る']
        if self.menu in ('heal', 'ether'):
            return [h.name + '  HP %d/%d  MP %d/%d' % (h.hp, h.max_hp, h.mp, h.max_mp) for h in self.party] + ['戻る']
        return ['戻る']

    def menu_accept(self):
        c, m = self.choice, self.menu
        if c == len(self.menu_options()) - 1:
            if m == 'main' or m == 'shop' or self.menu_return == 'title':
                self.state = self.menu_return
            else:
                self.menu, self.choice = 'main', 0
            return
        if m == 'main':
            if c in (0, 1, 2, 3, 4, 5):
                self.menu = ['party', 'heal', 'ether', 'journal', 'save', 'load'][c]
                self.choice = 0
            elif c == 6:
                self.toggle_music()
            elif c == 7:
                self.autosave()
                self.state, self.choice = 'title', 0
        elif m == 'save':
            try:
                self.save(c + 1)
                self.toast('記録 %d にセーブしました' % (c + 1))
            except OSError:
                self.toast('セーブできません。フォルダの書き込み権限を確認してください。')
        elif m == 'load':
            self.load(c)
        elif m in ('heal', 'ether'):
            h = self.party[c]
            if m == 'heal' and self.potions > 0 and h.hp < h.max_hp:
                self.potions -= 1
                h.hp = min(h.max_hp, h.hp + 65)
                self.toast(h.name + 'のHPが回復した')
            elif m == 'ether' and self.ethers > 0 and h.mp < h.max_mp:
                self.ethers -= 1
                h.mp = min(h.max_mp, h.mp + 24)
                self.toast(h.name + 'のMPが回復した')
            else:
                self.toast('道具がないか、回復の必要がありません')
        elif m == 'shop':
            cost = [25, 40, 120 + self.party[0].weapon * 100, 100 + self.party[0].armor * 100][c]
            if self.gold < cost:
                self.toast('所持金が足りません'); return
            if c >= 2 and getattr(self.party[0], 'weapon' if c == 2 else 'armor') >= 5:
                self.toast('最大まで強化済みです'); return
            self.gold -= cost
            if c == 0:
                self.potions += 1
            elif c == 1:
                self.ethers += 1
            else:
                for h in self.party:
                    attr = 'weapon' if c == 2 else 'armor'
                    setattr(h, attr, getattr(h, attr) + 1)
            self.sound()
            self.toast('購入しました！')

    def toggle_music(self):
        self.muted = not self.muted
        if self.audio:
            pygame.mixer.music.set_volume(0 if self.muted else .35)

    def key(self, key):
        ok = key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
        back = key in (pygame.K_ESCAPE, pygame.K_x)
        up = key in (pygame.K_UP, pygame.K_w)
        down = key in (pygame.K_DOWN, pygame.K_s)
        if key == pygame.K_F1:
            import webbrowser
            webbrowser.open((ROOT / '使い方.html').as_uri())
            return
        if key == pygame.K_m:
            self.toggle_music(); return
        if self.dialog:
            if ok or back:
                self.advance_dialog()
            return
        if self.state == 'title':
            if up or down:
                self.choice = (self.choice + (1 if down else -1)) % 3
            if ok:
                if self.choice == 0:
                    self.new_data()
                    self.state = 'field'
                    self.say('十年前、王都の鐘は鳴るのをやめた。\n帰るべき国を失った王子は、小さな村で名を隠して生きてきた。',
                             'けれど今朝、北の森に王家の光が灯った。\nアルト：もう、待つのは終わりだ。まずは北にいる長老を訪ねよう。')
                elif self.choice == 1:
                    self.open_menu('load', 'title')
                else:
                    self.running = False
        elif self.state == 'field':
            if ok:
                self.interact()
            elif back:
                self.open_menu()
            elif key == pygame.K_TAB:
                self.state = 'map'
            elif key == pygame.K_F5:
                self.autosave(); self.toast('自動セーブ枠へ記録しました')
        elif self.state == 'map':
            if back or ok or key == pygame.K_TAB:
                self.state = 'field'
        elif self.state == 'menu':
            if up or down:
                self.choice = (self.choice + (1 if down else -1)) % len(self.menu_options())
            elif ok:
                self.menu_accept()
            elif back:
                if self.menu in ('main', 'shop') or self.menu_return == 'title':
                    self.state = self.menu_return
                else:
                    self.menu, self.choice = 'main', 0
        elif self.state == 'battle':
            b = self.battle
            if b['phase'] == 'round':
                if ok:
                    self.next_actor(-1)
            elif b['phase'] == 'target':
                targets = b['targets']
                if up or down or key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.choice = (self.choice + (1 if down or key == pygame.K_RIGHT else -1)) % len(targets)
                elif ok:
                    self.battle_action(b['action'], targets[self.choice])
                elif back:
                    b['phase'], self.choice = 'command', 0
            else:
                if up or down:
                    self.choice = (self.choice + (1 if down else -1)) % 6
                elif ok:
                    action = self.choice
                    h = self.party[b['actor']]
                    if action in (0, 3, 4) or (action == 1 and h.race in ('エルフ', 'ドワーフ')):
                        b['targets'] = ([i for i, e in enumerate(b['enemies']) if e['hp'] > 0] if action in (0, 1) else list(range(len(self.party))))
                        b['action'], b['phase'], self.choice = action, 'target', 0
                    else:
                        self.battle_action(action)
        elif self.state == 'defeat':
            if ok:
                self.recover()
        elif self.state == 'ending':
            if ok:
                self.state = 'field'
                self.say('新しい王国の物語は、ここから始まる。\nクリア後も自由に探索できます。メニューから旅を記録してください。')

    def tile(self, kind, zone):
        key = (kind, zone)
        if key in self.tile_cache:
            return self.tile_cache[key]
        s = pygame.Surface((TILE, TILE))
        a, b, c, d = PALETTES[zone]
        s.fill(a)
        rng = random.Random(zone * 120 + ord(kind))
        for _ in range(12):
            pygame.draw.rect(s, b, (rng.randrange(32), rng.randrange(32), 2, 2))
        if kind == ':':
            s.fill('#a6936b' if zone < 3 else '#85908a')
            for x, y in [(3, 5), (20, 12), (8, 25)]:
                pygame.draw.line(s, '#c0ad87' if zone < 3 else '#99aaa1', (x, y), (x + 5, y), 2)
        elif kind == '~':
            s.fill('#315c76')
            for y in (6, 19, 28):
                pygame.draw.line(s, '#518c9b', (4, y), (19, y), 2)
        elif kind == 'T':
            pygame.draw.rect(s, '#634d3b', (13, 18, 7, 14))
            pygame.draw.polygon(s, d, [(16, 0), (1, 22), (31, 22)])
            pygame.draw.polygon(s, c, [(16, 0), (3, 16), (29, 16)])
            pygame.draw.polygon(s, b, [(16, 1), (6, 10), (23, 10)])
            pygame.draw.line(s, '#8aac68', (14, 4), (9, 10), 2)
        elif kind == 'R':
            pygame.draw.polygon(s, d, [(2, 30), (3, 12), (13, 4), (26, 6), (31, 25), (27, 31)])
            pygame.draw.polygon(s, '#a1a39a', [(4, 14), (13, 5), (25, 7), (18, 13)])
            pygame.draw.line(s, c, (18, 13), (22, 28), 3)
        elif kind == 'H':
            # Building facades are drawn once over their full tile footprint.
            pass
        elif kind == ',':
            for x, y in [(7, 8), (22, 25), (26, 7)]:
                pygame.draw.line(s, c, (x, y), (x, y + 5), 2)
                pygame.draw.rect(s, '#c8b88d' if zone != 3 else '#9fbce5', (x - 1, y, 3, 3))
        self.tile_cache[key] = s
        return s

    def sprite(self, x, y, index=0, scale=2, enemy=None):
        """Draw original low-resolution sprites, then nearest-neighbor scale."""
        s = pygame.Surface((32, 40), pygame.SRCALPHA)
        r = lambda col, rect: pygame.draw.rect(s, col, rect)
        if enemy:
            col = {'slime': '#87bf86', 'wolf': '#9bafbb', 'plant': '#78976b', 'golem': '#a58e73',
                   'flame': '#e9a15e', 'ghost': '#94a8c3', 'knight': '#697b9e', 'dragon': '#8c92b1', 'king': '#b5b7ce'}[enemy]
            if enemy == 'slime':
                pygame.draw.ellipse(s, '#293d46', (1, 31, 30, 7))
                pygame.draw.ellipse(s, col, (2, 19, 28, 17))
                r('#c0e9aa', (7, 23, 5, 3))
            elif enemy in ('plant', 'dragon'):
                pygame.draw.polygon(s, col, [(15, 4), (20, 16), (31, 9), (26, 27), (30, 35), (16, 31), (2, 35), (6, 23), (0, 10), (12, 17)])
                r('#c9c399', (12, 21, 8, 13))
            elif enemy == 'wolf':
                pygame.draw.polygon(s, col, [(4, 15), (7, 5), (15, 13), (25, 5), (28, 20), (24, 34), (6, 34)])
                r('#d5dbcd', (9, 21, 15, 10))
            else:
                pygame.draw.polygon(s, col, [(9, 10), (7, 22), (2, 32), (11, 35), (20, 35), (30, 32), (24, 20), (23, 10)])
                r(col, (9, 4, 14, 13))
                if enemy in ('king', 'knight'):
                    r('#484965', (7, 18, 18, 16))
                    r('#d5bd7f', (9, 2, 14, 4))
                    for xx in (9, 15, 21):
                        r('#eedfae', (xx, 0, 2, 5))
            r('#2d2c3e', (10, 18 if enemy == 'slime' else 13, 3, 3))
            r('#2d2c3e', (20, 18 if enemy == 'slime' else 13, 3, 3))
            if enemy in ('king', 'knight'):
                r('#e78793', (11, 13, 10, 2))
        else:
            coats = ['#668db4', '#6f9c76', '#b18a5d', '#b7909e', '#a79bba', '#acb497']
            hair = ['#b59a63', '#d2d1a3', '#ab754e', '#b89464', '#d4d5cd', '#a89476']
            col = coats[index % 6]
            bob = int(self.tick * 6) % 2 if self.state == 'field' else 0
            pygame.draw.ellipse(s, '#223d46', (7, 33, 19, 5))
            r('#343d49', (10, 29 + bob, 5, 7))
            r('#343d49', (19, 29 - bob, 5, 7))
            r(col, (9, 18, 16, 14))
            r('#e0c28e', (13, 9, 11, 12))
            r(hair[index % 6], (10, 6, 15, 7))
            r(hair[index % 6], (9, 12, 5, 8))
            r('#283545', (21, 14, 2, 3))
            r('#dfc489', (9, 27, 16, 2))
            r('#e0c28e', (6, 21, 4, 7))
            if index == 0:
                r('#c1d7dc', (26, 17, 2, 14)); r('#d5b478', (23, 26, 7, 2))
            elif index == 1:
                pygame.draw.arc(s, '#d9c693', (23, 12, 8, 22), -1.5, 1.5, 2)
                r('#e0c28e', (24, 12, 5, 3))
            elif index == 2:
                r('#a36346', (12, 18, 12, 8)); r('#d3d8c6', (25, 15, 6, 9))
            elif index == 3:
                r('#adba82', (6, 4, 20, 5)); r('#b9ce92', (12, 1, 10, 4))
        s = pygame.transform.scale(s, (32 * scale, 40 * scale))
        self.canvas.blit(s, (int(x - 16 * scale), int(y - 36 * scale)))

    def camera(self):
        return max(0, min(self.x * TILE - W // 2, MAP_W * TILE - W)), max(0, min(self.y * TILE - 280, MAP_H * TILE - H))

    def field_draw(self):
        cx, cy = self.camera()
        for y in range(max(0, cy // TILE), min(MAP_H, (cy + H) // TILE + 1)):
            for x in range(max(0, cx // TILE), min(MAP_W, (cx + W) // TILE + 1)):
                self.canvas.blit(self.tile(self.tiles[y][x], self.zone), (x * TILE - cx, y * TILE - cy))
        if self.zone == 0:
            for hx, hy, label in [(9, 10, '宿屋'), (31, 10, '道具屋'), (9, 19, ''), (31, 19, '')]:
                bx, by = hx * TILE - cx, hy * TILE - cy
                pygame.draw.rect(self.canvas, '#bbaa85', (bx + 4, by + 38, 152, 58))
                pygame.draw.rect(self.canvas, '#716448', (bx + 4, by + 88, 152, 8))
                pygame.draw.polygon(self.canvas, '#4f4041', [(bx - 5, by + 43), (bx + 80, by - 11), (bx + 165, by + 43)])
                pygame.draw.polygon(self.canvas, '#95614e', [(bx - 5, by + 38), (bx + 80, by - 16), (bx + 165, by + 38)])
                for ry in range(0, 39, 8):
                    half = int((ry + 16) * 1.56)
                    pygame.draw.line(self.canvas, '#b47e5a', (bx + 80 - half, by + ry), (bx + 80 + half, by + ry), 2)
                for wx in (23, 111):
                    pygame.draw.rect(self.canvas, '#594b3e', (bx + wx, by + 53, 23, 22))
                    pygame.draw.rect(self.canvas, '#d3c184', (bx + wx + 3, by + 56, 17, 16))
                    pygame.draw.line(self.canvas, '#776849', (bx + wx + 11, by + 54), (bx + wx + 11, by + 74), 2)
                pygame.draw.rect(self.canvas, '#514537', (bx + 67, by + 55, 26, 41))
                pygame.draw.rect(self.canvas, '#9b774f', (bx + 71, by + 60, 18, 36))
                pygame.draw.rect(self.canvas, GOLD, (bx + 83, by + 78, 3, 3))
                if label:
                    self.panel((bx + 40, by + 98, 80, 26), '#413d34')
                    self.text(label, bx + 80, by + 101, 13, GOLD, True)
        things = [(y, x, kind, name) for x, y, kind, name in self.objects()]
        things += [(self.y, self.x, 'hero', '')]
        for y, x, kind, name in sorted(things):
            px, py = x * TILE + 16 - cx, y * TILE + 24 - cy
            if kind == 'hero':
                self.sprite(px, py, 0, 1)
            elif kind in ('elder', 'inn', 'shop', 'villager', 'recruit'):
                i = self.zone if kind == 'recruit' and self.zone < 4 else 4 if kind == 'elder' else 5
                self.sprite(px, py, i, 1)
            elif kind == 'chest':
                opened = '%d:%d:%d' % (self.zone, x, y) in self.chests
                pygame.draw.rect(self.canvas, '#473c39', (px - 12, py - 18, 24, 19))
                pygame.draw.rect(self.canvas, '#b18b56', (px - 11, py - (23 if opened else 18), 22, 9))
                pygame.draw.rect(self.canvas, GOLD, (px - 2, py - 12, 4, 6))
            elif kind == 'crystal':
                pygame.draw.ellipse(self.canvas, '#adb5a3', (px - 17, py - 4, 34, 13))
                offset = math.sin(self.tick * 2) * 3
                pygame.draw.polygon(self.canvas, '#a9e4cf', [(px, py - 31 + offset), (px + 9, py - 17 + offset), (px, py - 5 + offset), (px - 9, py - 17 + offset)])
            elif kind == 'boss':
                pygame.draw.rect(self.canvas, '#4e5668', (px - 23, py - 8, 46, 15))
                self.sprite(px, py - 4, scale=1, enemy=BOSSES[self.zone][4])
            elif kind == 'exit':
                self.text('↑ 北へ' if y < 10 else '↓ 南へ', px, py - 15, 13, GOLD, True)
            if kind != 'hero' and abs(x - self.x) + abs(y - self.y) <= 2:
                self.panel((px - 60, py - 60, 120, 24))
                self.text(name, px, py - 58, 12, GOLD, True)
        self.panel((18, 16, 285, 69))
        self.text(NAMES[self.zone], 34, 24, 22)
        self.text(SUBTITLES[self.zone], 35, 57, 11, GOLD)
        self.panel((650, 16, 292, 69))
        self.text('誓印  %s   /   %d G' % ('◆' * len(self.seals) + '◇' * (3 - len(self.seals)), self.gold), 668, 28, 17, GOLD)
        self.text('Esc 手帳   Z 調べる   Tab 地図   F1 ヘルプ', 668, 58, 11, MUTED)
        self.panel((18, 568, 924, 56))
        for i, h in enumerate(self.party):
            x = 34 + i * 225
            self.text('%s  Lv.%d' % (h.name, h.level), x, 575, 16)
            self.bar(x, 604, 125, h.hp, h.max_hp, '#8ec7a0')
            self.text('%d/%d' % (h.hp, h.max_hp), x + 132, 596, 12, MUTED)

    def bar(self, x, y, width, value, maximum, color):
        pygame.draw.rect(self.canvas, '#293746', (x, y, width, 6))
        pygame.draw.rect(self.canvas, color, (x, y, int(width * max(0, min(1, value / maximum))), 6))

    def title_draw(self):
        self.canvas.fill('#142c3a')
        for i in range(65):
            x, y = (i * 151 + 31) % W, (i * 73) % 330
            pygame.draw.rect(self.canvas, '#a8bdc1' if i % 3 else '#e0d5a7', (x, y, 2, 2))
        pygame.draw.circle(self.canvas, '#dacfa6', (740, 122), 44)
        pygame.draw.circle(self.canvas, '#142c3a', (725, 110), 40)
        for layer, color in enumerate(['#294453', '#213c49', '#19313d']):
            pts = [(0, 500)] + [(x, 315 + layer * 50 + int(math.sin(x / 110 + layer) * 60)) for x in range(0, W + 1, 20)] + [(W, H), (0, H)]
            pygame.draw.polygon(self.canvas, color, pts)
        for x, height in [(390, 95), (440, 130), (490, 112), (540, 85)]:
            pygame.draw.rect(self.canvas, '#102936', (x, 410 - height, 30, height))
            pygame.draw.polygon(self.canvas, '#102936', [(x - 5, 410 - height), (x + 15, 385 - height), (x + 35, 410 - height)])
        self.text('T H E   R E T U R N   O F   T H E   K I N G', W // 2, 106, 18, GOLD, True)
        self.text('王の帰還', W // 2, 148, 64, WHITE, True)
        self.text('四つの種族。三つの誓い。一つの帰る場所。', W // 2, 242, 17, '#b2c6c9', True)
        self.panel((315, 383, 330, 156), '#122632')
        for i, label in enumerate(['はじめから', '旅のつづき', '終了']):
            self.text(('▸  ' if self.choice == i else '    ') + label, 480, 401 + i * 42, 21, GOLD if self.choice == i else WHITE, True)
        for i in range(4):
            self.sprite(410 + i * 47, 364, i, 1)
        self.text('↑↓ 選択   Enter / Z 決定   F1 使い方   M BGM', 480, 580, 14, MUTED, True)

    def battle_draw(self):
        b = self.battle
        self.canvas.fill(PALETTES[self.zone][3])
        for y in range(0, 365, 32):
            for x in range(0, W, 32):
                self.canvas.blit(self.tile(('R' if self.zone in (2, 4) else 'T') if y < 120 else '.' if y < 300 else ':', self.zone), (x, y))
        if self.zone == 4:
            pygame.draw.rect(self.canvas, '#354657', (0, 0, W, 100))
            for px in range(30, W, 160):
                pygame.draw.rect(self.canvas, '#92a0a0', (px, 0, 25, 178))
                pygame.draw.rect(self.canvas, '#c1c1a9', (px - 5, 158, 35, 20))
                pygame.draw.rect(self.canvas, '#596e7c', (px + 18, 0, 7, 158))
        shade = pygame.Surface((W, 365), pygame.SRCALPHA)
        shade.fill((10, 18, 35, 75))
        self.canvas.blit(shade, (0, 0))
        self.text('BATTLE / %s' % NAMES[self.zone], 25, 18, 17, GOLD)
        self.text('TURN %02d' % b['turn'], 890, 18, 17, GOLD, True)
        for i, e in enumerate(b['enemies']):
            if e['hp'] <= 0:
                continue
            x, y = 185 + i * 210, 265 + i * 15
            scale = 4 if b['boss'] else 3
            self.sprite(x, y + math.sin(self.tick * 2 + i) * 3, scale=scale, enemy=e['kind'])
            self.text(e['name'], x, 95 if b['boss'] else 135, 17, WHITE, True)
            self.bar(x - 65, 125 if b['boss'] else 165, 130, e['hp'], e['max_hp'], '#df9b91')
            if b['phase'] == 'target' and b['action'] in (0, 1) and b['targets'][self.choice] == i:
                self.text('▼', x, 65 if b['boss'] else 105, 22, GOLD, True)
        for i, h in enumerate(self.party):
            self.sprite(705 + (i % 2) * 110, 220 + (i // 2) * 92, i, 2)
        self.panel((18, 365, 924, 94))
        for i, h in enumerate(self.party):
            x = 34 + i * 228
            active = b['actor'] == i and b['phase'] != 'round'
            self.text(('▸' if active else '') + h.name + (' [倒]' if h.hp == 0 else ''), x, 373, 17, GOLD if active else WHITE)
            self.text('HP %d / %d' % (h.hp, h.max_hp), x, 400, 14)
            self.bar(x, 426, 174, h.hp, h.max_hp, '#8ec7a0')
            self.text('MP %d / %d' % (h.mp, h.max_mp), x, 435, 12, '#a8bfe0')
        self.panel((18, 470, 298, 154))
        if b['phase'] == 'round':
            self.wrapped('次のターンへ\nEnter / Z', 40, 500, 250, 20, GOLD)
        elif b['phase'] == 'target':
            self.text('対象を選択  ↑↓ / ←→', 34, 481, 16, GOLD)
            for j, target in enumerate(b['targets']):
                name = b['enemies'][target]['name'] if b['action'] in (0, 1) else self.party[target].name
                self.text(('▸ ' if self.choice == j else '   ') + name, 34, 511 + j * 24, 15)
        else:
            h = self.party[b['actor']]
            skill = {'人間': '王家の光 6MP', 'エルフ': '風の矢 5MP', 'ドワーフ': '砕岩撃 5MP', 'ハーフフット': '星の歌 6MP'}[h.race]
            labels = ['攻撃', skill, '防御', '薬草 ×%d' % self.potions, '魔力の雫 ×%d' % self.ethers, '逃げる']
            for i, label in enumerate(labels):
                self.text(('▸ ' if self.choice == i else '   ') + label, 30, 480 + i * 22, 15, GOLD if self.choice == i else WHITE)
        self.panel((328, 470, 614, 154))
        for i, line in enumerate(b['log']):
            self.text(line, 343, 481 + i * 27, 15)
        if b['boss'] and b['turn'] % 3 == 0:
            self.text('予兆：次は全体大技。防御で耐えよう！', 344, 599, 14, '#ebbd89')

    def menu_draw(self):
        self.field_draw() if self.menu_return != 'title' else self.title_draw()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 13, 24, 190))
        self.canvas.blit(veil, (0, 0))
        self.panel((100, 62, 760, 515))
        title = {'main': '旅の記録', 'party': '四つの種族 / 仲間', 'heal': '薬草を使う', 'ether': '魔力の雫を使う',
                 'journal': '冒険手帳', 'save': 'セーブ / 枠を選択すると上書き', 'load': 'ロード / 枠を選択', 'shop': '道具屋 / %d G' % self.gold}[self.menu]
        self.text(title, 130, 84, 25, GOLD)
        pygame.draw.line(self.canvas, '#526675', (130, 125), (825, 125))
        if self.menu == 'party':
            for i, h in enumerate(self.party):
                y = 147 + i * 86
                self.sprite(158, y + 48, i, 1)
                self.text('%s / %s  Lv.%d' % (h.name, h.race, h.level), 194, y, 19)
                self.text('HP %d/%d   MP %d/%d   攻撃 %d   防御 %d' % (h.hp, h.max_hp, h.mp, h.max_mp, h.attack, h.defense), 194, y + 30, 16)
                self.text('次のLvまで %d EXP   武器 +%d / 防具 +%d' % (h.level * 35 - h.xp, h.weapon, h.armor), 194, y + 55, 13, MUTED)
        elif self.menu == 'journal':
            self.text('CHAPTER %02d  /  誓印 %d / 3' % (min(5, self.stage + 1), len(self.seals)), 133, 150, 17, MUTED)
            self.wrapped(JOURNAL[self.stage], 133, 196, 660, 23)
            self.wrapped('旅の知恵：泉と宿屋は無料。全滅しても経験と誓印は残る。ボスの大技は3ターンごと。南へ戻れば、いつでも村で買い物ができる。', 133, 305, 660, 18, MUTED)
            self.text('プレイ時間 %d 分 / 薬草 %d / 魔力の雫 %d' % (self.playtime // 60, self.potions, self.ethers), 133, 444, 16)
        else:
            for i, label in enumerate(self.menu_options()):
                self.text(('▸  ' if self.choice == i else '    ') + label, 134, 145 + i * (39 if self.menu != 'main' else 40), 18, GOLD if self.choice == i else WHITE)
        self.text('↑↓ 選択   Enter / Z 決定   Esc / X 戻る', 132, 541, 14, MUTED)
        if self.menu in ('party', 'journal'):
            self.text('Enter / Esc で戻る', 700, 504, 13, GOLD, True)

    def ending_draw(self):
        self.canvas.fill('#1d3947')
        for i in range(90):
            pygame.draw.rect(self.canvas, '#97afa8', ((i * 137) % W, (i * 57) % H, 2, 2))
        self.text('王の帰還', W // 2, 70, 48, GOLD, True)
        lines = ['空の玉座に、四つの影が並んだ。', '王子と、森の弓使いと、山の鍛冶師と、小さな旅人。',
                 'アルトは冠を掲げず、城の門を開いた。', '「ここは、みんなが帰る場所だ。」', '',
                 '十年ぶりに、王都の鐘が鳴った。']
        for i, line in enumerate(lines):
            self.text(line, W // 2, 166 + i * 38, 20, WHITE, True)
        for i in range(4):
            self.sprite(365 + i * 78, 487, i, 2)
        self.text('THE END  /  Thank you for playing', W // 2, 523, 18, GOLD, True)
        self.text('Enter / Z：クリア後の世界へ', W // 2, 580, 15, MUTED, True)

    def map_draw(self):
        self.canvas.fill(INK)
        self.text(NAMES[self.zone] + ' / 旅路の地図', 36, 22, 26, GOLD)
        ox, oy, size = 30, 91, 13
        for y, row in enumerate(self.tiles):
            for x, tile in enumerate(row):
                col = {'.': '#557453', ',': '#557453', ':': '#bcad83', 'T': '#284c40',
                       'R': '#414c59', 'H': '#a17863', '~': '#396c87'}[tile]
                pygame.draw.rect(self.canvas, col, (ox + x * size, oy + y * size, size - 1, size - 1))
        for x, y, kind, name in self.objects():
            col = '#91d9d0' if kind == 'crystal' else '#e0bf80'
            pygame.draw.circle(self.canvas, col, (ox + x * size + 6, oy + y * size + 6), 5)
        pygame.draw.circle(self.canvas, '#ffffff', (ox + self.x * size + 6, oy + self.y * size + 6), 6)
        self.text('白：現在地  /  水色：回復の泉', 36, 550, 16, WHITE)
        self.text('北 ↑    Tab / Esc / Z で戻る', 36, 585, 16, MUTED)
        self.text('LANDMARKS', 690, 98, 17, GOLD)
        for i, (_, _, kind, name) in enumerate(self.objects()):
            self.text(name, 690, 140 + i * 30, 16, '#91d9d0' if kind == 'crystal' else WHITE)
        self.wrapped(JOURNAL[self.stage], 690, 440, 230, 16, GOLD)

    def draw(self):
        if self.state == 'title':
            self.title_draw()
        elif self.state == 'battle':
            self.battle_draw()
        elif self.state == 'menu':
            self.menu_draw()
        elif self.state == 'map':
            self.map_draw()
        elif self.state == 'ending':
            self.ending_draw()
        elif self.state == 'defeat':
            self.battle_draw()
            self.panel((200, 180, 560, 150))
            self.text('灯は、まだ消えていない', 480, 204, 28, GOLD, True)
            self.text('Enter / Z：村へ戻る（所持金 −20%）', 480, 270, 18, WHITE, True)
        else:
            self.field_draw()
        if self.dialog:
            self.panel((30, 427, 900, 195), '#142335', GOLD)
            self.wrapped(self.dialog[0], 57, 449, 840, 21)
            self.text('Z / Enter  ▼', 880, 589, 13, GOLD, True)
        if self.notice_time > 0:
            self.panel((80, 97, 800, 45))
            self.text(self.notice, 480, 108, 16, GOLD, True)
        sw, sh = self.screen.get_size()
        factor = min(sw / W, sh / H)
        nw, nh = int(W * factor), int(H * factor)
        self.screen.fill('#080e18')
        self.screen.blit(pygame.transform.scale(self.canvas, (nw, nh)), ((sw - nw) // 2, (sh - nh) // 2))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(.1, self.clock.tick(60) / 1000)
            self.tick += dt
            self.notice_time -= dt
            self.move_timer -= dt
            if self.state != 'title':
                self.playtime += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    if self.state in ('field', 'menu', 'ending', 'map') and self.menu_return != 'title':
                        self.autosave()
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.key(event.key)
            if self.state == 'field' and not self.dialog and self.move_timer <= 0:
                keys = pygame.key.get_pressed()
                dx = int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - int(keys[pygame.K_LEFT] or keys[pygame.K_a])
                dy = int(keys[pygame.K_DOWN] or keys[pygame.K_s]) - int(keys[pygame.K_UP] or keys[pygame.K_w])
                if dx or dy:
                    self.move(dx, 0) if dx else self.move(0, dy)
                    self.move_timer = .095 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else .15
            self.draw()
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description='王の帰還 / The Return of the King')
    parser.add_argument('--smoke-test', action='store_true', help='Render a frame without playing')
    args = parser.parse_args()
    game = Game(headless=args.smoke_test)
    if args.smoke_test:
        game.draw()
        print('OK: title rendered; maps=%d; pygame=%s' % (len(NAMES), pygame.version.ver))
        pygame.quit()
    else:
        game.run()


if __name__ == '__main__':
    main()
