-- Read-only adapter for the same Core, Weapon and settings shipped by JamieWin.
local Gameplay = {}
Gameplay.__index = Gameplay
local menuClasses = {"PBZSystemScreenWidget", "PBZGameSystemWidget"}
function Gameplay.new(Core, Weapon, settings, valid)
    return setmetatable({ core=Core.new(), weapon=Weapon, settings=settings, valid=valid,
        menuWidgets={},menuDirty=true }, Gameplay)
end
function Gameplay:className(object)
    return self.valid(object) and object:GetClass():GetFName():ToString() or ""
end
function Gameplay:inactive(detail, player)
    self.core:observe(player or "", false, "unknown")
    return { active=false, controller=self.controller, track="none", state="unknown", player=player or "",
        heavy=self.core.heavy,wins=self.core.wins,paused=false,inMenu=false,detail=detail }
end
function Gameplay:isA(object,name)
    local current=self.valid(object) and object:GetClass() or nil
    while self.valid(current)do
        if current:GetFName():ToString()==name then return true end
        current=current:GetSuperStruct()
    end
    return false
end
function Gameplay:isMenu(object)
    for _,name in ipairs(menuClasses)do
        if self:isA(object,name) then return true end
    end
    return false
end
function Gameplay:rememberMenu(widget)
    if not self.valid(widget) or not self:isMenu(widget) then return end
    local key=widget:GetAddress()
    for _,entry in ipairs(self.menuWidgets)do
        if self.valid(entry.object) and entry.object:GetAddress()==key then return end
    end
    self.menuWidgets[#self.menuWidgets+1]={object=widget,class=self:className(widget)}
end
function Gameplay:resetWorld()
    self.controller,self.menuController,self.owner=nil,nil,nil
    self.menuWidgets,self.menuDirty={},true
end
function Gameplay:menuOpen(paused)
    -- Called only for game events. Creation/activation hooks add new menu roots;
    -- one discovery pass covers widgets that already existed when the mod started.
    if paused then return true,"game paused" end
    if self.menuDirty or self.menuController~=self.controller then
        self.menuController,self.menuWidgets=self.controller,{}
        self.menuDirty=false
        for _,class in ipairs(menuClasses)do
            local ok,widgets=pcall(FindAllOf,class)
            if ok then
                for _,widget in ipairs(widgets or {})do
                    self.menuWidgets[#self.menuWidgets+1]={object=widget,class=class}
                end
            else self.menuDirty=true end
        end
    end
    for index=#self.menuWidgets,1,-1 do
        local entry=self.menuWidgets[index]
        local widget=entry.object
        if self.valid(widget) then
            local ok,open=pcall(function()
                local owner=widget:GetOwningPlayer()
                return self.valid(owner) and owner:GetAddress()==self.controller:GetAddress()
                    and widget:IsActivated()==true and widget:IsVisible()==true
            end)
            if ok and open then return true,entry.class end
        else table.remove(self.menuWidgets,index) end
    end
    return false,"none"
end
function Gameplay:sample()
    local valid = self.valid
    if not valid(self.controller) or not valid(self.controller.Player) then
        self.controller = nil
        for _, item in ipairs(FindAllOf("PlayerController") or {}) do
            if valid(item) and valid(item.Player)
                and not self:className(item):find("DebugCamera", 1, true) then
                self.controller = item
                break
            end
        end
    end
    if not valid(self.controller) then return self:inactive("no local player") end
    local pawn = self.controller.Pawn
    if not valid(pawn) then return self:inactive("no player pawn") end
    self.owner=pawn
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
