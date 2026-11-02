local Autostart = {}

function Autostart.start(root, valid, find)
    local executable = (root .. "/Player/JamieWin.Audio.exe"):gsub("/", "\\")
    local file = io.open(executable, "rb")
    if not file then return "missing" end
    file:close()
    local system = find("/Script/Engine.Default__KismetSystemLibrary")
    if not valid(system) then return "waiting" end
    -- The game launches a windowless executable directly; no command shell is involved.
    system:LaunchURL(executable)
    return "started"
end

return Autostart
