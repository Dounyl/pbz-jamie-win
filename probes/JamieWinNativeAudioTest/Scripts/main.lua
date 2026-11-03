-- In-process music and voice playback, driven by observed game state.
local source=debug.getinfo(1,"S").source:gsub("^@",""):gsub("\\","/")
local root=assert(source:match("^(.*)/Scripts/[^/]+$"),"Cannot locate native mod")
local function module(name)return dofile(root.."/Scripts/"..name..".lua")end
local config,settings=module("probe_settings"),module("settings")
local Core,Weapon=module("core"),module("weapon")
local Gameplay,Audio=module("gameplay"),module("native_audio")
local GameAudio,Executions=module("game_audio"),module("executions")
local Events=module("game_events")
local function log(message)
    print("[JamieWinNativeAudioTest] "..message.."\n")
    local file=io.open(root.."/runtime/native-audio-test.log","a")
    if file then file:write(os.date("%Y-%m-%d %H:%M:%S "),message,"\n");file:close() end
end
local function valid(object)
    if object==nil then return false end
    local ok,result=pcall(function()return object:IsValid()end)
    return ok and result==true
end
local observer=Gameplay.new(Core,Weapon,settings,valid)
local audio=Audio.new(root,config,valid,log,GameAudio.new(valid,log))
local queued,stopped,stopRequested,dirty=false,false,false,true
local lastState,lastError,executions,events,schedule
local function inactive(reason)
    return {active=false,track="none",player="",controller=observer.controller,detail=reason}
end
local function tick(refresh)
    local now=os.time()
    if stopRequested then
        executions.enabled=false
        events:stop()
        audio:update(inactive("F10"),now)
        if audio:isStopped(now) then
            stopped=true
            log("STOPPED F10; native output stopped and original music restored; restart game to enable again")
        end
        return
    end
    if not refresh then audio:service(now);return end
    events:refresh()
    if events.forceInactive then
        events.forceInactive=false
        executions:cancel()
        audio:update(inactive("lifecycle change"),now)
    end
    if events.transitioning then return end
    local state=observer:sample()
    if events:playerEnded(state) then state=observer:inactive("player ended") end
    events:watchCurrent(state)
    executions:update(state.player,now,state.active)
    local diagnostic="track="..state.track.."; state="..state.state.."; player="..state.player
        .."; paused="..tostring(state.paused).."; menu="..tostring(state.inMenu).."; drink="..state.heavy.."; wins="..state.wins.."; "..state.detail
    if diagnostic~=lastState then lastState=diagnostic;log("GAMEPLAY "..diagnostic) end
    audio:update(state,now)
end
schedule=function(refresh)
    if refresh then dirty=true end
    if queued or stopped then return end
    queued=true
    local scheduled,scheduleError=pcall(function()
        ExecuteInGameThread(function()
            local refreshState=dirty
            dirty=false
            local ok,err=pcall(tick,refreshState)
            if not ok then
                executions:cancel()
                audio:update(inactive("observation/API error"),os.time())
                if tostring(err)~=lastError then lastError=tostring(err);log("FAIL "..lastError) end
            else lastError=nil end
            queued=false
            -- Hooks may fire while processing a snapshot or an audio restore.
            -- Keep that notification for the next frame instead of dropping it.
            if dirty and not stopped then schedule(false) end
        end)
    end)
    if not scheduled then
        queued=false
        audio:reset("game thread schedule error")
        if tostring(scheduleError)~=lastError then lastError=tostring(scheduleError);log("FAIL "..lastError) end
    end
end
local function changed()schedule(true)end
executions=Executions.new(observer,settings,valid,log,changed)
events=Events.new(observer,settings,valid,log,changed)
log("BOOT "..config.Version.."; real gameplay; in-process music+voices; follows game sliders; F10 stops")
log("SCOPE mute/restore original music; four-drink cue; paired execution animation start cue; voice overlay without music ducking; menu lowpass with continuous music")
local keyOk,keyError=pcall(function()
    RegisterKeyBindAsync(Key.F10,function()stopRequested=true;schedule(false)end)
end)
if not keyOk then log("WARNING F10 unavailable: "..tostring(keyError)) end
LoopAsync(settings.AudioServiceMs,function()
    if stopped then return true end
    if stopRequested or audio:needsService() then schedule(false) end
    return stopped
end)
schedule(true) -- one initial snapshot, followed exclusively by gameplay events
