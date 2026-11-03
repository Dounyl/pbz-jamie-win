"""Event snapshots: local menu roots, initial discovery, and object lifetime."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/cache/testdeps'))
from lupa.lua54 import LuaRuntime


class MenuDetectionTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('Gameplay=assert(load(...))()', (ROOT / 'probes/JamieWinNativeAudioTest/Scripts/gameplay.lua').read_text())
        self.lua.execute('''
            queries=0
            function valid(o)return o and o.valid==true end
            function class(name,super)
                return {valid=true,GetFName=function()return {ToString=function()return name end}end,
                    GetSuperStruct=function()return super end}
            end
            controller={valid=true,GetAddress=function()return 42 end}
            other={valid=true,GetAddress=function()return 99 end}
            widget={valid=true,active=false,visible=true,owner=controller}
            function widget:GetOwningPlayer()return self.owner end
            function widget:IsActivated()return self.active end
            function widget:IsVisible()return self.visible end
            function widget:GetAddress()return 101 end
            local widgetClass=class('W_Menu_C',class('PBZSystemScreenWidget'))
            function widget:GetClass()return widgetClass end
            roots={PBZSystemScreenWidget={widget},PBZGameSystemWidget={}}
            FindAllOf=function(name)queries=queries+1;return roots[name]end
            observer=Gameplay.new({new=function()return {observe=function()end,heavy=0,wins=0}end},{},{},valid)
            observer.controller=controller
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_pause_needs_no_discovery(self):
        self.check("assert(observer:menuOpen(true)==true and queries==0)")

    def test_only_visible_activated_local_menu_counts(self):
        self.check("assert(not observer:menuOpen(false));widget.active=true;assert(observer:menuOpen(false));widget.visible=false;assert(not observer:menuOpen(false));widget.visible=true;widget.owner=other;assert(not observer:menuOpen(false));widget.owner=controller;widget.active=false;assert(not observer:menuOpen(false));assert(queries==2)")

    def test_creation_event_adds_new_root_without_global_rescan(self):
        self.check('''
            roots.PBZSystemScreenWidget={};assert(not observer:menuOpen(false))
            widget.active=true;observer:rememberMenu(widget);observer:rememberMenu(widget)
            assert(observer:menuOpen(false) and queries==2 and #observer.menuWidgets==1)
            widget.valid=false;assert(not observer:menuOpen(false) and #observer.menuWidgets==0)
        ''')

    def test_unrelated_widget_cannot_enable_menu(self):
        self.check('''
            roots.PBZSystemScreenWidget={};assert(not observer:menuOpen(false))
            widget.GetClass=function()return class('HUD_Widget')end
            widget.active=true;observer:rememberMenu(widget)
            assert(not observer:menuOpen(false) and #observer.menuWidgets==0)
        ''')

    def test_repeated_event_snapshots_reuse_menu_objects(self):
        self.check('''
            for event=1,3000 do assert(not observer:menuOpen(false))end
            assert(queries==2)
            widget.active=true;assert(observer:menuOpen(false) and queries==2)
        ''')

    def test_world_change_discards_old_menu_and_controller(self):
        self.check('''
            widget.active=true;assert(observer:menuOpen(false))
            observer:resetWorld();assert(observer.controller==nil and #observer.menuWidgets==0)
            observer.controller=other;assert(not observer:menuOpen(false) and queries==4)
            widget.owner=other;assert(observer:menuOpen(false) and queries==4)
        ''')

    def test_failed_discovery_retries_on_next_event_only(self):
        self.check('''
            local find=FindAllOf;FindAllOf=function()error('objects not ready')end
            assert(not observer:menuOpen(false) and observer.menuDirty)
            FindAllOf=find;widget.active=true;assert(observer:menuOpen(false) and queries==2)
        ''')

    def test_existing_controller_waits_for_pawn_without_rediscovery(self):
        self.check('''
            controller.Player={valid=true}
            for event=1,10 do assert(observer:sample().detail=='no player pawn')end
            assert(queries==0)
        ''')

    def test_title_and_death_take_priority(self):
        self.check('''
            controller.Player={valid=true};controller.Pawn={valid=true,GetAddress=function()return 1 end}
            observer.titleLibrary={valid=true,IsStartMenuMap=function()return true end}
            widget.active=true
            local state=observer:sample();assert(not state.active and not state.inMenu and queries==0)
            observer.titleLibrary.IsStartMenuMap=function()return false end
            controller.Pawn.AttributeSetBase={valid=true,Health={CurrentValue=0}}
            state=observer:sample();assert(not state.active and not state.inMenu and queries==0)
        ''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
