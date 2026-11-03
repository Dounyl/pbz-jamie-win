-- PBZ build 26266538: observe reflected events, never Tick or delegate signatures.
local Events={}
Events.__index=Events
local function names(list)local set={};for _,name in ipairs(list)do set[name]=true end;return set end
local menuNames=names({"BP_OnActivated","BP_OnDeactivated","Construct","Destruct"})
local descriptors={
    {kind="player",notify="/Script/ProjectPBZ.PBZCharacter_Player",
        path="/Game/RenewalContent/Prototypes/Character/BP_RenewalPlayer.BP_RenewalPlayer_C",
        functions=names({"ReceiveBeginPlay","ReceiveEndPlay","ReceivePossessed","ReceiveUnpossessed",
            "On Dead","Health Post Func","Respawn","Respawn Recover Attributes","OnWeaponListInitialized_Event",
            "ReplaceWeaponConfigReady_Event","EquipmentWeaponConfigReady_Event","ChangeArmed","Unarm"})},
    {kind="menu",path="/Script/ProjectPBZ.PBZSystemScreenWidget",functions=menuNames},
    {kind="menu",path="/Script/ProjectPBZ.PBZGameSystemWidget",functions=menuNames},
    {kind="ability",path="/PBZCombatAsset/ActorData/Players/Hun/Abilities/ChiZheCanJian/Use/Passive/GA_ChiZheCanJian_DrinkPassive.GA_ChiZheCanJian_DrinkPassive_C",
        functions=names({"K2_ActivateAbility","K2_OnEndAbility","IntoZuiStep","ExitZuiStep/ClearDrink",
            "SuccessDrinkFX","SuccessZuiFX","ExitzuiStateFX","ZuiGECounter",
            "Added_3F367BD940D38E1846A930B63DC8DAD4","Removed_61EB55D449355AD19D9385921E31366A",
            "Removed_DBE5B1D844C40AD736E12FAD53DA0DE1"})},
    {kind="ability",path="/SGameCombatSystem/Weapon/Abilities/BP_ChangeArmed_Base.BP_ChangeArmed_Base_C",
        functions=names({"K2_ActivateAbility","K2_OnEndAbility","Set Changing Armed","On Changing Arm State End"})},
    {kind="arm_action",path="/SGameCombatSystem/Weapon/Action/GAAction_ChangeArmed.GAAction_ChangeArmed_C",
        functions=names({"Change Armed"})},
    {kind="arm_action",path="/SGameCombatSystem/Weapon/Action/GAAction_ChangeArmed_Duration.GAAction_ChangeArmed_Duration_C",
        functions=names({"Change Arm"})},
}
local cueNames=names({"GC_ChiZheCanJian_PreZui_3_C","GC_ChiZheCanJian_ZuiJian_C","GC_ChiZheCanJian_ZuiJianInfinite_C"})
local function unwrap(value)
    local ok,result=pcall(function()return value:get()end)
    if ok then return result end
    return value
end
function Events.new(observer,settings,valid,log,changed)
    return setmetatable({observer=observer,settings=settings,valid=valid,log=log,changed=changed,
        enabled=true,hooks={},skipped={},bound={},classes={},pending={},seen={},errors={},notifications={}},Events)
end
function Events:same(a,b)
    return self.valid(a) and self.valid(b) and a:GetAddress()==b:GetAddress()
end
function Events:localPawn(object)
    if not self.valid(object) then return false end
    local controller=self.observer.controller
    if self:same(object,self.observer.owner) or (self.valid(controller) and self:same(object,controller.Pawn)) then return true end
    if not self.observer:isA(object,"Pawn") then return false end
    local owner=object.Controller
    if self.valid(owner) and self.observer:isA(owner,"PlayerController")
        and self.valid(owner.Player) and self:same(object,owner.Pawn) then
        self.observer.controller=owner
        return true
    end
    return false
