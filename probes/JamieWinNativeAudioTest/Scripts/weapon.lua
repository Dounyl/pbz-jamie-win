-- Read the active slot, not every weapon carried in the inventory.
local Weapon = {}

function Weapon.held(pawn, expectedConfig, valid)
    local component = pawn["Character Weapons Component"]
    if not valid(component) then return false, "component unavailable" end
    local held, names = false, {}
    component.RuntimeWeaponData:ForEach(function(slotRef, dataRef)
        local slot, data = slotRef:get(), dataRef:get()
        local index = component:GetCurrentWeaponIndex(slot, false)
        if type(index) == "number" and index >= 0 and index < #data.Weapons then
            local config = data.Weapons[index + 1].WeaponConfig
            local name = valid(config) and config:GetFName():ToString() or "unavailable"
            local armed = component:IsArmed(slot) == true
            names[#names + 1] = slot.TagName:ToString() .. "=" .. name .. ";armed=" .. tostring(armed)
            if name == expectedConfig and armed then held = true end
        end
    end)
    table.sort(names)
    return held, table.concat(names, ",")
end

return Weapon
