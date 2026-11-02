-- Observe the paired execution animation starting, never ability activation or target availability.
local Executions={}
Executions.__index=Executions
function Executions.new(observer,settings,valid,log,changed)
    local allowed={}
    for _,name in ipairs(settings.ExecutionClasses)do allowed[name]=true end
    return setmetatable({observer=observer,settings=settings,valid=valid,log=log,changed=changed,
        allowed=allowed,hooks={},classes={},pending={},waiting={},serial=0,enabled=true},Executions)
end
function Executions:key(object)return self.valid(object) and tostring(object:GetAddress()) or "" end
function Executions:health(actor)
    if not self.valid(actor) or not self.valid(actor.AttributeSetBase) then return nil end
    return actor.AttributeSetBase.Health.CurrentValue
end
function Executions:actor(value)
    if self.valid(value) then return value end
    local ok,actor=pcall(function()return value:Get()end)
    return ok and actor or nil
end
function Executions:begin(ability)
    if not self.enabled or not self.valid(ability) then return end
    local name=self.observer:className(ability)
    if not self.allowed[name] then return end
    local state=self.observer:sample()
    if not state.active or state.paused or state.inMenu or self:key(ability:GetAvatarActorFromActorInfo())~=state.player then return end
    local key=self:key(ability)
    if self.pending[key] then return end
    -- Play Execution calls PlayTimeline in build 26266538. Its post hook must
    -- observe that exact timeline running; merely selecting a live target is insufficient.
    local timeline=ability.ExecutionTimeline
    if not self.valid(timeline) or ability:IsPlayingTimeline(timeline)~=true then
        self.log("EXECUTION_START_IGNORED "..name.."; execution timeline is not playing")
        return
    end
    local info=ability["Execution Info"]
    if info==nil or info.IsTarget~=false or self:key(self:actor(info.Executor))~=state.player then
        self.log("EXECUTION_START_IGNORED "..name.."; local player is not the executor")
        return
    end
    local target=self:actor(info.Target)
    local hp=self:health(target)
    if type(hp)~="number" or hp<=0 then return end
    if self:key(target)==state.player then return end
    self.serial=self.serial+1
    local id=state.player..":"..self.serial
    local entry={id=id,time=os.time(),player=state.player,name=name}
    self.pending[key]=entry
    self.waiting[id]=entry
    local delay=self.settings.ExecutionVoiceDelayMs
    self.log("EXECUTION_BEGIN "..name.."; target="..self:key(target).."; source=Play Execution; timeline playing; voice_delay_ms="..delay)
    -- UE4SS delays run asynchronously. Read game objects and publish only after
    -- returning to the game thread; os.time() is too coarse for this delay.
    local ok,err=pcall(function()
        ExecuteWithDelay(delay,self:protect(function()
            ExecuteInGameThread(self:protect(function()self:deliver(id)end))
        end))
    end)
    if not ok then
        self.waiting[id]=nil
        self.log("EXECUTION_DELAY_ERROR "..tostring(err))
    end
end
function Executions:deliver(id)
    local entry=self.waiting[id]
    if not entry then return end
    self.waiting[id]=nil
    if not self.enabled then return end
    local state=self.observer:sample()
    if not state.active or state.player~=entry.player then return end
    -- Target health and animation were confirmed at the start. Do not require
    -- them again after the delay, or a short execution would lose its cue.
    -- Menus already hold voice playback in the audio adapter until resumed.
    if self.observer.core:executionStarted(id,{local_player=true,drunk_sword=true,target_was_alive=true}) then
        self.log("EXECUTION_VOICE "..entry.name.."; delayed Jamie wins requested")
        self.changed()
    end
end
function Executions:finish(ability)
    if self.valid(ability) then self.pending[self:key(ability)]=nil end
end
function Executions:protect(fn)
    return function(...)
        local ok,err=pcall(fn,...)
        if not ok then self.log("EXECUTION_HOOK_ERROR "..tostring(err)) end
    end
end
function Executions:update(player,now,active)
    for key,entry in pairs(self.pending)do
        if entry.player~=player or now-entry.time>30 then self.pending[key]=nil end
    end
    for id,entry in pairs(self.waiting)do
        if not self.enabled or active==false or entry.player~=player or now-entry.time>30 then self.waiting[id]=nil end
    end
    if not self.enabled or self.lastInstall==now then return end
    self.lastInstall=now
    for _,name in ipairs(self.settings.ExecutionClasses)do
        if not self.valid(self.classes[name]) then self.classes[name]=FindObject(nil,name) end
        local current=self.classes[name]
        while self.valid(current)do
            current:ForEachFunction(function(fn)
                local short=fn:GetFName():ToString()
                if short~="Play Execution" and short~="K2_OnEndAbility" then return end
                local path=fn:GetFullName():gsub("^%S+%s+","")
                if self.hooks[path] then return end
                local callback=self:protect(function(ctx)
                    if short=="Play Execution" then self:begin(ctx:get()) else self:finish(ctx:get()) end
                end)
                local ok=pcall(function()
                    if path:sub(1,8)=="/Script/" then RegisterHook(path,function()end,callback)
                    else RegisterHook(path,callback) end
                end)
                if ok then self.hooks[path]=true;self.log("EXECUTION_HOOK "..path) end
            end)
            current=current:GetSuperStruct()
        end
    end
end
return Executions
