-- Own only the game's music RTPC. User preferences remain read-only.
local GameAudio = {}
GameAudio.__index = GameAudio
function GameAudio.new(valid, log)
    return setmetatable({valid=valid,log=log,owned=false,phase="idle",ticks=0},GameAudio)
end
function GameAudio:resolve(controller)
    if self.valid(controller) and self.valid(controller.Player) then
        self.controller=controller
        local settings=controller.Player.SharedSettings
        if self.valid(settings) then self.settings=settings end
    end
end
local function volume(value, name)
    assert(type(value)=="number" and value==value and value>=0 and value<=1,"invalid game "..name)
    return value
end
function GameAudio:volumes(controller)
    self:resolve(controller)
    if not self.valid(self.settings) then return nil end
    local master=volume(self.settings.OverallVolume,"master volume")
    local music=volume(self.settings.MusicVolume,"music volume")
    local voice=volume(self.settings.DialogueVolume,"voice volume")
    -- Preserve the previously chosen balance without adding user configuration.
    return {music=master*music*0.45,drink=master*voice*0.9,win=master*voice}
end
function GameAudio:subsystem()
    if self.valid(self.controller) then
        local library=StaticFindObject("/Script/Engine.Default__SubsystemBlueprintLibrary")
        local class=StaticFindObject("/Script/ProjectPBZ.PBZSoundFXSubsystem")
        if self.valid(library) and self.valid(class) then
            local current=library:GetWorldSubsystem(self.controller,class)
            if self.valid(current) then self.sound=current end
        end
    end
    return self.valid(self.sound)
end
function GameAudio:read()
    if not self.valid(self.ak) then self.ak=StaticFindObject("/Script/AkAudio.Default__AkGameplayStatics") end
    if not self.valid(self.rtpc) then
        local config=StaticFindObject("/Script/ProjectPBZ.Default__PBZGameSettings")
        local system=StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
        if self.valid(config) and self.valid(system) then self.rtpc=system:LoadAsset_Blocking(config.Volume_Music) end
    end
    if not self.valid(self.ak) or not self.valid(self.rtpc) then return nil end
    local result,kind={},{}
    self.ak:GetRTPCValue(self.rtpc,0,1,result,kind,nil)
    if kind.OutputValueType==4 then return nil end
    return type(result.Value)=="number" and result.Value or nil
end
function GameAudio:write(value)
    self.ownCall=true
    local ok,err=pcall(function()self.sound:SetAudioVolume(2,value)end)
    self.ownCall=false
    if not ok then error(err) end
    self.writeTick=self.ticks
end
function GameAudio:installHook()
    if self.hooked then return end
    RegisterHook("/Script/ProjectPBZ.PBZSoundFXSubsystem:SetAudioVolume",function(_,kind,value)
        local ok,err=pcall(function()
            if self.owned and self.phase~="restoring" and not self.ownCall and kind:get()==2 then value:set(0) end
        end)
        if not ok then self.log("VOLUME_HOOK_ERROR "..tostring(err)) end
        -- Do not return a value to UE4SS.
    end)
    self.hooked=true
end
function GameAudio:preference()
    if self.valid(self.settings) then
        local current=self.settings.MusicVolume
        if type(current)=="number" and current>=0 and current<=1 then return current end
    end
    return self.saved
end
function GameAudio:update(want, safe, controller, now)
    self.ticks=self.ticks+1
    self:resolve(controller)
    if not want and not self.owned then return false end
    if not self:subsystem() then return false end
    if want and self.phase~="restoring" then
        if not self.owned then
            local preference=self:preference()
            if preference==nil or self:read()==nil then return false end
            self:installHook()
            self.saved,self.owned,self.phase,self.started=preference,true,"muting",now
            self:write(0)
            self.log("MUSIC_MUTE_REQUEST preference="..preference)
        elseif self.phase=="muting" and self.ticks>self.writeTick then
            local current=self:read()
            if current~=nil and math.abs(current)<=0.001 then
                self.phase="muted";self.log("MUSIC_MUTED_CONFIRMED")
            elseif now-self.started>=3 then error("game music mute confirmation timeout") end
        end
    elseif self.owned and (safe or self.phase=="restoring") then
        local preference=self:preference()
        if preference==nil then return false end
        if self.phase~="restoring" or self.target~=preference then
            self.phase,self.target,self.lastRestore="restoring",preference,now
            self:write(preference)
            self.log("MUSIC_RESTORE_REQUEST preference="..preference)
        elseif self.ticks>self.writeTick then
            local current=self:read()
            if current~=nil and math.abs(current-preference)<=0.001 then
                self.owned,self.phase,self.saved=false,"idle",nil
                self.log("MUSIC_RESTORED_CONFIRMED value="..preference)
            elseif now-self.lastRestore>=1 then
                self:write(preference);self.lastRestore=now
            end
        end
    end
    return self.owned and self.phase=="muted"
end
return GameAudio
