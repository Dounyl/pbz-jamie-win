"""Offline transport/ownership/event checks; real PCM and device checks are separate."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/cache/testdeps'))
from lupa.lua54 import LuaRuntime
PROBE = ROOT / 'probes/JamieWinNativeAudioTest/Scripts'
SHARED = ROOT / 'mods/JamieWin/Scripts'


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('modules={}')
    for name in ('probe_settings', 'native_audio', 'game_audio', 'executions', 'gameplay', 'core', 'weapon', 'settings'):
        path = (SHARED if name in ('core', 'weapon', 'settings') else PROBE) / (name + '.lua')
        lua.execute('local n,s=...;modules[n]=assert(load(s))()', name, path.read_text(encoding='utf-8'))
    return lua


class NativeAudioProbeTests(unittest.TestCase):
    def setUp(self):
        self.lua = runtime()
        self.lua.execute(r'''
            now,loads,beats,stops,applies,starts,drinks,wins=100,0,0,0,0,0,0,0
            messages,history,events={}, {}, {}
            status,hasStatus={},false
            function log(s)messages[#messages+1]=s end
            function logs()return table.concat(messages,'\n')end
            function valid(o)return o~=nil and o.Valid==true end
            owner={Valid=true,IsValid=function(self)return self.Valid end}
            state={active=true,owner=owner,controller={},player='pawn-1',track='none',state='sober',
                paused=false,heavy=0,wins=0,detail='test'}
            local core=modules.core.new()
            function gameplay(alive,drunk,held,player)
                state.active=alive;state.player=player or state.player;state.state=drunk or 'sober'
                core:observe(state.player,alive,state.state,held)
                state.track=core.track;state.heavy=core.heavy
            end
            gate={owned=false,phase='idle',gains={music=.45,drink=.9,win=1}}
            function gate:volumes()if volumeFails then error('volume unavailable')end;return self.gains end
            function gate:update(want,safe)
                if want then
                    if not self.owned then self.owned=true;self.phase='muting';events[#events+1]='mute'
                    elseif self.phase=='muting' then self.phase='muted' end
                elseif self.owned and safe then
                    if self.phase~='restoring' then self.phase='restoring';events[#events+1]='restore'
                    else self.owned=false;self.phase='idle' end
                end
                return self.phase=='muted'
            end
            local nativeTrack,seenDrink,seenWin=0,0,0
            package.loadlib=function(path,symbol)
                assert(path:match('Native\\JamieWinAudio%.dll$'))
                if loadFails then return nil,'DLL unavailable' end
                loads=loads+1
                local name=assert(symbol:match('^JamieNative_(.+)$'))
                if name=='Init' then return function()
                    hasStatus=true;status={version=modules.probe_settings.Version,session='',seq='0',epoch='0',
                        track='none',phase='idle',samples='0',tick='1',ready='0',music_stopped='1',pid='123',emergency='0'}
                end end
                if name=='Heartbeat' then return function()beats=beats+1 end end
                if name=='Stop' then return function()
                    stops=stops+1;status.phase='idle';status.music_stopped='1';status.emergency='1';nativeTrack=0
                end end
                assert(name=='Apply')
                return function()
                    applies=applies+1
                    local f={};for v in commandData:gmatch('[^|]+')do f[#f+1]=v end
                    assert(#f==14 and f[1]=='JWN5' and f[14]=='END\n')
                    history[#history+1]=f
                    status.session,status.seq,status.epoch,status.emergency=f[2],f[3],f[4],'0'
                    status.track=({'none','armed','drunk'})[tonumber(f[6])+1]
                    status.ready=autoReady==false and '0' or '1'
                    status.menu=f[7]
                    status.phase=f[5]=='0' and 'idle' or f[6]~='0' and f[8]=='1' and 'playing' or 'ready'
                    status.music_stopped=f[5]=='0' or f[6]=='0' or f[8]=='0' and '1' or '0'
                    if status.music_stopped==true then status.music_stopped='1' end
                    if status.music_stopped=='0' then
                        if nativeTrack~=tonumber(f[6]) then starts=starts+1;events[#events+1]='play' end
                        nativeTrack=tonumber(f[6])
                    else nativeTrack=0 end
                    if f[5]=='1' and f[7]=='0' and (f[6]=='0' or f[8]=='1') then
                        if tonumber(f[12])>seenDrink then drinks=drinks+1;seenDrink=tonumber(f[12]) end
                        if tonumber(f[13])>seenWin then wins=wins+1;seenWin=tonumber(f[13]) end
                    end
                    if rejectOpen then status.phase='failed';status.operation='waveOutOpen';status.code='2';status.music_stopped='1' end
                end
            end
            io.open=function(path,mode)
                if mode=='a' then return {write=function()return true end,close=function()return true end} end
                if mode=='wb' then
                    assert(path:match('/native%-command%.txt$'))
                    if writeFails then return nil end
                    return {write=function(_,s)commandData=s;return true end,close=function()return not closeFails end}
                end
                assert(mode=='rb' and path:match('/native%-status%.txt$'))
                if missingStatus or not hasStatus then return nil end
                return {close=function()return true end,read=function(_,limit)
                    assert(limit==2048);local rows={}
                    for k,v in pairs(status)do
                        if k=='seq' and staleSequence then v=tostring(tonumber(v)-1) end
                        rows[#rows+1]=k..'='..tostring(v)
                    end
                    return table.concat(rows,'\n')
                end}
            end
            os.remove=function()if removeFails then return nil end;hasStatus=false;return true end
            os.time=function()return math.floor(now)end
            os.date=function()return 'TEST ' end
            audio=modules.native_audio.new('C:/Probe',modules.probe_settings,valid,log,gate)
            function step(seconds)
                now=now+(seconds or .2)
                if hasStatus and not freezeStatus then
                    status.tick=tostring((tonumber(status.tick) or 0)+1)
                    if status.phase=='playing' then status.samples=tostring(tonumber(status.samples)+9600) end
                end
                audio:update(state,now)
            end
            function steps(n)for i=1,n or 1 do step()end end
            function enter()gameplay(true,'sober',true);steps(5)end
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_title_inventory_and_initial_pause_do_not_load_or_mute(self):
        self.check("state.active=false;step(600);gameplay(true,'sober',false);step();gameplay(true,'sober',true);state.paused=true;step();assert(loads==0 and not gate.owned);state.paused=false;steps(5);assert(loads==4 and starts==1)")

    def test_mute_confirmation_precedes_first_music_buffer(self):
        self.check("gameplay(true,'sober',true);step();assert(starts==0 and not gate.owned);step();assert(starts==0 and gate.phase=='muting');step();assert(starts==1 and events[1]=='mute' and events[2]=='play')")

    def test_tipsy_drunk_transitions_cues_and_music_dedup(self):
        self.check("enter();gameplay(true,'tipsy',true);steps(3);gameplay(true,'drunk',true);steps(3);assert(starts==2 and drinks==1);steps(5);assert(drinks==1);gameplay(true,'tipsy',false);step();gameplay(true,'drunk',false);step();assert(starts==2 and drinks==2);gameplay(true,'sober',true);steps(3);assert(starts==3)")

    def test_direct_sober_to_drunk_does_not_drop_voice(self):
        self.check("enter();gameplay(true,'drunk',true);steps(4);assert(starts==2 and drinks==1)")

    def test_voice_volume_follows_game_slider_without_restarting(self):
        self.check("enter();local n=applies;gate.gains={music=.1125,drink=.18,win=.2};steps(3);assert(applies==n+1 and starts==1);local f=history[#history];assert(tonumber(f[9])==.1125 and tonumber(f[10])==.18 and tonumber(f[11])==.2);gate.gains={music=0,drink=0,win=0};steps(2);assert(starts==1)")

    def test_brief_status_contention_and_pending_ack_do_not_withdraw_permission(self):
        self.check("enter();local n=applies;missingStatus=true;steps(2);assert(applies==n and starts==1);gate.gains.music=.1;step();staleSequence=true;missingStatus=false;steps(2);assert(applies==n+1 and starts==1);staleSequence=false;step();assert(audio.phase=='playing' and starts==1)")

    def test_execution_counter_and_drink_can_play_together_once(self):
        self.check("enter();state.wins=1;gameplay(true,'drunk',true);steps(4);assert(wins==1 and drinks==1);steps(4);assert(wins==1);state.wins=2;steps(2);assert(wins==2)")

    def test_menu_continues_music_and_holds_pending_voice_until_exit(self):
        self.check("enter();local before=tonumber(status.samples);state.paused=true;state.wins=1;steps(4);assert(audio.phase=='playing' and starts==1 and wins==0 and status.menu=='1');assert(tonumber(status.samples)>before);step(100);assert(not audio.blocked and gate.owned);state.paused=false;steps(4);assert(audio.phase=='playing' and wins==1 and starts==1 and status.menu=='0')")

    def test_nonpausing_menu_rapid_toggles_and_sliders_preserve_permission(self):
        self.check("enter();local epoch=audio.epoch;for i=1,10 do state.inMenu=true;step();state.inMenu=false;step()end;state.inMenu=true;gate.gains.music=.1;steps(4);assert(audio.phase=='playing' and starts==1 and audio.epoch==epoch and gate.owned);assert(status.menu=='1' and tonumber(history[#history][9])==.1);state.inMenu=false;steps(4);assert(status.menu=='0' and starts==1 and #events==2)")

    def test_menu_during_preparation_does_not_cancel_or_restart_loading(self):
        self.check("autoReady=false;gameplay(true,'sober',true);step();state.paused=true;steps(3);autoReady=true;gate.gains.music=.4;steps(4);assert(starts==1 and audio.phase=='playing' and status.menu=='1');state.paused=false;steps(3);assert(starts==1 and stops==0)")

    def test_death_in_menu_stops_and_restores_original_music(self):
        self.check("enter();state.inMenu=true;steps(3);gameplay(false,'sober',true);steps(4);assert(not gate.owned and status.menu=='0' and audio:isStopped(now))")

    def test_stop_waits_for_device_ack_then_restores(self):
        self.check("enter();gameplay(false,'sober',true);step();assert(gate.owned and gate.phase=='muted');step();assert(gate.phase=='restoring');step();assert(not gate.owned and audio:isStopped(now));assert(events[3]=='restore')")

    def test_weapon_sheath_stops_music_but_keeps_voice_transport_ready(self):
        self.check("enter();gameplay(true,'sober',false);steps(4);assert(not gate.owned and status.music_stopped=='1');state.wins=1;steps(2);assert(wins==1 and not gate.owned)")

    def test_new_player_does_not_replay_old_voice_counter(self):
        self.check("enter();state.wins=1;step();local epoch=audio.epoch;gameplay(true,'drunk',true,'pawn-2');steps(4);assert(audio.epoch>epoch and audio.drink==0 and audio.win==1)")

    def test_failure_does_not_retry_each_tick_and_recovers_on_transition(self):
        self.check("rejectOpen=true;enter();steps(20);assert(applies==1 and stops==1 and not gate.owned);assert(logs():find('operation=waveOutOpen; code=2',1,true));rejectOpen=false;gameplay(true,'sober',false);steps(3);enter();assert(starts==1 and audio.phase=='playing')")

    def test_missing_stale_or_frozen_status_stops_and_releases_after_lease(self):
        for fault in ('missingStatus=true', 'staleSequence=true', "status.version='old-version'", 'freezeStatus=true'):
            with self.subTest(fault=fault):
                self.setUp()
                self.check("enter();"+fault+";step(11);local b=beats;assert(stops==1);step(6);steps(3);assert(beats==b and not gate.owned and audio.phase=='failed')")

    def test_loading_timeout_never_mutes_original_music(self):
        self.check("autoReady=false;enter();step(11);assert(stops==1 and not gate.owned and starts==0)")

    def test_volume_or_command_failure_restores_music_even_if_preferences_unreadable(self):
        for fault in ('volumeFails=true', 'writeFails=true', 'closeFails=true'):
            with self.subTest(fault=fault):
                self.setUp()
                self.check("enter();"+fault+";gate.gains.music=.2;steps(4);assert(stops==1 and not gate.owned)")

    def test_load_failure_and_stale_status_cleanup_are_bounded(self):
        for fault in ('loadFails=true', 'hasStatus=true;removeFails=true'):
            with self.subTest(fault=fault):
                self.setUp()
                self.check(fault+";enter();steps(10);assert(applies==0 and not gate.owned and audio.phase=='failed')")

    def test_main_f10_waits_for_restore_and_disables_execution_events(self):
        self.lua.execute('''
            dofile=function(path)return modules[assert(path:match('/([^/]+)%.lua$'))]end
            modules.gameplay={new=function()return {controller=state.controller,sample=function()
                if observationError then error('observation failed')end;return state
            end}end}
            modules.game_audio={new=function()return gate end}
            modules.executions={new=function()execution={enabled=true,update=function()end};return execution end}
            print=log;Key={F10=121};RegisterKeyBindAsync=function(_,fn)stopKey=fn end
            ExecuteInGameThread=function(fn)fn()end;LoopAsync=function(_,fn)timer=fn end
        ''')
        self.lua.execute('assert(load(...,"@C:/Probe/Scripts/main.lua"))()', (PROBE / 'main.lua').read_text())
        self.check("gameplay(true,'sober',true);for i=1,5 do timer()end;assert(starts==1);observationError=true;for i=1,4 do timer()end;assert(not gate.owned);observationError=false;for i=1,5 do timer()end;assert(starts==2);stopKey();assert(timer()==false and execution.enabled==false);for i=1,4 do timer()end;assert(timer()==true and not gate.owned);assert(logs():find('STOPPED F10',1,true))")


class GameVolumeTests(unittest.TestCase):
    def setUp(self):
        self.lua = runtime()
        self.lua.execute('''
            function valid(o)return o and o.valid==true end
            preference={valid=true,OverallVolume=.8,MusicVolume=.5,DialogueVolume=.25}
            controller={valid=true,Player={valid=true,SharedSettings=preference}}
            rtpcValue=.5;writes={};messages={}
            sound={valid=true,SetAudioVolume=function(_,kind,value)
                if writeError then error('RTPC write failed')end
                if hook then hook(nil,{get=function()return kind end},{set=function(_,v)value=v end})end
                writes[#writes+1]=value;rtpcValue=value
            end}
            StaticFindObject=function(path)
                if path:find('SubsystemBlueprintLibrary',1,true) then
                    return {valid=true,GetWorldSubsystem=function(_,c,k)assert(c==controller and k.valid);return sound end}
                elseif path:find('AkGameplayStatics',1,true) then
                    return {valid=true,GetRTPCValue=function(_,r,a,b,result,kind)
                        if not readMissing then result.Value=rtpcValue;kind.OutputValueType=1 end
                    end}
                elseif path:find('KismetSystemLibrary',1,true) then
                    return {valid=true,LoadAsset_Blocking=function()return {valid=true}end}
                else return {valid=true,Volume_Music={}} end
            end
            RegisterHook=function(path,fn)assert(path:find('SetAudioVolume',1,true));hook=fn end
            gate=modules.game_audio.new(valid,function(s)messages[#messages+1]=s end)
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_gain_products_and_no_preference_writes(self):
        self.check("local v=gate:volumes(controller);assert(math.abs(v.music-.18)<1e-6 and math.abs(v.drink-.18)<1e-6 and v.win==.2);preference.OverallVolume=0;v=gate:volumes(controller);assert(v.music==0 and v.drink==0 and v.win==0);assert(#writes==0)")

    def test_mute_ack_restore_latest_preference_and_hooks_only_music(self):
        self.check('''
            assert(not gate:update(true,false,controller,1));assert(rtpcValue==0 and preference.MusicVolume==.5)
            assert(gate:update(true,false,controller,2))
            local called=false;assert(hook(nil,{get=function()return 1 end},{set=function()called=true end})==nil);assert(not called)
            sound:SetAudioVolume(2,.7);assert(rtpcValue==0)
            preference.MusicVolume=.7;gate:update(false,false,controller,3);assert(rtpcValue==0)
            gate:update(false,true,controller,4);assert(rtpcValue==.7 and gate.owned)
            gate:update(false,true,controller,5);assert(not gate.owned and preference.MusicVolume==.7)
        ''')

    def test_mute_requires_live_readback_and_write_failure_can_restore(self):
        self.check("readMissing=true;assert(not gate:update(true,false,controller,1) and not gate.owned);readMissing=false;writeError=true;assert(not pcall(function()gate:update(true,false,controller,2)end));assert(gate.owned);writeError=false;gate:update(false,true,controller,3);gate:update(false,true,controller,4);assert(not gate.owned and rtpcValue==.5)")

    def test_restore_changes_target_when_user_moves_slider_during_restore(self):
        self.check("gate:update(true,false,controller,1);gate:update(true,false,controller,2);gate:update(false,true,controller,3);preference.MusicVolume=.2;gate:update(false,true,controller,4);assert(gate.owned and rtpcValue==.2);gate:update(false,true,controller,5);assert(not gate.owned)")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.lua = runtime()
        self.lua.execute('''
            function obj(address)return {valid=true,GetAddress=function()return address end}end
            function valid(o)return o and o.valid==true end
            pawn=obj('player');enemy=obj('enemy');enemy.AttributeSetBase={valid=true,Health={CurrentValue=10}}
            ability=obj('ability');ability.name='GA_SimpleExecution_ChiZheCanJian_C';ability.ExecutionTarget=enemy
            ability.GetAvatarActorFromActorInfo=function()return pawn end
            state={active=true,paused=false,player='player'}
            observer={core=modules.core.new(),sample=function()return state end,className=function(_,o)return o.name end}
            changed=0;logs={};executions=modules.executions.new(observer,modules.settings,valid,
                function(s)logs[#logs+1]=s end,function()changed=changed+1 end)
            FindObject=function()return nil end
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_local_live_target_once_at_activation_and_rearm_after_end(self):
        self.check("executions:begin(ability);executions:begin(ability);assert(changed==1 and observer.core.wins==1);executions:finish(ability);executions:begin(ability);assert(changed==2)")

    def test_reject_other_actor_dead_target_wrong_class_pause_and_stop(self):
        for reject in ("pawn.GetAddress=function()return 'other' end", 'enemy.AttributeSetBase.Health.CurrentValue=0', "ability.name='unrelated'", 'state.paused=true', 'state.inMenu=true', 'state.active=false', 'executions.enabled=false'):
            with self.subTest(reject=reject):
                self.setUp()
                self.check(reject+";executions:begin(ability);assert(changed==0 and observer.core.wins==0)")

    def test_weapon_execution_weak_target_and_inherited_hook_dedup(self):
        self.check("ability.name='GA_Hun_BEx_ChiZheCanJian_M_01_C';ability['Execution Info']={Target={Get=function()return enemy end}};executions:begin(ability);executions:begin(ability);assert(changed==1)")

    def test_blueprint_and_native_post_hooks_do_not_return_values(self):
        self.check('''
            local functions={
                {GetFName=function()return {ToString=function()return 'K2_ActivateAbility' end}end,
                 GetFullName=function()return 'Function /Game/Ability:K2_ActivateAbility' end},
                {GetFName=function()return {ToString=function()return 'K2_OnEndAbility' end}end,
                 GetFullName=function()return 'Function /Script/GameplayAbilities.GameplayAbility:K2_OnEndAbility' end}}
            class={valid=true,ForEachFunction=function(_,fn)for _,v in ipairs(functions)do fn(v)end end,GetSuperStruct=function()return nil end}
            FindObject=function()return class end
            registered={};RegisterHook=function(path,pre,post)registered[path]={pre,post}end
            executions:update('player',1)
            local begin=registered['/Game/Ability:K2_ActivateAbility'];local ending=registered['/Script/GameplayAbilities.GameplayAbility:K2_OnEndAbility']
            assert(begin[1] and not begin[2] and ending[1] and ending[2])
            local ctx={get=function()return ability end}
            assert(begin[1](ctx)==nil and changed==1);assert(begin[1](ctx)==nil and changed==1)
            assert(ending[2](ctx)==nil);begin[1](ctx);assert(changed==2)
        ''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
