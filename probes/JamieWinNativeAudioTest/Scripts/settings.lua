return {
    AudioServiceMs = 200, -- native heartbeat/ack only; never samples gameplay
    ExecutionVoiceDelayMs = 2000,
    -- Reflected classes observed in this user's Steam build 26266538 header dump.
    -- Runtime transition checks are still required for final game acceptance.
    TipsyEffect = "GE_ChiZheCanJian_Prezui_3_C",
    DrunkEffect = "GE_ChiZheCanJian_Zui_C",
    InfiniteDrunkEffect = "GE_ChiZheCanJian_Zui_Infinite_C",
    DrunkSwordWeaponConfig = "Weapon_Hun_ChiZheZuiJian",
    -- Paired executor abilities only. SimpleExecution also runs during ordinary
    -- attacks and can retain a live ExecutionTarget without starting a finisher.
    ExecutionClasses = {
        "GA_Hun_BEx_ChiZheCanJian_M_01_C",
        "GA_Hun_BEx_ChiZheCanJian_M_02_C",
    },
}
