-- Read-only adapter for the same Core, Weapon and settings shipped by JamieWin.
local Gameplay = {}
Gameplay.__index = Gameplay
function Gameplay.new(Core, Weapon, settings, valid)
    return setmetatable({ core=Core.new(), weapon=Weapon, settings=settings, valid=valid }, Gameplay)
end
function Gameplay:className(object)
    return self.valid(object) and object:GetClass():GetFName():ToString() or ""
end
function Gameplay:inactive(detail, player)
    self.core:observe(player or "", false, "unknown")
    return { active=false, controller=self.controller, track="none", state="unknown", player=player or "",
        heavy=self.core.heavy,wins=self.core.wins,paused=false,inMenu=false,detail=detail }
end
function Gameplay:menuOpen(paused)
    -- IsGamePaused is already observed in PBZ. Also recognize active system menus
    -- that do not pause the world. Query roots, never individual hidden tab panels.
    if paused then return true,"game paused" end
    local now=os.time()
    if self.menuScanAt~=now or self.menuController~=self.controller then
        self.menuScanAt,self.menuController,self.menuWidgets=now,self.controller,{}
        for _,class in ipairs({"PBZSystemScreenWidget","PBZGameSystemWidget"})do
            local ok,widgets=pcall(FindAllOf,class)
            if ok then
                for _,widget in ipairs(widgets or {})do
                    self.menuWidgets[#self.menuWidgets+1]={object=widget,class=class}
                end
            end
        end
    end
    for _,entry in ipairs(self.menuWidgets or {})do
        local widget=entry.object
        if self.valid(widget) then
            local ok,open=pcall(function()
                local owner=widget:GetOwningPlayer()
                return self.valid(owner) and owner:GetAddress()==self.controller:GetAddress()
                    and widget:IsActivated()==true and widget:IsVisible()==true
            end)
            if ok and open then return true,entry.class end
        end
    end
    return false,"none"
end
function Gameplay:sample()
    local valid = self.valid
    if not valid(self.controller) or not valid(self.controller.Player)
        or not valid(self.controller.Pawn) then
        self.controller = nil
        for _, item in ipairs(FindAllOf("PlayerController") or {}) do
            if valid(item) and valid(item.Player) and valid(item.Pawn)
                and not self:className(item):find("DebugCamera", 1, true) then
                self.controller = item
                break
            end
        end
    end
    if not valid(self.controller) then return self:inactive("no local player") end
    local pawn = self.controller.Pawn
    local player = tostring(pawn:GetAddress())
    if not valid(self.titleLibrary) then
        self.titleLibrary = StaticFindObject("/Script/ProjectPBZ.Default__PBZBlueprintFunctionLibrary")
    end
    -- A title map can have a controller/pawn too. Never use it as a playback trigger.
    if not valid(self.titleLibrary) then return self:inactive("waiting for map query") end
    if self.titleLibrary:IsStartMenuMap(pawn) then return self:inactive("title menu") end
    local attributes = pawn.AttributeSetBase
    if not valid(attributes) then return self:inactive("no player health", player) end
    local hp = attributes.Health.CurrentValue
    if type(hp) ~= "number" or hp <= 0 then return self:inactive("player dead/unavailable", player) end
    if not valid(pawn.AbilitySystemComponent) then return self:inactive("no ability system", player) end
    local state, names = "sober", {}
    local active = pawn.AbilitySystemComponent.ActiveGameplayEffects.GameplayEffects_Internal
    for index = 1, #active do
        local effect = active[index]
        if not effect.bIsInhibited then
            local name = self:className(effect.Spec.Def)
            if name:find("ChiZhe", 1, true) then names[#names + 1] = name end
            if name == self.settings.DrunkEffect or name == self.settings.InfiniteDrunkEffect then
                state = "drunk"
            elseif name == self.settings.TipsyEffect and state ~= "drunk" then
                state = "tipsy"
            end
        end
    end
    table.sort(names)
    local holding, weaponDetail = self.weapon.held(pawn, self.settings.DrunkSwordWeaponConfig, valid)
    self.core:observe(player, true, state, holding)
    if not valid(self.statics) then self.statics = StaticFindObject("/Script/Engine.Default__GameplayStatics") end
    local paused = valid(self.statics) and self.statics:IsGamePaused(pawn) == true
    local inMenu,menuSource = self:menuOpen(paused)
    return { active=true,controller=self.controller,owner=pawn,player=player,state=state,track=self.core.track,paused=paused,
        inMenu=inMenu,
        heavy=self.core.heavy,wins=self.core.wins,
        detail="held=" .. tostring(holding) .. "; effects=" .. table.concat(names, ",") .. "; " .. weaponDetail .. "; menu_source=" .. menuSource }
end
return Gameplay