end
function Events:signal(kind)
    if not self.enabled then return end
    if not self.seen[kind] then self.seen[kind]=true;self.log("EVENT_SEEN "..kind) end
    self.changed()
end
function Events:protect(fn)
    return function(...)
        if not self.enabled then return end
        local ok,err=pcall(fn,...)
        if not ok then
            err=tostring(err)
            if not self.errors[err] then self.errors[err]=true;self.log("EVENT_ERROR "..err) end
            self.forceInactive=true
            self.changed()
        end
        -- Never override engine return values or mutate hook parameters.
    end
end
function Events:hook(path,key,handler)
    local fn=StaticFindObject(path)
    if not self.valid(fn) then error("event function unavailable: "..path) end
    local isNative=(fn:GetFunctionFlags() & 0x400)~=0 -- FUNC_Native
    -- PBZ's Puerts overrides live in asset packages but use native thunks.
    -- The native hook's synthetic frame has no bytecode; these thunks read it.
    -- Never install a native hook on an asset override (including mixins).
    if isNative and path:sub(1,8)~="/Script/" then
        if not self.valid(self.skipped[path]) then
            self.log("EVENT_SKIP native asset bridge "..path)
            self.skipped[path]=fn
        end
        return
    end
    local entry=self.hooks[path]
    if entry and self.valid(entry.fn) then entry.handlers[key]=handler;return end
    entry={fn=fn,handlers={[key]=handler}}
    local callback=self:protect(function(ctx,...)
        local object=unwrap(ctx)
        for _,listener in pairs(entry.handlers)do listener(object,...) end
    end)
    if isNative then
        entry.pre,entry.post=RegisterHook(path,function()end,callback)
    else entry.pre,entry.post=RegisterHook(path,callback) end
    self.hooks[path]=entry
    self.log("EVENT_HOOK "..path)
end
function Events:accept(descriptor,object,short,...)
    if not self.valid(object) then return end
    local kind=descriptor.kind
    if kind=="menu" then
        if not self.observer:isMenu(object) then return end
        self.observer:rememberMenu(object)
        local owner=object:GetOwningPlayer()
        if self.valid(self.observer.controller) and not self:same(owner,self.observer.controller) then return end
    elseif kind=="player" then
        if not self:localPawn(object) then return end
        if short=="Health Post Func" then
            local newer,older=...
            newer,older=unwrap(newer),unwrap(older)
            if type(newer)=="number" and type(older)=="number" and newer>0 and older>0 then return end
        end
        if short=="On Dead" or short=="ReceiveEndPlay" or short=="ReceiveUnpossessed"
            or (short=="Health Post Func" and type(unwrap((...)))=="number" and unwrap((...))<=0) then
            self.forceInactive=true
        end
        if short=="ReceiveEndPlay" or short=="ReceiveUnpossessed" then self.endedPawn=object
        elseif short=="ReceivePossessed" or short=="Respawn" then self.endedPawn=nil end
    elseif kind=="ability" then
        if not self.observer:isA(object,descriptor.path:match("%.([^%.]+)$"))
            or not self:localPawn(object:GetAvatarActorFromActorInfo()) then return end
    elseif kind=="arm_action" then
        if not self:localPawn(unwrap((...))) then return end
    end
    self:signal(kind)
end
function Events:bind(class,descriptor)
    if not self.valid(class) then return end
    local key=descriptor.path..":"..tostring(class:GetAddress())
    if self.valid(self.bound[key]) then return end
    local current,found=class,{}
    while self.valid(current)do
        current:ForEachFunction(function(fn)
            local short=fn:GetFName():ToString()
            if not descriptor.functions[short] or found[short] then return end
            found[short]=true
            local path=fn:GetFullName():gsub("^%S+%s+","")
            self:hook(path,descriptor.path,function(object,...)
                self:accept(descriptor,object,short,...)
            end)
        end)
        current=current:GetSuperStruct()
    end
    self.bound[key]=class
