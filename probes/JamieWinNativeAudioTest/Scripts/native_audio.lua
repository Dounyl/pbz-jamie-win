-- File snapshots cross the standard Lua C ABI. Only the native worker owns the device.
local Audio={}
Audio.__index=Audio
local tracks={none=0,armed=1,drunk=2}
function Audio.new(root,config,valid,log,gate)
    return setmetatable({root=root,config=config,valid=valid,log=log,gate=assert(gate),
        session=tostring(os.time()).."-"..tostring({}):gsub("[^%w]",""),
        sequence=0,epoch=0,drink=0,win=0,phase="idle",gains={music=0,drink=0,win=0}},Audio)
end
function Audio:load(now)
    if self.api then return end
    local api,dll={},(self.root.."/Native/JamieWinAudio.dll"):gsub("/","\\")
    for _,name in ipairs({"Init","Apply","Stop","Heartbeat"})do
        local fn,err=package.loadlib(dll,"JamieNative_"..name)
        assert(type(fn)=="function","native module load failed: "..tostring(err))
        api[name]=fn
    end
    self.statusPath=self.root.."/runtime/native-status.txt"
    local existing=io.open(self.statusPath,"rb")
    if existing then existing:close();assert(os.remove(self.statusPath),"cannot discard stale native status") end
    api.Init();self.api=api;self.lastSeenAt=now
    self.log("NATIVE_MODULE_LOADED; in-process PCM mixer; game volume sliders; no device-volume calls")
end
function Audio:send(active,track,inMenu,allow,now)
    local g=self.gains
    local body=string.format("%d|%d|%d|%d|%d|%.6f|%.6f|%.6f|%d|%d|END\n",
        self.epoch,active and 1 or 0,tracks[track],inMenu and 1 or 0,allow and 1 or 0,
        g.music,g.drink,g.win,self.drink,self.win)
    if body==self.lastBody then return end
    local sequence=self.sequence+1
    local file=assert(io.open(self.root.."/runtime/native-command.txt","wb"),"cannot write native command")
    local wrote,err=file:write("JWN5|"..self.session.."|"..sequence.."|"..body)
    local closed,closeError=file:close()
    assert(wrote and closed,err or closeError or "cannot finish native command")
    self.api.Apply()
    self.sequence,self.lastBody,self.lastSentAt=sequence,body,now
    if not active then self.stopAt=self.stopAt or now else self.stopAt=nil end
end
function Audio:readStatus(now)
    if not self.statusPath then return nil end
    local file=io.open(self.statusPath,"rb")
    if not file then return nil end
    local data=file:read(2048);file:close()
    local status={}
    for line in (data or ""):gmatch("[^\r\n]+")do
        local key,value=line:match("^([%w_]+)=(.*)$")
        if key then status[key]=value end
    end
    if status.version~=self.config.Version or status.session~=self.session
        or tonumber(status.seq)~=self.sequence or not tonumber(status.tick) then return nil end
    if status.tick~=self.lastTick then self.lastTick,self.lastSeenAt=status.tick,now end
    return status
end
function Audio:fail(reason,now)
    if self.blocked~=self.context then
        self.blocked,self.stopAt=self.context,now
        self.readyEpoch=nil
        self.log("FAIL "..reason.."; retry after gameplay track/player changes")
        if self.api then pcall(self.api.Stop) end
    end
    self.phase="failed"
end
function Audio:safeToRestore(status,now)
    if not self.api then return true end
    if status and status.music_stopped=="1" and now-self.lastSeenAt<1 then return true end
    -- No heartbeat or Apply after stop/failure. Native lease is 3 s and the queue <=80 ms.
    if self.stopAt and now-self.stopAt>=5 then
        if not self.leaseLogged then self.log("STOP_LEASE_EXPIRED; native heartbeat and bounded queue elapsed");self.leaseLogged=true end
        return true
    end
    return false
