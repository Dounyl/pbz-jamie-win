local Config = require("settings")
local Core = require("core")
local Lease = require("music_lease")
local Weapon = require("weapon")
local Autostart = require("autostart")
local source = debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/")
local root = assert(source:match("^(.*)/Scripts/[^/]+$"), "Cannot locate JamieWin folder")
local bridge = root .. "/runtime/bridge.txt"
local logpath = root .. "/runtime/game.log"
local requestPath = root .. "/runtime/audio-request.txt"
local session = tostring(os.time()) .. "-" .. tostring({}):gsub("[^%w]", "")
local core = Core.new()
local sequence, activation = 0, 0
local pawn, controller
local classes, hooks, pending = {}, {}, {}
local executionClasses = {}
for _, name in ipairs(Config.ExecutionClasses) do executionClasses[name] = true end
local lastStatus, lastError, lastRefresh, lastWeapon = "", "", 0, ""
local musicLease, soundSubsystem, settingsObject
local musicRtpc, akStatics
local savedMusicVolume, ownVolumeCall = nil, false
local audioReady, nextAudioProbe = false, 0
local muteBefore, pendingRestoreVolume, restoreCheckStarted
local companionRequested = false
local function log(message)
    print("[JamieWin] " .. message .. "\n")
    local file = io.open(logpath, "a")
    if file then file:write(os.date("%Y-%m-%d %H:%M:%S "), message, "\n"); file:close() end
end
local function valid(object)
    if object == nil then return false end
    local ok, result = pcall(function() return object:IsValid() end)
    return ok and result == true
end
local function key(object)
    return valid(object) and tostring(object:GetAddress()) or ""
end
local function className(object)
    return valid(object) and object:GetClass():GetFName():ToString() or ""
end
local function class(name)
    if not valid(classes[name]) then
        -- PBZ uses custom generated class types as well as BlueprintGeneratedClass.
        classes[name] = FindObject(nil, name)
    end
    return classes[name]
end
local function health(actor)
    if not valid(actor) then return nil end
    local ok, value = pcall(function()
        local attributes = actor.AttributeSetBase
        if valid(attributes) then return attributes.Health.CurrentValue end
    end)
    return ok and type(value) == "number" and value or nil
end
local function publish()
    sequence = sequence + 1
    local line = string.format("JW3|%s|%d|%d|%s|%d|%d|%s|%s|END\n",
        session, sequence, os.time(), core.state, core.heavy, core.wins,
        musicLease and musicLease.grant or "-", core.track)
    local file, err = io.open(bridge, "w")
    if not file then error("bridge write failed: " .. tostring(err)) end
    file:write(line); file:close()
end
local function resolveAudio()
    if valid(controller) and valid(controller.Player) then
        local obj = controller.Player.SharedSettings
        if valid(obj) then settingsObject = obj end
    end
    if not valid(soundSubsystem) then
        for _, item in ipairs(FindAllOf("PBZSoundFXSubsystem") or {}) do
            if valid(item) and not item:GetFName():ToString():find("^Default__") then
                soundSubsystem = item
                break
            end
        end
    end
    return valid(soundSubsystem) and valid(settingsObject)
end
local function readMusicRtpc()
    if not valid(akStatics) then akStatics = StaticFindObject("/Script/AkAudio.Default__AkGameplayStatics") end
    if not valid(musicRtpc) then
        -- The volume RTPC is a soft reference and was absent from the live object dump.
        -- Resolve the game's authoritative configuration, not a similarly named battle RTPC.
        local gameConfig = StaticFindObject("/Script/ProjectPBZ.Default__PBZGameSettings")
        local system = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
        if valid(gameConfig) and valid(system) then
            musicRtpc = system:LoadAsset_Blocking(gameConfig.Volume_Music)
            if valid(musicRtpc) then log("MUSIC RTPC " .. musicRtpc:GetFullName()) end
        end
    end
    if not valid(akStatics) or not valid(musicRtpc) then return nil end
    local value, kind = {}, {}
    akStatics:GetRTPCValue(musicRtpc, 0, 1, value, kind, nil)
    if kind.OutputValueType == 4 then return nil end
    return type(value.Value) == "number" and value.Value or nil
end
local function setRuntimeMusic(volume)
    ownVolumeCall = true
    local ok, err = pcall(function() soundSubsystem:SetAudioVolume(2, volume) end)
    ownVolumeCall = false
    if not ok then error(err) end
