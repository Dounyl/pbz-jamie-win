using System;
using System.Collections.Generic;
using System.Globalization;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Media;
using System.Windows.Threading;

namespace JamieWin
{
    public sealed class Options
    {
        public string Bridge { get; set; }
        public string Music { get; set; }
        public string ArmedMusic { get; set; }
        public string Drink { get; set; }
        public string Win { get; set; }
        public string Runtime { get; set; }
        public bool WatchGame { get; set; }
        public string GameExecutable { get; set; }
        public double MusicVolume { get; set; }
        public double DrinkVolume { get; set; }
        public double WinVolume { get; set; }
        public double DuckVolume { get; set; }

        public static Options Load(string path)
        {
            var value = new JavaScriptSerializer().Deserialize<Options>(File.ReadAllText(path));
            var root = Path.GetDirectoryName(Path.GetFullPath(path));
            value.Bridge = Resolve(root, value.Bridge);
            value.Music = Resolve(root, value.Music);
            value.ArmedMusic = Resolve(root, value.ArmedMusic);
            value.Drink = Resolve(root, value.Drink);
            value.Win = Resolve(root, value.Win);
            value.Runtime = Resolve(root, value.Runtime);
            if (value.WatchGame) value.GameExecutable = Resolve(root, value.GameExecutable);
            foreach (var volume in new[] { value.MusicVolume, value.DrinkVolume, value.WinVolume, value.DuckVolume })
                if (double.IsNaN(volume) || volume < 0 || volume > 1) throw new ArgumentException("Volume must be between 0 and 1.");
            return value;
        }
        static string Resolve(string root, string value)
        {
            if (String.IsNullOrWhiteSpace(value)) throw new ArgumentException("Missing path in audio.json.");
            return Path.GetFullPath(Path.IsPathRooted(value) ? value : Path.Combine(root, value));
        }
    }

