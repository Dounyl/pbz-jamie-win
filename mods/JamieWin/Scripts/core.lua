-- Pure state machine. The adapter supplies observed game facts, never input keys.
local Core = {}
Core.__index = Core

function Core.new()
    return setmetatable({ state = "unknown", stable = "unknown", player = "", heavy = 0, wins = 0,
        track = "none", seen = {}, order = {} }, Core)
end

function Core:observe(player, alive, state, holdingSword)
    if player ~= self.player then
        self.player, self.state, self.stable = player or "", "unknown", "unknown"
        self.seen, self.order = {}, {}
    end
    if alive ~= true then state = "unknown" end
    if state ~= "sober" and state ~= "tipsy" and state ~= "drunk" then state = "unknown" end
    if state == "drunk" and self.stable ~= "drunk" then self.heavy = self.heavy + 1 end
    if state ~= "unknown" then self.stable = state end
    self.state = state
    if state == "tipsy" or state == "drunk" then self.track = "drunk"
    elseif state == "sober" and holdingSword == true then self.track = "armed"
    else self.track = "none" end
end

function Core:executionStarted(id, facts)
    if self.seen[id] or not facts.local_player or not facts.drunk_sword
        or facts.target_was_alive ~= true then return false end
    self.seen[id] = true
    self.order[#self.order + 1] = id
    if #self.order > 128 then self.seen[table.remove(self.order, 1)] = nil end
    self.wins = self.wins + 1
    return true
end

return Core