end
musicLease = Lease.new(function()
    if not resolveAudio() then return false end
    local volume = settingsObject.MusicVolume
    if type(volume) ~= "number" then return false end
    local before = readMusicRtpc()
    if before == nil then
        if lastError ~= "Music RTPC unavailable" then lastError = "Music RTPC unavailable"; log(lastError) end
        return false
    end
    savedMusicVolume = volume
    muteBefore, pendingRestoreVolume = before, nil
    -- Own the change before making the call so an exception still leads to restoration.
    musicLease.muted = true
    setRuntimeMusic(0)
    log("MUSIC mute requested; RTPC before=" .. tostring(before)
        .. "; saved preference=" .. tostring(volume))
    return true
end, function()
    if not resolveAudio() then return false end
    local volume = settingsObject.MusicVolume
    if type(volume) ~= "number" then volume = savedMusicVolume end
    if type(volume) ~= "number" then return false end
    setRuntimeMusic(volume)
    pendingRestoreVolume, restoreCheckStarted = volume, os.time()
    log("MUSIC restore requested; preference=" .. tostring(volume))
    savedMusicVolume = nil
    return true
end, session, function()
    local after = readMusicRtpc()
    if after ~= nil and math.abs(after) <= 0.001 then
        log("MUSIC muted confirmed; RTPC=" .. tostring(muteBefore) .. " -> " .. tostring(after))
        return true
    end
    return false
end)
local function updateMusicLease()
    if pendingRestoreVolume ~= nil then
        local after = readMusicRtpc()
        if after ~= nil and math.abs(after - pendingRestoreVolume) <= 0.001 then
            log("MUSIC restored confirmed; RTPC=" .. tostring(after))
            pendingRestoreVolume = nil
        elseif os.time() - restoreCheckStarted >= 5 then
            log("MUSIC restore readback mismatch; expected=" .. tostring(pendingRestoreVolume)
                .. "; RTPC=" .. tostring(after))
            pendingRestoreVolume = nil
        end
    end
    local file = io.open(requestPath, "r")
    local request
    if file then request = Lease.parse(file:read("*a")); file:close() end
    musicLease:update(core.track ~= "none", request, os.time())
end
local function refreshPlayer()
    if valid(controller) and valid(controller.Player) and valid(controller.Pawn) then
        pawn = controller.Pawn
        return
    end
    controller, pawn = nil, nil
    for _, item in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(item) and valid(item.Player) and valid(item.Pawn)
            and not className(item):find("DebugCamera", 1, true) then
            controller, pawn = item, item.Pawn
            break
        end
    end
end
local function weakActor(value)
    if valid(value) then return value end
    local ok, object = pcall(function() return value:Get() end)
    if ok and valid(object) then return object end
    return nil
end
local function targetOf(ability)
    if className(ability):find("GA_SimpleExecution_", 1, true) then return ability.ExecutionTarget end
    return weakActor(ability["Execution Info"].Target)
end
local function localAbility(ability)
    if not valid(ability) or not executionClasses[className(ability)] then return false end
    return valid(pawn) and key(ability:GetAvatarActorFromActorInfo()) == key(pawn)
end
local function beginExecution(ability)
    if not localAbility(ability) then return end
    local id = key(ability)
    if pending[id] then return end -- inherited Blueprint calls share the same activation
    local target = targetOf(ability)
    local hp = health(target)
    if not hp or hp <= 0 then
        log("EXECUTION ignored: no live target; class=" .. className(ability))
        return
    end
    activation = activation + 1
    pending[id] = { id = session .. ":" .. activation, ability = ability, target = target,
        targetKey = key(target), playerKey = key(pawn), wasAlive = true,
        started = os.time(), name = className(ability) }
    local entry = pending[id]
    entry.voiced = core:executionStarted(entry.id, { local_player = true,
        drunk_sword = true, target_was_alive = true })
    log("EXECUTION begin " .. entry.name .. " target=" .. entry.targetKey
        .. "; voice now=" .. tostring(entry.voiced))
    if entry.voiced then publish() end -- notify the player immediately, not on the next poll
end
local function endExecution(ability, cancelled)
    if not valid(ability) or not executionClasses[className(ability)] then return end
    local id = key(ability)
    local entry = pending[id]
    if not entry then return end
    pending[id] = nil
    local hp = health(entry.target)
    log("EXECUTION end cancelled=" .. tostring(cancelled)
        .. " dead=" .. tostring(hp ~= nil and hp <= 0)
        .. " voiced=" .. tostring(entry.voiced == true) .. " class=" .. entry.name)
end
local function protect(callback)
    return function(...)
        local ok, err = pcall(callback, ...)
        if not ok and tostring(err) ~= lastError then
            lastError = tostring(err); log("ERROR " .. lastError)
        end
        -- Never return a value: hook return values could change game behavior.
    end
