using System;
using JamieWin;

public static class ProtocolTests
{
    static int count;
    static void Check(bool ok, string message)
    { count++; if (!ok) throw new Exception(message); }
    static Snapshot State(long sequence, string state, long heavy, long wins, string grant, string track = null)
    { return Snapshot.Parse((track == null ? "JW2" : "JW3") + "|game1|" + sequence + "|100|" + state + "|" + heavy + "|" + wins + "|" + grant + (track == null ? "" : "|" + track) + "|END\n"); }
    public static int Main()
    {
        Check(Snapshot.Parse("JW2|partial") == null, "reject partial snapshots");
        Check(Snapshot.Parse("JW2|g|1|100|drunk|-1|0|-|END\n") == null, "reject negative counters");
        var h = new Handoff();
        Check(h.Accept(State(1, "sober", 0, 0, "-")), "accept baseline");
        Check(!h.CanPlay(true, true), "sober must not play music");
        h.Accept(State(2, "tipsy", 0, 0, "-"));
        Check(h.Mode(true, true) == "want" && !h.CanPlay(true, true), "wait for mute acknowledgement");
        Check(h.Mode(false, true) == "idle", "decode failure must not silence original music");
        h.Accept(State(3, "tipsy", 0, 0, h.Request));
        Check(h.CanPlay(true, true), "matching grant permits music");
        Check(!h.CanPlay(true, false), "game watchdog stops music");
        h.Accept(State(4, "drunk", 1, 0, h.Request));
        Check(h.NewDrink && h.CanPlay(true, true), "tipsy to drunk keeps music and adds cue");
        Check(!h.Accept(State(4, "drunk", 1, 0, h.Request)) && !h.NewDrink, "duplicate snapshot cannot replay cue");
        h.Accept(State(5, "sober", 1, 1, "-"));
        Check(h.NewWin && !h.CanPlay(true, true), "win may finish as drunk state expires");
        h.Revoke(); var old = h.Request; h.Revoke();
        h.Accept(State(6, "tipsy", 1, 1, old));
        Check(!h.CanPlay(true, true), "old grant cannot resume after idle/recovery");
        var reconnected = new Handoff();
        reconnected.Accept(State(7, "drunk", 9, 8, "-"));
        Check(!reconnected.NewDrink && !reconnected.NewWin, "reconnect never replays historical cues");
        var themes = new Handoff();
        themes.Accept(State(1, "sober", 0, 0, "-", "armed"));
        Check(themes.Mode(true,true)=="want" && !themes.CanPlay(true,true), "held sword requests mute first");
        var request = themes.Request;
        themes.Accept(State(2, "sober", 0, 0, request, "armed"));
        Check(themes.CanPlay(true,true), "sober held sword permits theme after grant");
        themes.Accept(State(3, "tipsy", 0, 0, request, "drunk"));
        Check(themes.CanPlay(true,true) && themes.Request==request, "track switch keeps the native music lease");
        themes.Accept(State(4, "sober", 0, 0, request, "armed"));
        Check(themes.CanPlay(true,true), "sobering up returns to held sword theme");
        themes.Accept(State(5, "sober", 0, 0, request, "none"));
        Check(themes.Mode(true,true)=="idle", "sheathed or replaced sword releases music");
        Check(State(6,"unknown",0,0,request,"armed")==null, "unknown player cannot request a track");
        Check(State(6,"drunk",0,0,request,"armed")==null, "drunk state must choose drunk theme");
        Console.WriteLine("PASS " + count + " audio protocol checks");
        return 0;
    }
}
