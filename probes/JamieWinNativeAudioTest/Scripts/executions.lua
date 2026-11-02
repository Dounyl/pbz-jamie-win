-- The four execution classes and activation timing are shared with the verified legacy adapter.
local Executions={}
Executions.__index=Executions
function Executions.new(observer,settings,valid,log,changed)
    local allowed={}
    for _,name in ipairs(settings.ExecutionClasses)do allowed[name]=true end
    return setmetatable({observer=observer,settings=settings,valid=valid,log=log,changed=changed,
        allowed=allowed,hooks={},classes={},pending={},serial=0,enabled=true},Executions)
end
function Executions:key(object)return self.valid(object) and tostring(object:GetAddress()) or "" end
function Executions:health(actor)
    if not self.valid(actor) or not self.valid(actor.AttributeSetBase) then return nil end
    return actor.AttributeSetBase.Health.CurrentValue
end
function Executions:target(ability)
    if self.observer:className(ability):find("GA_SimpleExecution_",1,true) then return ability.ExecutionTarget end
    local target=ability["Execution Info"].Target
    if self.valid(target) then return target end
    local ok,value=pcall(function()return target:Get()end)
    return ok and value or nil
end
function Executions:begin(ability)
    if not self.enabled or not self.valid(ability) then return end
    local name=self.observer:className(ability)
    if not self.allowed[name] then return end
    local state=self.observer:sample()
    if not state.active or state.paused or state.inMenu or self:key(ability:GetAvatarActorFromActorInfo())~=state.player then return end
    local key=self:key(ability)
    if self.pending[key] then return end
    local hp=self:health(self:target(ability))
    if type(hp)~="number" or hp<=0 then return end
    self.serial=self.serial+1
    local id=state.player..":"..self.serial
    self.pending[key]={time=os.time(),player=state.player}
    if self.observer.core:executionStarted(id,{local_player=true,drunk_sword=true,target_was_alive=true}) then
        self.log("EXECUTION_BEGIN "..name.."; Jamie wins requested at activation")
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
function Executions:update(player,now)
    for key,entry in pairs(self.pending)do
        if entry.player~=player or now-entry.time>30 then self.pending[key]=nil end
    end
    if not self.enabled or self.lastInstall==now then return end
    self.lastInstall=now
    for _,name in ipairs(self.settings.ExecutionClasses)do
        if not self.valid(self.classes[name]) then self.classes[name]=FindObject(nil,name) end
        local current=self.classes[name]
        while self.valid(current)do
            current:ForEachFunction(function(fn)
                local short=fn:GetFName():ToString()
                if short~="K2_ActivateAbility" and short~="K2_OnEndAbility" then return end
                local path=fn:GetFullName():gsub("^%S+%s+","")
                if self.hooks[path] then return end
                local callback=self:protect(function(ctx)
                    if short=="K2_ActivateAbility" then self:begin(ctx:get()) else self:finish(ctx:get()) end
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