end
local function installHooks()
    local volumePath = "/Script/ProjectPBZ.PBZSoundFXSubsystem:SetAudioVolume"
    if not hooks[volumePath] then
        RegisterHook(volumePath, protect(function(_, kind, volume)
            if musicLease.muted and not ownVolumeCall and kind:get() == 2 then
                volume:set(0) -- Keep menu/reinitialization calls from unmuting underneath the mod.
            end
        end))
        hooks[volumePath] = true
        log("HOOK " .. volumePath)
    end
    for _, name in ipairs(Config.ExecutionClasses) do
        local current = class(name)
        while valid(current) do
            current:ForEachFunction(function(fn)
                local short = fn:GetFName():ToString()
                if short ~= "K2_ActivateAbility" and short ~= "K2_OnEndAbility" then return end
                local path = fn:GetFullName():gsub("^%S+%s+", "")
                if hooks[path] then return end
                local callback
                if short == "K2_ActivateAbility" then
                    callback = protect(function(ctx) beginExecution(ctx:get()) end)
                else
                    callback = protect(function(ctx, cancelled) endExecution(ctx:get(), cancelled:get()) end)
                end
                local ok, err = pcall(function()
                    if path:sub(1, 8) == "/Script/" then
                        RegisterHook(path, function() end, callback)
                    else
                        RegisterHook(path, callback)
                    end
                end)
                if not ok then
                    -- A class may exist before its bytecode is ready. Retry without blocking other hooks.
                    return
                end
                hooks[path] = true
                log("HOOK " .. path)
            end)
            current = current:GetSuperStruct()
        end
    end
end
local function observeEffects()
    local active = pawn.AbilitySystemComponent.ActiveGameplayEffects.GameplayEffects_Internal
    local state, names = "sober", {}
    for index = 1, #active do
        local effect = active[index]
        if not effect.bIsInhibited then
            local name = className(effect.Spec.Def)
            if name:find("ChiZhe", 1, true) then names[#names + 1] = name end
            if name == Config.DrunkEffect or name == Config.InfiniteDrunkEffect then
                state = "drunk"
            elseif name == Config.TipsyEffect and state ~= "drunk" then
                state = "tipsy"
            end
        end
    end
    table.sort(names)
    local diagnostic = state .. " effects=" .. table.concat(names, ",")
    if diagnostic ~= lastStatus then lastStatus = diagnostic; log("STATE " .. diagnostic) end
    return state
end
local function tick()
    if not companionRequested then
        local ok, result = pcall(Autostart.start, root, valid, StaticFindObject)
        if not ok or result ~= "waiting" then
            companionRequested = true
            log("AUDIO autostart " .. tostring(result))
        end
    end
    if os.time() ~= lastRefresh then
        refreshPlayer()
        local ok, err = pcall(installHooks)
        if not ok and tostring(err) ~= lastError then lastError = tostring(err); log("HOOK ERROR " .. lastError) end
        lastRefresh = os.time()
    end
    local playerKey = key(pawn)
    if playerKey ~= core.player then pending = {} end
    local hp = health(pawn)
    if playerKey == "" or hp == nil or hp <= 0 then
        core:observe(playerKey, false, "unknown")
        pending = {}
    else
        local holding, diagnostic = false, ""
        local ok, result, detail = pcall(Weapon.held, pawn, Config.DrunkSwordWeaponConfig, valid)
        if ok then holding, diagnostic = result, detail
        else diagnostic = "ERROR " .. tostring(result) end
        if diagnostic ~= lastWeapon then lastWeapon = diagnostic; log("WEAPON " .. diagnostic) end
        core:observe(playerKey, true, observeEffects(), holding)
        if not audioReady and os.time() >= nextAudioProbe then
            nextAudioProbe = os.time() + 5
            local ok, result = pcall(readMusicRtpc)
            if ok and result ~= nil then
                audioReady = true
                log("MUSIC ready; current RTPC=" .. tostring(result))
            elseif not ok and tostring(result) ~= lastError then
                lastError = tostring(result); log("AUDIO PROBE " .. lastError)
            end
        end
        for id, entry in pairs(pending) do
            if os.time() - entry.started > 30 then pending[id] = nil; log("EXECUTION expired") end
        end
    end
    updateMusicLease()
    publish()
end

log("Loaded v0.8 for Steam build 26266538; audio starts and exits with the game.")
local queued = false
LoopAsync(Config.PollMs, function()
    if not queued then
        queued = true
        ExecuteInGameThread(function()
            local ok, err = pcall(tick)
            if not ok then
                core:observe(core.player, false, "unknown")
                pcall(updateMusicLease)
                pcall(publish)
                if tostring(err) ~= lastError then lastError = tostring(err); log("ERROR " .. lastError) end
            end
            queued = false
        end)
    end
    return false
end)