end
function Audio:tick(state,now)
    local active=state.active==true and self.valid(state.owner)
    local inMenu=active and (state.inMenu==true or state.paused==true)
    local track=active and state.track or "none"
    assert(tracks[track],"invalid gameplay track")
    local player=active and state.player or ""
    local context=player..":"..track..":"..tostring(active)
    local samePlayer=active and self.active and self.player==player
    if self.player~=player or self.active~=active then self.epoch=self.epoch+1;self.readyEpoch=nil end
    if samePlayer then
        if (state.heavy or 0)>(self.lastHeavy or 0) then self.drink=self.drink+1 end
        if (state.wins or 0)>(self.lastWins or 0) then self.win=self.win+1 end
    end
    self.lastHeavy,self.lastWins=state.heavy or 0,state.wins or 0
    self.player,self.active=player,active
    if context~=self.context then
        self.context,self.blocked,self.changedAt=context,nil,now
        self.lastSeenAt=now
        self.progress,self.lastSamples,self.leaseLogged=false,0,false
        self.log("TRACK_REQUEST "..track.."; player="..player)
    end
    self.track=track
    local status=self:readStatus(now)
    if status and tonumber(status.epoch)==self.epoch then
        self.readyEpoch=status.ready=="1" and self.epoch or nil
    end
    if self.blocked~=context and self.api then
        if status and tonumber(status.epoch)==self.epoch and status.track==track and status.phase=="failed" then
            self:fail("native operation="..tostring(status.operation).."; code="..tostring(status.code),now)
        elseif now-self.lastSeenAt>=self.config.StatusTimeoutSeconds then
            self:fail("native status timeout",now)
        end
    end
    if self.blocked==context then
        self.gate:update(false,self:safeToRestore(status,now),state.controller,now)
        return
    end
    -- Wait for a first gameplay observation; once started, menus never pause the music.
    if not self.api and (not active or inMenu or (track=="none" and self.drink==0 and self.win==0)) then
        self.gate:update(false,true,state.controller,now);self.phase="idle";return
    end
    if not self.api then self:load(now) end
    if active then
        self.gains=assert(self.gate:volumes(state.controller),"game volume preferences unavailable")
        self.api.Heartbeat()
    end
    -- All four assets share one prepared device. Keep that fact across brief file contention,
    -- gain updates and song changes; withdrawing permission would restart the music.
    local ready=self.readyEpoch==self.epoch
    local want=active and track~="none" and (ready or self.gate.owned)
    local allow=self.gate:update(want,self:safeToRestore(status,now),state.controller,now) and ready
    self:send(active,track,inMenu,allow,now)
    if self.inMenu~=inMenu then
        self.inMenu=inMenu
        self.log("MENU_FILTER "..(inMenu and "ENTER" or "EXIT").."; continuous music; transition=0.4s")
    end
    -- Only acknowledge the exact snapshot that is still current after sending changes.
    if status and tonumber(status.seq)==self.sequence then
        self.phase=status.phase
        local samples=tonumber(status.samples) or 0
        if samples>self.lastSamples and status.phase=="playing" and not self.progress then
            self.progress=true
            self.log("DEVICE_CLOCK_ADVANCED track="..track.."; pid="..tostring(status.pid).."; listener must confirm audio")
        end
        self.lastSamples=samples
        if active and track~="none" and status.phase~="playing"
            and now-self.changedAt>=self.config.StatusTimeoutSeconds then self:fail("music start/mute timeout",now) end
    else self.phase=active and "waiting" or "stopping" end
end
function Audio:update(state,now)
    local ok,err=pcall(function()self:tick(state,now)end)
    if not ok then self:fail("Lua/native error: "..tostring(err),now) end
end
function Audio:isStopped(now)
    return not self.active and not self.gate.owned and self:safeToRestore(self:readStatus(now),now)
end
function Audio:reset(reason)
    self:fail("emergency stop: "..reason,os.time())
end
return Audio