    public sealed class Snapshot
    {
        public string Session, State, Grant, Track;
        public long Sequence, Time, Heavy, Wins;
        public bool WantsMusic { get { return Track == "armed" || Track == "drunk"; } }
        public static Snapshot Parse(string text)
        {
            if (text == null || text.Length > 2048 || !text.EndsWith("\n")) return null;
            var fields = text.TrimEnd('\r', '\n').Split('|');
            var legacy = fields.Length == 9 && fields[0] == "JW2" && fields[8] == "END";
            if (!legacy && !(fields.Length == 10 && fields[0] == "JW3" && fields[9] == "END")) return null;
            var s = new Snapshot { Session = fields[1], State = fields[4], Grant = fields[7] };
            s.Track = legacy ? (s.State == "tipsy" || s.State == "drunk" ? "drunk" : "none") : fields[8];
            if (!Token(s.Session) || !Token(s.Grant)) return null;
            if (s.State != "unknown" && s.State != "sober" && s.State != "tipsy" && s.State != "drunk") return null;
            if (s.Track != "none" && s.Track != "armed" && s.Track != "drunk") return null;
            if (s.State == "unknown" && s.Track != "none") return null;
            if (s.State == "sober" && s.Track == "drunk") return null;
            if ((s.State == "tipsy" || s.State == "drunk") && s.Track != "drunk") return null;
            if (!Number(fields[2], out s.Sequence) || !Number(fields[3], out s.Time)
                || !Number(fields[5], out s.Heavy) || !Number(fields[6], out s.Wins)) return null;
            return s;
        }
        static bool Number(string text, out long result)
        { return Int64.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out result) && result >= 0; }
        static bool Token(string text)
        {
            if (text.Length == 0 || text.Length > 128) return false;
            foreach (var c in text) if (!(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'z')
                && !(c >= 'A' && c <= 'Z') && c != '-') return false;
            return true;
        }
    }

    // Pure protocol state; every audio start requires a matching game-side grant.
    public sealed class Handoff
    {
        public string Session = "", Request = "-";
        public Snapshot Current;
        public bool NewDrink, NewWin;
        long sequence = -1, heavy, wins;
        public bool Accept(Snapshot next)
        {
            NewDrink = NewWin = false;
            if (next == null) return false;
            if (next.Session != Session)
            {
                Session = next.Session; Request = Guid.NewGuid().ToString("N"); sequence = -1;
                heavy = next.Heavy; wins = next.Wins; // do not replay past effects on reconnect
            }
            if (next.Sequence <= sequence || next.Heavy < heavy || next.Wins < wins) return false;
            NewDrink = next.Heavy > heavy && next.State == "drunk";
            NewWin = next.Wins > wins;
            sequence = next.Sequence; heavy = next.Heavy; wins = next.Wins; Current = next;
            return true;
        }
        public bool CanPlay(bool ready, bool fresh)
        { return ready && fresh && Current != null && Current.WantsMusic && Current.Grant == Request; }
        public string Mode(bool ready, bool fresh)
        { return ready && fresh && Current != null && Current.WantsMusic ? "want" : "idle"; }
        public void Revoke() { Request = Guid.NewGuid().ToString("N"); }
    }

    public sealed class Channel
    {
        readonly MediaPlayer player = new MediaPlayer();
        readonly Action<string> log;
        readonly string label;
        readonly bool loop;
        public bool Ready, Playing, Failed;
        public double Duration;
        public Action Changed = delegate { };
        public Channel(string path, string name, bool repeat, double volume, Action<string> logger)
        {
            log = logger; label = name; loop = repeat; player.Volume = volume;
            player.MediaOpened += delegate
            {
                Ready = player.HasAudio; Failed = !Ready;
                Duration = player.NaturalDuration.HasTimeSpan ? player.NaturalDuration.TimeSpan.TotalSeconds : 0;
                log(label + " opened; seconds=" + Duration.ToString("0.00", CultureInfo.InvariantCulture));
                Changed();
            };
            player.MediaFailed += (sender, e) =>
            { Ready = Playing = false; Failed = true; log(label + " ERROR " + e.ErrorException.Message); Changed(); };
            player.MediaEnded += delegate
            {
                if (loop && Playing) { player.Position = TimeSpan.Zero; player.Play(); }
                else { Playing = false; player.Stop(); Changed(); }
            };
            if (!File.Exists(path)) { Failed = true; log(label + " missing: " + path); return; }
            player.Open(new Uri(path, UriKind.Absolute));
        }
        public void Play(bool restart)
        {
            if (!Ready || (!restart && Playing)) return;
            if (restart) player.Position = TimeSpan.Zero;
            player.Play(); Playing = true; log(label + " play"); Changed();
        }
        public void Stop()
        {
            if (!Playing) return;
            player.Stop(); Playing = false; log(label + " stop"); Changed();
        }
        public void Volume(double value) { player.Volume = value; }
        public void Close() { Playing = false; player.Close(); }
    }

    public sealed class Host
    {
        readonly Options options;
        readonly Handoff handoff = new Handoff();
        readonly Channel music, armedMusic, drink, win;
        Channel currentMusic;
        DateTime musicStartAfter;
        readonly string requestPath, stopPath, logPath;
        readonly bool checkOnly;
        readonly Process gameProcess;
        readonly DispatcherTimer timer = new DispatcherTimer();
        DateTime started = DateTime.UtcNow, lastUpdate = DateTime.MinValue, lastRequest = DateTime.MinValue;
        string lastState = "", lastError = "", lastMode = "idle";
        long requestSequence;
        bool closing;
        public int ExitCode;
        public Host(Options config, bool check)
        {
            options = config; checkOnly = check;
            Directory.CreateDirectory(options.Runtime);
            requestPath = Path.Combine(Path.GetDirectoryName(options.Bridge), "audio-request.txt");
            stopPath = Path.Combine(options.Runtime, "stop");
            logPath = Path.Combine(options.Runtime, check ? "audio-check.log" : "audio.log");
            if (!check && options.WatchGame) gameProcess = FindGame(options.GameExecutable);
            if (!check && File.Exists(stopPath)) File.Delete(stopPath);
            music = new Channel(options.Music, "music", true, options.MusicVolume, Log);
            armedMusic = new Channel(options.ArmedMusic, "armed-music", true, options.MusicVolume, Log);
            drink = new Channel(options.Drink, "drink4", false, options.DrinkVolume, Log);
            win = new Channel(options.Win, "jamie-win", false, options.WinVolume, Log);
            drink.Changed = win.Changed = delegate
            {
                var volume = drink.Playing || win.Playing ? options.DuckVolume : options.MusicVolume;
                music.Volume(volume); armedMusic.Volume(volume);
            };
            timer.Interval = TimeSpan.FromMilliseconds(50); timer.Tick += delegate { Tick(); }; timer.Start();
            Log(check ? "Checking audio decoding; playback disabled." : "Waiting for game; music requires mute acknowledgement.");
            if (gameProcess != null) Log("Watching game process " + gameProcess.Id + "; player exits with game.");
        }
        static Process FindGame(string path)
        {
            foreach (var process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(path)))
            {
                try
                {
                    if (!process.HasExited && String.Equals(Path.GetFullPath(process.MainModule.FileName), path, StringComparison.OrdinalIgnoreCase))
                        return process;
                }
                catch (System.ComponentModel.Win32Exception) { }
                catch (InvalidOperationException) { }
                process.Dispose();
            }
            return null;
        }
        void Log(string message)
        {
            var line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " " + message;
            Console.WriteLine(line);
            try { File.AppendAllText(logPath, line + Environment.NewLine, Encoding.UTF8); } catch (IOException) { }
        }
        static long UnixNow()
        { return (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds; }
        static string ReadShared(string path)
        {
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                if (stream.Length > 2048) return "";
                using (var reader = new StreamReader(stream)) return reader.ReadToEnd();
            }
        }
        void WriteRequest(string mode)
        {
            if (handoff.Session == "") return;
            Directory.CreateDirectory(Path.GetDirectoryName(requestPath));
            var text = String.Format(CultureInfo.InvariantCulture, "JWA2|{0}|{1}|{2}|{3}|{4}|END\n",
                handoff.Session, ++requestSequence, UnixNow(), handoff.Request, mode);
            // The game ignores incomplete lines. Sharing allows safe polling during the short write.
            using (var file = new FileStream(requestPath, FileMode.Create, FileAccess.Write, FileShare.ReadWrite))
            { var bytes = Encoding.ASCII.GetBytes(text); file.Write(bytes, 0, bytes.Length); }
            lastRequest = DateTime.UtcNow;
        }
        void StopMusic()
        { music.Stop(); armedMusic.Stop(); currentMusic = null; }
        void PlayMusic(Channel selected)
        {
            if (currentMusic != selected)
            {
                StopMusic(); currentMusic = selected;
                // Leave a short gap for queued stop commands before starting the other track.
                musicStartAfter = DateTime.UtcNow.AddMilliseconds(100);
            }
            if (DateTime.UtcNow >= musicStartAfter) selected.Play(false);
        }
        void Tick()
        {
            if (closing) return;
            try
            {
                if (checkOnly)
                {
                    if (music.Failed || armedMusic.Failed || drink.Failed || win.Failed) { ExitCode = 1; Finish(); }
                    else if (music.Ready && armedMusic.Ready && drink.Ready && win.Ready) { Log("PASS: all four assets decoded without playback."); Finish(); }
                    else if ((DateTime.UtcNow - started).TotalSeconds > 15) { ExitCode = 1; Log("ERROR decode timeout"); Finish(); }
                    return;
                }
                if (File.Exists(stopPath)) { File.Delete(stopPath); Finish(); return; }
                if (options.WatchGame && (gameProcess == null || gameProcess.HasExited))
                { Log("Game exited or unavailable; shutting down audio."); Finish(); return; }
                Snapshot next = null;
                try { next = Snapshot.Parse(ReadShared(options.Bridge)); } catch (IOException) { }
                if (next != null && Math.Abs(UnixNow() - next.Time) <= 3)
                {
                    var previousSession = handoff.Session;
                    if (handoff.Accept(next))
                    {
                        if (previousSession != handoff.Session) { StopMusic(); drink.Stop(); win.Stop(); }
                        lastUpdate = DateTime.UtcNow;
                        if (handoff.NewDrink) drink.Play(true);
                        if (handoff.NewWin) win.Play(true);
                        if (lastState != next.State) { lastState = next.State; Log("game=" + lastState); }
                    }
                }
                var fresh = (DateTime.UtcNow - lastUpdate).TotalSeconds <= 1.2;
                var selected = handoff.Current == null ? null :
                    handoff.Current.Track == "drunk" ? music : handoff.Current.Track == "armed" ? armedMusic : null;
                var ready = selected != null && selected.Ready;
                var mode = handoff.Mode(ready, fresh);
                if (handoff.CanPlay(ready, fresh))
                {
                    PlayMusic(selected);
                }
                else StopMusic();
                if (mode == "idle")
                {
                    if (lastMode != "idle") handoff.Revoke();
                    if (!fresh || handoff.Current == null || handoff.Current.State == "unknown") { drink.Stop(); win.Stop(); }
                }
                lastMode = mode;
                // Stop has completed before idle is acknowledged to the game.
                if ((DateTime.UtcNow - lastRequest).TotalMilliseconds >= 150) WriteRequest(mode);
            }
            catch (Exception ex)
            {
                StopMusic(); drink.Stop(); win.Stop();
                handoff.Revoke(); lastMode = "idle";
                if (lastError != ex.Message) { lastError = ex.Message; Log("ERROR " + lastError); }
                try { WriteRequest("idle"); } catch (IOException) { } catch (UnauthorizedAccessException) { }
            }
        }
        public void Finish()
        {
            if (closing) return;
            closing = true; timer.Stop(); music.Close(); armedMusic.Close(); drink.Close(); win.Close();
            if (!checkOnly) try { WriteRequest("idle"); } catch (IOException) { } catch (UnauthorizedAccessException) { }
            if (gameProcess != null) gameProcess.Dispose();
            Log("Stopped."); Dispatcher.CurrentDispatcher.BeginInvokeShutdown(DispatcherPriority.Background);
        }
    }

    public static class Program
    {
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                var check = Array.IndexOf(args, "--check") >= 0;
                var configIndex = Array.IndexOf(args, "--config");
                var installedConfig = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "audio.json"));
                var config = configIndex >= 0 ? args[configIndex + 1] : File.Exists(installedConfig) ? installedConfig : Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "audio.json");
                var options = Options.Load(config);
                if (Array.IndexOf(args, "--stop") >= 0)
                { Directory.CreateDirectory(options.Runtime); File.WriteAllText(Path.Combine(options.Runtime, "stop"), "stop"); return 0; }
                string mutexName;
                using (var hash = SHA256.Create()) mutexName = "Local\\JamieWinAudio-" + BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(options.Bridge.ToLowerInvariant()))).Replace("-", "");
                bool created;
                using (var mutex = new Mutex(true, mutexName + (check ? "-check" : ""), out created))
                {
                    if (!created) { Console.WriteLine("JamieWin audio is already running."); return 0; }
                    try
                    {
                        var host = new Host(options, check);
                        hostDispatcher = Dispatcher.CurrentDispatcher;
                        Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
                        { e.Cancel = true; hostDispatcher.BeginInvoke(new Action(host.Finish)); };
                        Dispatcher.Run(); return host.ExitCode;
                    }
                    finally { mutex.ReleaseMutex(); }
                }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
        static Dispatcher hostDispatcher;
    }
}
