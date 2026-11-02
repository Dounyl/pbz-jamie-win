"""Run Lua 5.4 behavior tests and parse every production Lua file."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local' / 'cache' / 'testdeps'))
from lupa.lua54 import LuaRuntime


class LuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('package.path = ... .. ";" .. package.path',
                         str(ROOT / 'mods' / 'JamieWin' / 'Scripts' / '?.lua').replace('\\', '/'))

    def test_production_syntax(self):
        for path in (ROOT / 'mods').rglob('*.lua'):
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
            assert(c:executionStarted('execution-1',good), 'play at activation without waiting for a kill')
            assert(not c:executionStarted('execution-1',good), 'inherited activation hooks must not replay')
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

    def test_autostart_launches_executable_without_command_shell(self):
        self.lua.execute('''
            local Autostart=require('autostart')
            local original=io.open
            local found,opened,launched=true,nil,nil
            io.open=function(path,mode)
                opened=path;assert(mode=='rb')
                if found then return {close=function()end} end
            end
            local system={LaunchURL=function(_,path)launched=path end}
            local function find(path)
                assert(path=='/Script/Engine.Default__KismetSystemLibrary');return system end
            assert(Autostart.start('C:/Games/Space & Quotes/JamieWin',function()return true end,find)=='started')
            assert(launched==opened and launched:match('JamieWin.Audio.exe$'))
            launched=nil;found=false
            assert(Autostart.start('C:/missing',function()return true end,find)=='missing')
            assert(launched==nil)
            io.open=original
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

    def test_music_handoff_never_restores_before_stop(self):
        self.lua.execute('''
            local Lease=require('music_lease')
            local mutes,restores=0,0
            local lease=Lease.new(function()mutes=mutes+1;return true end,
                function()restores=restores+1;return true end,'game1')
            local function request(seq,time,mode)
                return {session='game1',sequence=seq,time=time,id='req1',mode=mode}
            end
            assert(lease:update(true,request(1,100,'want'),100)=='-')
            assert(lease:update(true,request(2,100,'want'),100)=='req1')
            assert(mutes==1 and restores==0)
            assert(lease:update(false,request(3,100,'want'),100)=='-')
            assert(restores==0, 'revoking grant must wait for the companion to stop')
            lease:update(false,nil,101)
            assert(restores==0, 'a partial heartbeat must not unmute under playing audio')
            lease:update(false,request(4,101,'idle'),101)
            assert(restores==1 and not lease.muted)
        ''')

    def test_missing_media_failed_mute_and_crash_recovery(self):
        self.lua.execute('''
            local Lease=require('music_lease')
            local restores=0
            local l=Lease.new(function()return true end,function()restores=restores+1;return true end,'g')
            l:update(true,{session='g',sequence=1,time=100,id='r',mode='idle'},100)
            assert(not l.muted, 'missing media sends idle, so original music remains')
            l:update(true,{session='g',sequence=2,time=100,id='r',mode='want'},100)
            l:update(true,nil,104)
            assert(restores==1 and not l.muted, 'dead companion must release music')
            local failed=Lease.new(function()return false end,function()error('unexpected restore')end,'g')
            for i=1,3 do assert(failed:update(true,{session='g',sequence=i,time=100,id='r',mode='want'},100)=='-') end
            assert(not failed.muted)
        ''')

    def test_protocol_rejects_partial_wrong_session_and_stale(self):
        self.lua.execute('''
            local Lease=require('music_lease')
            assert(not Lease.parse('JWA2|g|1|100|r|want|EN'))
            assert(not Lease.parse('JWA2|g|1|100|r|bogus|END\\n'))
            assert(Lease.parse('JWA2|g|1|100|r|want|END\\n').mode=='want')
            local l=Lease.new(function()error('must not mute')end,function()return true end,'g')
            l:update(true,{session='old',sequence=1,time=100,id='r',mode='want'},100)
            l:update(true,{session='g',sequence=1,time=90,id='r',mode='want'},100)
            assert(not l.muted)
        ''')

    def test_audio_thread_delay_and_confirmation_timeout(self):
        self.lua.execute('''
            local Lease=require('music_lease')
            local rtpc, writes, restores = 1, 0, 0
            local l=Lease.new(function() writes=writes+1; return true end,
                function() restores=restores+1; rtpc=1; return true end,'g',
                function() return rtpc==0 end)
            local function req(n,t,mode)
                return {session='g',sequence=n,time=t,id='r',mode=mode or 'want'}
            end
            assert(l:update(true,req(1,100),100)=='-')
            assert(l:update(true,req(2,100),100)=='-')
            assert(writes==1 and restores==0, 'must wait without undoing the queued mute')
            rtpc=0 -- audio thread has now processed the pending write
            assert(l:update(true,req(3,101),101)=='r')
            l:update(false,req(4,101,'idle'),101)
            assert(restores==1 and rtpc==1)
            assert(l:update(true,req(5,102),102)=='-')
            assert(l:update(true,req(6,105),105)=='-')
            assert(restores==2 and not l.muted, 'unconfirmed mute must time out and restore')
            l:update(true,req(7,106),106)
            assert(writes==2, 'failed confirmation must back off instead of toggling every frame')
        ''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
