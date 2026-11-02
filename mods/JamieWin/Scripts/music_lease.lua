-- Two-way handoff: mute -> grant -> play; revoke -> player stops -> restore.
-- A dead companion cannot leave the game muted beyond the heartbeat lease.
local Lease = {}
Lease.__index = Lease

function Lease.new(mute, restore, session, confirm)
    return setmetatable({ mute = mute, restore = restore, session = session, confirm = confirm,
        muted = false, confirmed = false, ticks = 0, grant = "-", leaseSeconds = 3,
        retryAt = 0 }, Lease)
end

function Lease:update(wanted, request, now)
    -- A truncated concurrent file write is not an idle acknowledgement.
    if request and request.session == self.session and (not self.request
        or request.id ~= self.request.id or request.sequence > self.request.sequence) then
        self.request = request
    end
    request = self.request
    local fresh = request and request.session == self.session and request.time <= now + 2
        and now - request.time <= self.leaseSeconds
    local owns = fresh and request.mode == "want" and request.id ~= "-"
    self.grant = "-"
    if wanted and owns and now >= self.retryAt then
        if not self.muted then
            self.muted = self.mute() == true
            self.ticks, self.confirmed, self.muteStarted = 0, false, now
            if not self.muted then self.retryAt = now + 1 end
        end
        if self.muted then
            self.ticks = self.ticks + 1
            -- Audio commands are queued; never verify in the same game tick as the write.
            if self.ticks >= 2 then
                if not self.confirmed then
                    self.confirmed = not self.confirm or self.confirm() == true
                    if not self.confirmed and now - self.muteStarted >= 3 then
                        -- Do not leave the game silent if confirmation cannot be obtained.
                        if self.restore() == true then
                            self.muted, self.ticks, self.retryAt = false, 0, now + 5
                        end
                    end
                end
                if self.confirmed then self.grant = request.id end
            end
        end
    elseif self.muted and (not fresh or request.mode == "idle") then
        -- The companion acknowledges idle only AFTER it has stopped its music.
        if self.restore() == true then self.muted, self.confirmed, self.ticks = false, false, 0 end
    end
    return self.grant
end

function Lease.parse(text)
    local session, sequence, time, id, mode = text:match(
        "^JWA2|([%w%-]+)|(%d+)|(%d+)|([%w%-]+)|(%a+)|END\n$")
    if not session or (mode ~= "want" and mode ~= "idle") then return nil end
    return { session = session, sequence = tonumber(sequence), time = tonumber(time), id = id, mode = mode }
end

return Lease