end
function Events:resetWorld(transitioning)
    self.transitioning,self.forceInactive=transitioning,true
    self.pending={}
    self.endedPawn=nil
    self.observer:resetWorld()
    self:signal("world")
end
function Events:playerEnded(state)
    return self:same(state.owner,self.endedPawn)
end
function Events:notify(path,callback)
    if self.notifications[path] then return end
    NotifyOnNewObject(path,self:protect(callback))
    self.notifications[path]=true
end
function Events:start()
    if self.started then return end
    local function native(class,list,handler)
        for _,name in ipairs(list)do self:hook(class..":"..name,class,handler) end
    end
    native("/Script/SGameCombatSystem.CharacterWeaponsComponent",
        {"SetArmed","SetCurrentWeapon","SetSlotWeapon","AutoSetCurrentWeapon","OnRestarted"},function(object)
            if self.valid(object) and self:localPawn(object:GetOwner()) then self:signal("weapon") end
        end)
    native("/Script/ProjectPBZ.PBZSettingsShared",{"SetOverallVolume","SetMusicVolume","SetDialogueVolume"},function(object)
        local controller=self.observer.controller
        if self.valid(controller) and self.valid(controller.Player)
            and self:same(object,controller.Player.SharedSettings) then self:signal("volume") end
    end)
    native("/Script/Engine.GameplayStatics",{"SetGamePaused"},function()self:signal("menu")end)
    native("/Script/Engine.PlayerController",{"ClientRestart"},function(object)
        if self.valid(object) and self.valid(object.Player) then
            self.observer.controller=object;self:signal("player")
        end
    end)
    native("/Script/GameplayAbilities.GameplayCueNotify_Static",{"OnActive","WhileActive","OnRemove"},function(object,target)
        if cueNames[self.observer:className(object)] and self:localPawn(unwrap(target)) then self:signal("drunk_cue") end
    end)
    for _,descriptor in ipairs(descriptors)do
        self:notify(descriptor.notify or descriptor.path,function(object)
            -- Do not inspect partially constructed objects on the creation thread.
            self.pending[#self.pending+1]={object=object,descriptor=descriptor}
            self.changed()
        end)
    end
    self:notify("/Script/Engine.PlayerController",function()self:signal("controller_created")end)
    for _,name in ipairs(self.settings.ExecutionClasses)do
        local asset=name:gsub("_C$","")
        self:notify("/PBZCombatAsset/ActorData/Players/Hun/Abilities/ChiZheCanJian/Use/EXE/"..asset.."."..name,
            function()self:signal("execution_created")end)
    end
    if not self.mapPre then
        RegisterLoadMapPreHook(self:protect(function()self:resetWorld(true)end));self.mapPre=true
    end
    if not self.mapPost then
        RegisterLoadMapPostHook(self:protect(function()self:resetWorld(false)end));self.mapPost=true
    end
    self.started=true
    self.log("EVENT_MODE gameplay hooks enabled; no periodic gameplay sampling; native_asset_bridges=skipped; hook_dispatch=flags")
end
function Events:refresh()
    self:start()
    for _,descriptor in ipairs(descriptors)do
        local class=self.classes[descriptor.path]
        if not self.valid(class) then class=StaticFindObject(descriptor.path);self.classes[descriptor.path]=class end
        self:bind(class,descriptor)
    end
    local pending=self.pending;self.pending={}
    for _,entry in ipairs(pending)do
        if self.valid(entry.object) then
            self:bind(entry.object:GetClass(),entry.descriptor)
            if entry.descriptor.kind=="menu" then self.observer:rememberMenu(entry.object) end
        end
    end
end
function Events:watchCurrent(state)
    if self.valid(state.owner) then self:bind(state.owner:GetClass(),descriptors[1]) end
    for _,entry in ipairs(self.observer.menuWidgets)do
        if self.valid(entry.object) then self:bind(entry.object:GetClass(),descriptors[2]) end
    end
end
function Events:stop()
    self.enabled=false
    self.pending={}
end
return Events
