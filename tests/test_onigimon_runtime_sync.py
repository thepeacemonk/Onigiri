import ast
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from pathlib import Path

source = ast.parse((Path(__file__).resolve().parents[1] / 'gamification' / 'onigimon.py').read_text())
bridge = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'AnkimonBridge')
methods = [n for n in bridge.body if isinstance(n, ast.FunctionDef) and n.name in ('_get_main_runtime_hp', '_update_runtime_main_object')]
namespace = {'sys': sys, 'mw': SimpleNamespace(ankimon_db=None)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + methods, type_ignores=[])), '<bridge>', 'exec'), namespace)

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.pokemon = SimpleNamespace(individual_id='test', hp=0, current_hp=0, max_hp=30, xp=5, base_stats={'def':65}, calculate_max_hp=lambda:30, _update_battle_stats=Mock())
        self.tracker=SimpleNamespace(update_gui=Mock())
        self.singletons=SimpleNamespace(main_pokemon=self.pokemon, ankimon_tracker_obj=self.tracker)
        self.bridge=SimpleNamespace(addon_id='1908235722', _pokemon_identity=lambda d:d['individual_id'])
    def test_numeric_package_reads_live_fainted_hp(self):
        with patch.dict(sys.modules, {'1908235722.singletons':self.singletons, 'Ankimon.singletons':None}):
            self.assertEqual(namespace['_get_main_runtime_hp'](self.bridge), {'current_hp':0,'max_hp':30})
    def test_legacy_package_still_supported(self):
        with patch.dict(sys.modules, {'1908235722.singletons':None, 'Ankimon.singletons':self.singletons}):
            self.assertEqual(namespace['_get_main_runtime_hp'](self.bridge)['max_hp'],30)
    def test_feed_updates_live_pokemon_and_refreshes(self):
        with patch.dict(sys.modules, {'1908235722.singletons':self.singletons, 'Ankimon.singletons':None}):
            namespace['_update_runtime_main_object'](self.bridge, {'individual_id':'test','base_stats':{'def':80},'xp':55,'current_hp':10})
        self.assertEqual((self.pokemon.hp,self.pokemon.current_hp,self.pokemon.xp,self.pokemon.base_stats['def']),(10,10,55,80))
        self.pokemon._update_battle_stats.assert_called_once()
        self.tracker.update_gui.assert_called_once()
    def test_feed_updates_cached_engine_without_resetting_opponent(self):
        fields = dict(hp=30, maxhp=30, attack=15, defense=23,
                      special_attack=16, special_defense=19, speed=14)
        fresh = SimpleNamespace(id='squirtle', **fields)
        self.pokemon.to_poke_engine_Pokemon = lambda: fresh
        cached = SimpleNamespace(id='squirtle', hp=12, maxhp=20, defense_boost=2)
        opponent = SimpleNamespace(hp=0)
        engine = SimpleNamespace(user=SimpleNamespace(active=cached),
                                 opponent=SimpleNamespace(active=opponent))
        battle = SimpleNamespace(_state=SimpleNamespace(new_state=engine))
        with patch.dict(sys.modules, {'1908235722.singletons': self.singletons,
                                     '1908235722.battle_loop': battle}):
            namespace['_update_runtime_main_object'](self.bridge, {
                'individual_id': 'test', 'current_hp': 30})
        self.assertEqual((cached.hp, cached.maxhp, cached.defense), (30, 30, 23))
        self.assertEqual(cached.defense_boost, 2)
        self.assertIs(engine.opponent.active, opponent)
        self.assertEqual(opponent.hp, 0)

    def test_battle_damage_is_read_from_live_hp_not_saved_hp(self):
        with patch.dict(sys.modules, {'1908235722.singletons': self.singletons}):
            self.pokemon.hp = 7
            self.pokemon.current_hp = 7
            hp = namespace['_get_main_runtime_hp'](self.bridge)
        self.assertEqual(hp, {'current_hp': 7, 'max_hp': 30})

    def test_other_pokemon_is_unchanged(self):
        with patch.dict(sys.modules, {'1908235722.singletons':self.singletons}):
            namespace['_update_runtime_main_object'](self.bridge, {'individual_id':'other','current_hp':10})
        self.assertEqual(self.pokemon.hp,0)
        self.tracker.update_gui.assert_not_called()

if __name__ == '__main__': unittest.main()
