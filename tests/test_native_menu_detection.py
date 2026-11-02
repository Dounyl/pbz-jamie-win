"""Read-only menu detection: local active roots and observed pause state."""
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
            now,queries=100,0
            os.time=function()return now end
            function valid(o)return o and o.valid==true end
            controller={valid=true,GetAddress=function()return 42 end}
            other={valid=true,GetAddress=function()return 99 end}
            widget={valid=true,active=false,visible=true,owner=controller}
            function widget:GetOwningPlayer()return self.owner end
            function widget:IsActivated()return self.active end
            function widget:IsVisible()return self.visible end
            roots={PBZSystemScreenWidget={widget},PBZGameSystemWidget={}}
            FindAllOf=function(class)queries=queries+1;return roots[class]end
            observer=Gameplay.new({new=function()return {observe=function()end,heavy=0,wins=0}end},{},{},valid)
            observer.controller=controller
        ''')

    def check(self, code):
        self.lua.execute(code)

    def test_pause_immediately_enables_effect_without_widget_discovery(self):
        self.check("assert(observer:menuOpen(true)==true and queries==0)")

    def test_only_visible_activated_local_menu_counts_and_cache_tracks_close(self):
        self.check("assert(not observer:menuOpen(false));widget.active=true;assert(observer:menuOpen(false));widget.visible=false;assert(not observer:menuOpen(false));widget.visible=true;widget.owner=other;assert(not observer:menuOpen(false));widget.owner=controller;widget.active=false;assert(not observer:menuOpen(false));assert(queries==2)")

    def test_new_inventory_root_discovered_and_stale_objects_ignored(self):
        self.check("roots.PBZSystemScreenWidget={};assert(not observer:menuOpen(false));roots.PBZGameSystemWidget={widget};widget.active=true;now=101;assert(observer:menuOpen(false));widget.valid=false;assert(not observer:menuOpen(false));widget.valid=true;widget.IsActivated=function()error('destroyed')end;assert(not observer:menuOpen(false))")

    def test_title_and_death_take_priority_over_menu(self):
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
