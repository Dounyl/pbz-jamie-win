"""Run Lua 5.4 behavior tests and parse every production Lua file."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'probes/JamieWinNativeAudioTest/Scripts'
sys.path.insert(0, str(ROOT / '.local' / 'cache' / 'testdeps'))
from lupa.lua54 import LuaRuntime


class LuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('package.path = ... .. ";" .. package.path',
                         str(SCRIPTS / '?.lua').replace('\\', '/'))

    def test_production_syntax(self):
        for path in SCRIPTS.glob('*.lua'):
            self.lua.execute('assert(load(...))', path.read_text(encoding='utf-8'))

    def test_drink_transition_dedup_and_reentry(self):
        self.lua.execute('''
            local c = require('core').new()
            c:observe('p1', true, 'sober')
            c:observe('p1', true, 'tipsy')
            assert(c.heavy == 0 and c.state == 'tipsy')
            c:observe('p1', true, 'drunk')
            for i=1,100 do c:observe('p1', true, 'drunk') end
            assert(c.heavy == 1)
            c:observe('p1', true, 'unknown')
            c:observe('p1', true, 'drunk')
            assert(c.heavy == 1, 'a transient read failure must not replay the cue')
            c:observe('p1', true, 'tipsy')
            c:observe('p1', true, 'drunk')
            assert(c.heavy == 2)
            c:observe('p1', false, 'drunk')
            assert(c.state == 'unknown', 'death must not keep music active')
        ''')

    def test_execution_start_acceptance_and_dedup(self):
        self.lua.execute('''
            local c = require('core').new()
            local good = {local_player=true, drunk_sword=true, target_was_alive=true}
            for _,field in ipairs({'local_player','drunk_sword','target_was_alive'}) do
                good[field] = false
                assert(not c:executionStarted(field,good))
                good[field] = true
            end
            assert(c:executionStarted('execution-1',good), 'play at execution start without waiting for a kill')
            assert(not c:executionStarted('execution-1',good), 'inherited start hooks must not replay')
            assert(c:executionStarted('execution-2',good))
            assert(c.wins==2)
        ''')

    def test_track_priority_weapon_changes_and_death(self):
        self.lua.execute('''
            local c = require('core').new()
            c:observe('p',true,'sober',false); assert(c.track=='none')
            c:observe('p',true,'sober',true); assert(c.track=='armed')
            c:observe('p',true,'tipsy',true); assert(c.track=='drunk' and c.heavy==0)
            c:observe('p',true,'drunk',true); assert(c.track=='drunk' and c.heavy==1)
            c:observe('p',true,'tipsy',false); assert(c.track=='drunk')
            c:observe('p',true,'sober',true); assert(c.track=='armed')
            c:observe('p',true,'sober',false); assert(c.track=='none')
            c:observe('p',false,'drunk',true); assert(c.track=='none')
            c:observe('new-player',true,'unknown',true); assert(c.track=='none')
        ''')

    def test_weapon_detection_uses_active_index_and_armed_flag(self):
        self.lua.execute('''
            local Weapon=require('weapon')
            local function fname(name) return {ToString=function()return name end} end
            local function config(name)
                return {IsValid=function()return true end,GetFName=function()return fname(name)end}
            end
            local index,armed=0,true
            local slot={TagName=fname('Slot.Main')}
            local data={Weapons={{WeaponConfig=config('OtherSword')},
                {WeaponConfig=config('Weapon_Hun_ChiZheZuiJian')}}}
            local component={IsValid=function()return true end,
                GetCurrentWeaponIndex=function(_,s,withPending)
                    assert(s==slot and withPending==false);return index end,
                IsArmed=function()return armed end,
                RuntimeWeaponData={ForEach=function(_,callback)
                    callback({get=function()return slot end},{get=function()return data end}) end}}
            local pawn={['Character Weapons Component']=component}
            local function valid(obj)return obj~=nil and obj:IsValid()end
            local function held()return Weapon.held(pawn,'Weapon_Hun_ChiZheZuiJian',valid)end
            assert(not held(),'carrying the sword in an inactive slot must not start music')
            index=1; assert(held())
            armed=false; assert(not held(),'sheathed sword must not count as held')
            armed=true;index=-1;assert(not held())
            pawn['Character Weapons Component']=nil;assert(not held())
        ''')

if __name__ == '__main__':
    unittest.main(verbosity=2)
