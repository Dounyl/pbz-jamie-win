-- In-process music and voice playback, driven by observed game state.
local source=debug.getinfo(1,"S").source:gsub("^@",""):gsub("\\","/")
local root=assert(source:match("^(.*)/Scripts/[^/]+$"),"Cannot locate native mod")
local function module(name)return dofile(root.."/Scripts/"..name..".lua")end
local config,settings=module("probe_settings"),module("settings")
local Core,Weapon=module("core"),module("weapon")
local Gameplay,Audio=module("gameplay"),module("native_audio")
local GameAudio,Executions=module("game_audio"),module("executions")
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
local queued,stopped,stopRequested=false,false,false
local lastState,lastError,executions,schedule
local function inactive(reason)
    return {active=false,track="none",player="",controller=observer.controller,detail=reason}
end
local function tick()
    local now=os.time()
    if stopRequested then
        executions.enabled=false
        audio:update(inactive("F10"),now)
        if audio:isStopped(now) then
            stopped=true
            log("STOPPED F10; native output stopped and original music restored; restart game to enable again")
        end
        return
    end
    local state=observer:sample()
    executions:update(state.player,now,state.active)
    local diagnostic="track="..state.track.."; state="..state.state.."; player="..state.player
        .."; paused="..tostring(state.paused).."; menu="..tostring(state.inMenu).."; drink="..state.heavy.."; wins="..state.wins.."; "..state.detail
    if diagnostic~=lastState then lastState=diagnostic;log("GAMEPLAY "..diagnostic) end
    audio:update(state,now)
end
schedule=function()
    if queued or stopped then return end
    queued=true
    local scheduled,scheduleError=pcall(function()
        ExecuteInGameThread(function()
            local ok,err=pcall(tick)
            if not ok then
                audio:update(inactive("observation/API error"),os.time())
                if tostring(err)~=lastError then lastError=tostring(err);log("FAIL "..lastError) end
            else lastError=nil end
            queued=false
        end)
    end)
    if not scheduled then
        queued=false
        audio:reset("game thread schedule error")
        if tostring(scheduleError)~=lastError then lastError=tostring(scheduleError);log("FAIL "..lastError) end
    end
end
executions=Executions.new(observer,settings,valid,log,schedule)
log("BOOT "..config.Version.."; real gameplay; in-process music+voices; follows game sliders; F10 stops")
log("SCOPE mute/restore original music; four-drink cue; paired execution animation start cue; voice overlay without music ducking; menu lowpass with continuous music")
local keyOk,keyError=pcall(function()
    RegisterKeyBindAsync(Key.F10,function()stopRequested=true end)
end)
if not keyOk then log("WARNING F10 unavailable: "..tostring(keyError)) end
LoopAsync(settings.PollMs,function()
    if stopped then return true end
    schedule()
    return stopped
end)
