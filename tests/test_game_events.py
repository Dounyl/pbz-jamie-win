"""Hook dispatch, late-loaded Blueprint overrides, local ownership, and lifecycle."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/cache/testdeps'))
from lupa.lua54 import LuaRuntime


class GameEventTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        scripts = ROOT / 'probes/JamieWinNativeAudioTest/Scripts'
        self.lua.execute('Events=assert(load(...))()', (scripts / 'game_events.lua').read_text())
        self.lua.execute('''
            function valid(o)return type(o)=='table' and o.valid==true end
            serial=0
            function object(name,tags)
                serial=serial+1;local id=serial
                return {valid=true,name=name,tags=tags or {},GetAddress=function()return id end}
            end
            function ref(value)return {get=function()return value end}end
            controller=object('local controller', {PlayerController=true})
            controller.Player=object('local player');controller.Player.SharedSettings=object('sliders')
            pawn=object('local pawn',{Pawn=true});pawn.Controller=controller;controller.Pawn=pawn
            enemy=object('enemy',{Pawn=true});enemy.Controller=object('AI controller')
            setmetatable(enemy.Controller,{__index=function(_,key)error('must not read AI controller '..key)end})
            observer={controller=controller,owner=pawn,menuWidgets={}}
            function observer:isA(obj,name)return valid(obj) and obj.tags[name]==true end
            function observer:className(obj)return valid(obj) and obj.name or ''end
            function observer:isMenu(obj)return valid(obj) and obj.tags.menu==true end
            function observer:rememberMenu(obj)
                if not self:isMenu(obj)then return end
                for _,entry in ipairs(self.menuWidgets)do if entry.object==obj then return end end
                self.menuWidgets[#self.menuWidgets+1]={object=obj}
            end
            function observer:resetWorld()self.controller=nil;self.owner=nil;self.menuWidgets={}end
            lookups={};hooks={};notifies={};walks=0;registrations=0;signals=0;logs={}
            function functionObject(path)
                local fn=object(path)
                fn.flags=path:sub(1,8)=='/Script/' and 0x400 or 0
                function fn:GetFunctionFlags()return self.flags end
                function fn:GetFName()return {ToString=function()return path:match(':([^:]+)$')end}end
                function fn:GetFullName()return 'Function '..path end
                return fn
            end
            function class(path,methods,super)
                local c=object(path);c.methods={}
                for _,name in ipairs(methods)do
                    local full=path..':'..name;local fn=functionObject(full)
                    lookups[full]=fn;c.methods[#c.methods+1]=fn
                end
                function c:ForEachFunction(callback)walks=walks+1;for _,fn in ipairs(self.methods)do callback(fn)end end
                function c:GetSuperStruct()return super end
                lookups[path]=c;return c
            end
            StaticFindObject=function(path)
                if path==missing then return nil end
                if not lookups[path] and path:sub(1,8)=='/Script/' and path:find(':',1,true)then
                    lookups[path]=functionObject(path)
                end
                return lookups[path]
            end
            RegisterHook=function(path,pre,post)
                if path==reject then error('bytecode not ready')end
                if (lookups[path]:GetFunctionFlags() & 0x400)~=0 then
                    assert(type(post)=='function')
                else assert(post==nil)end
                registrations=registrations+1;hooks[path]={pre=pre,post=post}
                return registrations*2,registrations*2+1
            end
            NotifyOnNewObject=function(path,fn)assert(not notifies[path]);notifies[path]=fn end
            RegisterLoadMapPreHook=function(fn)assert(not mapPre);mapPre=fn end
            RegisterLoadMapPostHook=function(fn)assert(not mapPost);mapPost=fn end
            function fire(path,obj,...)
                local entry=assert(hooks[path],path)
                if entry.post then assert(entry.pre(ref(obj),...)==nil)end
                assert((entry.post or entry.pre)(ref(obj),...)==nil)
            end
            events=Events.new(observer,{ExecutionClasses={'GA_Hun_BEx_ChiZheCanJian_M_01_C','GA_Hun_BEx_ChiZheCanJian_M_02_C'}},
                valid,function(s)logs[#logs+1]=s end,function()signals=signals+1 end)
            playerPath='/Game/RenewalContent/Prototypes/Character/BP_RenewalPlayer.BP_RenewalPlayer_C'
            menuPath='/Game/Menu.Menu_C'
            passivePath='/PBZCombatAsset/ActorData/Players/Hun/Abilities/ChiZheCanJian/Use/Passive/GA_ChiZheCanJian_DrinkPassive.GA_ChiZheCanJian_DrinkPassive_C'
            armedPath='/SGameCombatSystem/Weapon/Abilities/BP_ChangeArmed_Base.BP_ChangeArmed_Base_C'
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_native_weapon_hooks_ignore_other_actors_and_preserve_engine_returns(self):
        self.check('''
            events:refresh()
            local component=object('weapons');component.GetOwner=function()return pawn end
            fire('/Script/SGameCombatSystem.CharacterWeaponsComponent:SetArmed',component,ref({}),ref(true))
            assert(signals==1)
            component.GetOwner=function()return enemy end
            fire('/Script/SGameCombatSystem.CharacterWeaponsComponent:SetArmed',component)
            assert(signals==1 and not events.forceInactive)
        ''')

    def test_local_slider_events_and_cues_request_snapshots(self):
        self.check('''
            events:refresh()
            fire('/Script/ProjectPBZ.PBZSettingsShared:SetMusicVolume',controller.Player.SharedSettings,ref(.2))
            fire('/Script/ProjectPBZ.PBZSettingsShared:SetMusicVolume',object('other settings'),ref(.5))
            local cue=object('GC_ChiZheCanJian_ZuiJian_C')
            fire('/Script/GameplayAbilities.GameplayCueNotify_Static:OnActive',cue,ref(pawn))
            fire('/Script/GameplayAbilities.GameplayCueNotify_Static:OnRemove',cue,ref(pawn))
            fire('/Script/GameplayAbilities.GameplayCueNotify_Static:WhileActive',cue,ref(enemy))
            assert(signals==3 and not events.forceInactive)
        ''')

    def test_menu_creation_is_deferred_and_blueprint_activation_override_is_hooked(self):
        self.check('''
            events:refresh()
            local c=class(menuPath,{'BP_OnActivated','BP_OnDeactivated','Construct','Destruct','Tick'})
            local widget=object('menu',{menu=true});widget.GetOwningPlayer=function()return controller end
            widget.GetClass=function()error('construction callback must not inspect object')end
            assert(notifies['/Script/ProjectPBZ.PBZGameSystemWidget'](widget)==nil)
            assert(signals==1 and not hooks[menuPath..':BP_OnActivated'])
            widget.GetClass=function()return c end;events:refresh()
            assert(#observer.menuWidgets==1 and not hooks[menuPath..':Tick'])
            fire(menuPath..':BP_OnActivated',widget);fire(menuPath..':BP_OnDeactivated',widget)
            assert(signals==3)
            widget.GetOwningPlayer=function()return object('other controller')end
            fire(menuPath..':BP_OnActivated',widget);assert(signals==3)
        ''')

    def test_drunk_and_weapon_ability_callbacks_ignore_tick_and_unrelated_abilities(self):
        self.check('''
            class(passivePath,{'IntoZuiStep','ExitZuiStep/ClearDrink','K2_OnEndAbility','OnTick_884BD4474B87E2C1C5F25F9EF2DD9818'})
            class(armedPath,{'Set Changing Armed','K2_OnEndAbility'})
            events:refresh()
            local ability=object('passive',{GA_ChiZheCanJian_DrinkPassive_C=true})
            ability.GetAvatarActorFromActorInfo=function()return pawn end
            fire(passivePath..':IntoZuiStep',ability);fire(passivePath..':ExitZuiStep/ClearDrink',ability)
            local armed=object('armed',{BP_ChangeArmed_Base_C=true})
            armed.GetAvatarActorFromActorInfo=function()return pawn end
            fire(armedPath..':K2_OnEndAbility',armed)
            fire(armedPath..':K2_OnEndAbility',ability)
            assert(signals==3 and not hooks[passivePath..':OnTick_884BD4474B87E2C1C5F25F9EF2DD9818'])
        ''')

    def test_health_crossing_death_and_respawn_are_observed_without_damage_spam(self):
        self.check('''
            class(playerPath,{'Health Post Func','On Dead','Respawn','ReceiveEndPlay'})
            events:refresh()
            fire(playerPath..':Health Post Func',pawn,ref(80),ref(100));assert(signals==0)
            fire(playerPath..':Health Post Func',pawn,ref(0),ref(80));assert(signals==1 and events.forceInactive)
            fire(playerPath..':Respawn',pawn);assert(signals==2 and events.forceInactive)
            events.forceInactive=false
            fire(playerPath..':ReceiveEndPlay',pawn);assert(signals==3 and events.forceInactive)
        ''')

    def test_world_change_invalidates_even_if_pre_and_post_coalesce(self):
        self.check('''
            events:refresh();observer.menuWidgets={{object=object('old menu')}}
            assert(mapPre()==nil and events.transitioning and events.forceInactive)
            assert(observer.controller==nil and observer.owner==nil and #observer.menuWidgets==0)
            assert(mapPost()==nil and not events.transitioning and events.forceInactive and signals==2)
        ''')

    def test_most_derived_override_avoids_hooking_general_actor_parent(self):
        self.check('''
            local parent=class('/Script/Engine.Actor',{'ReceiveBeginPlay','ReceiveEndPlay'})
            class(playerPath,{'ReceiveBeginPlay','ReceiveEndPlay'},parent)
            events:refresh()
            assert(hooks[playerPath..':ReceiveBeginPlay'] and hooks[playerPath..':ReceiveEndPlay'])
            assert(not hooks['/Script/Engine.Actor:ReceiveBeginPlay'] and not hooks['/Script/Engine.Actor:ReceiveEndPlay'])
            fire(playerPath..':ReceiveEndPlay',pawn)
            assert(events:playerEnded({owner=pawn}))
            assert(not events:playerEnded({owner=enemy}))
        ''')

    def test_registry_is_idempotent_and_failed_blueprint_registration_can_retry(self):
        self.check('''
            class(passivePath,{'IntoZuiStep','ExitZuiStep/ClearDrink'})
            reject=passivePath..':ExitZuiStep/ClearDrink'
            assert(not pcall(function()events:refresh()end))
            reject=nil;events:refresh()
            local count,walkCount=registrations,walks
            for event=1,50 do events:refresh()end
            assert(registrations==count and walks==walkCount)
        ''')

    def test_unloaded_blueprint_functions_can_register_again(self):
        self.check('''
            local c=class(passivePath,{'IntoZuiStep'});events:refresh()
            local count=registrations;c.valid=false;c.methods[1].valid=false
            class(passivePath,{'IntoZuiStep'});events:refresh()
            assert(registrations==count+1)
        ''')

    def test_load_game_skips_native_asset_bridges_but_keeps_blueprint_events(self):
        self.check('''
            local base=class(playerPath,{'Respawn','Health Post Func','ReceiveEndPlay'})
            events:refresh()
            local derivedPath='/Game/RenewalContent/Actors/Players/BP_Renewal_Hun.BP_Renewal_Hun_C'
            local derived=class(derivedPath,{'Respawn','Health Post Func','ReceiveEndPlay','ReceivePossessed'},base)
            for i=1,3 do derived.methods[i].flags=0x400 end
            pawn.GetClass=function()return derived end
            notifies['/Script/ProjectPBZ.PBZCharacter_Player'](pawn)
            local count=registrations
            events:refresh();events:watchCurrent({owner=pawn})
            assert(registrations==count+1)
            for _,name in ipairs({'Respawn','Health Post Func','ReceiveEndPlay'})do
                assert(not hooks[derivedPath..':'..name])
                assert(events.skipped[derivedPath..':'..name])
            end
            assert(hooks[derivedPath..':ReceivePossessed'])
            local previous=signals
            fire(derivedPath..':ReceivePossessed',pawn)
            assert(signals==previous+1)
            events:refresh();events:watchCurrent({owner=pawn})
            assert(registrations==count+1)
        ''')

    def test_script_package_blueprint_event_uses_script_callback(self):
        self.check('''
            local path='/Script/CommonUI.CommonActivatableWidget'
            local base=class(path,{'BP_OnActivated'})
            base.methods[1].flags=0
            class('/Script/ProjectPBZ.PBZGameSystemWidget',{},base)
            events:refresh()
            local widget=object('menu',{menu=true})
            widget.GetOwningPlayer=function()return controller end
            assert(hooks[path..':BP_OnActivated'].post==nil)
            fire(path..':BP_OnActivated',widget)
            assert(signals==1 and #observer.menuWidgets==1)
        ''')

    def test_hook_error_requests_safe_stop_and_f10_ignores_later_events(self):
        self.check('''
            events:refresh()
            local broken=object('weapons');broken.GetOwner=function()error('destroyed')end
            fire('/Script/SGameCombatSystem.CharacterWeaponsComponent:SetArmed',broken)
            assert(events.forceInactive and signals==1)
            events:stop();mapPre();notifies['/Script/Engine.PlayerController'](controller)
            fire('/Script/Engine.GameplayStatics:SetGamePaused',object('statics'),ref(pawn),ref(true))
            assert(signals==1)
        ''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
