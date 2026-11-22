"""Campaign and persistence regression checks. Run: python -m unittest -v"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import json
import random
import tempfile
import unittest
from collections import deque
from pathlib import Path

import pygame
from main import Game
from world import Hero, make_map, SPAWNS, RECRUITS, MAP_W, MAP_H


class CampaignTests(unittest.TestCase):
    def setUp(self):
        random.seed(42)
        self.tmp = tempfile.TemporaryDirectory()
        self.g = Game(headless=True)
        self.g.save_path = lambda slot: Path(self.tmp.name) / ('slot%d.json' % slot)
        self.g.state = 'field'

    def tearDown(self):
        pygame.quit()
        self.tmp.cleanup()

    def test_every_landmark_is_reachable(self):
        for zone in range(5):
            self.g.zone = zone
            tiles = make_map(zone)
            blocked = {(x, y) for x, y, kind, _ in self.g.objects() if kind != 'exit'}
            visited = {SPAWNS[zone]}
            queue = deque(visited)
            while queue:
                x, y = queue.popleft()
                for p in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                    nx, ny = p
                    if 0 <= nx < MAP_W and 0 <= ny < MAP_H and tiles[ny][nx] in '.:,' and p not in blocked and p not in visited:
                        visited.add(p)
                        queue.append(p)
            for x, y, kind, name in self.g.objects():
                self.assertTrue(any(abs(px - x) + abs(py - y) <= 1 for px, py in visited), (zone, name))
            self.assertIn((24, 3), visited)
            self.assertIn((24, 30), visited)

    def test_save_roundtrip_and_corrupt_file(self):
        g = self.g
        g.gold, g.stage = 789, 2
        g.party[0].gain(100)
        g.save(1)
        g.new_data()
        self.assertTrue(g.load(1))
        self.assertEqual((g.gold, g.stage, g.party[0].level), (789, 2, 2))
        g.save_path(2).write_text('{broken', encoding='utf-8')
        self.assertFalse(g.load(2))
        self.assertEqual(g.gold, 789)

    def test_progression_and_complete_campaign(self):
        g = self.g
        g.x, g.y = 24, 6
        g.interact()
        self.assertEqual(g.stage, 1)
        g.dialog = []
        for zone in range(1, 5):
            g.change_zone(zone)
            if zone < 4:
                g.x, g.y = 24, 24
                g.interact()
                self.assertEqual(len(g.party), zone + 1)
                g.dialog = []
            # Three normal encounters per region: exercise growth and combat.
            for _ in range(3):
                for h in g.party:
                    h.restore()
                g.start_battle()
                self.win_battle()
                g.dialog = []
            for h in g.party:
                h.restore()
            g.start_battle(True)
            self.win_battle()
            while g.dialog:
                g.advance_dialog()
            self.assertEqual(g.stage, zone + 1)
        self.assertEqual(g.state, 'ending')
        self.assertEqual(g.seals, [1, 2, 3])
        g.draw()

    def win_battle(self):
        g = self.g
        for _ in range(400):
            if g.state != 'battle':
                self.assertNotEqual(g.state, 'defeat')
                return
            b = g.battle
            if b['phase'] == 'round':
                g.next_actor(-1)
                continue
            h = g.party[b['actor']]
            enemy = next(i for i, e in enumerate(b['enemies']) if e['hp'] > 0)
            if h.race == '人間' and h.mp >= 6 and any(a.hp < a.max_hp * .7 for a in g.party):
                g.battle_action(1)
            elif h.race == 'ハーフフット' and h.mp >= 6 and g.party[0].mp < 12:
                g.battle_action(1)
            elif b['boss'] and b['turn'] % 3 == 0:
                g.battle_action(2)
            elif h.race in ('エルフ', 'ドワーフ') and h.mp >= 5:
                g.battle_action(1, enemy)
            elif any(a.hp < a.max_hp * .3 for a in g.party) and g.potions:
                target = min(range(len(g.party)), key=lambda i: g.party[i].hp / g.party[i].max_hp)
                g.battle_action(3, target)
            else:
                g.battle_action(0, enemy)
        self.fail('Battle did not finish')

    def test_revive_defeat_and_ui_states(self):
        g = self.g
        g.party.append(Hero('リーフ', 'エルフ', hp=0))
        g.zone = 1
        g.start_battle()
        g.battle_action(1)
        self.assertGreater(g.party[1].hp, 0)
        for state in ['field', 'title', 'battle', 'defeat', 'ending', 'map']:
            g.state = state
            g.draw()
        for menu in ['main', 'party', 'journal', 'save', 'load', 'shop', 'heal', 'ether']:
            g.open_menu(menu)
            g.draw()
        g.gold = 100
        g.recover()
        self.assertEqual(g.gold, 80)
        self.assertTrue(all(h.hp == h.max_hp for h in g.party))

    def test_keyboard_menu_targeting_and_boss_gate(self):
        g = self.g
        g.key(pygame.K_ESCAPE)
        self.assertEqual(g.state, 'menu')
        g.choice = 4
        g.key(pygame.K_RETURN)
        self.assertEqual(g.menu, 'save')
        g.key(pygame.K_RETURN)
        self.assertTrue(g.save_path(1).exists())
        g.key(pygame.K_ESCAPE)
        g.key(pygame.K_ESCAPE)
        g.key(pygame.K_TAB)
        self.assertEqual(g.state, 'map')
        g.key(pygame.K_TAB)
        g.zone, g.x, g.y = 1, 24, 6
        g.interact()
        self.assertTrue(g.dialog)
        self.assertEqual(g.state, 'field')
        g.dialog = []
        g.start_battle()
        initial = g.battle['enemies'][0]['hp']
        g.key(pygame.K_RETURN)
        self.assertEqual(g.battle['phase'], 'target')
        g.key(pygame.K_RETURN)
        self.assertLess(g.battle['enemies'][0]['hp'], initial)


if __name__ == '__main__':
    unittest.main()
