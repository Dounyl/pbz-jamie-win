// In-process PCM mixer. No Unreal/Lua private ABI, child process or device-volume API.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <wchar.h>
#include <math.h>
#include "mixer.h"
#define VERSION "1.0.0-stable"
#define PATH_CAP 32768
#define MAX_PCM (64u*1024u*1024u)
#define BUFFER_COUNT 4
#define BUFFER_FRAMES 960
#define WATCHDOG_MS 3000
typedef struct {
    char session[64];
    unsigned long long seq, epoch, drink, win;
    int active, track, menu, allow;
    float music_gain, drink_gain, win_gain;
} Request;
typedef struct { WAVEHDR header; int16_t pcm[BUFFER_FRAMES*2]; JWBlock tags; } Buffer;
static const wchar_t *asset_names[]={L"mr_top_player",L"mandarin_duck_play",L"jamie_drink4_ja",L"jamie_wins"};
static HMODULE module_handle;
static SRWLOCK request_lock=SRWLOCK_INIT;
static Request request, applied;
static HANDLE wake_event;
static volatile LONG64 heartbeat;
static volatile LONG emergency;
static BOOL initialized, loaded;
static wchar_t root[PATH_CAP],status_path[PATH_CAP],temp_path[PATH_CAP],log_path[PATH_CAP],command_path[PATH_CAP];
static HWAVEOUT output;
static Buffer buffers[BUFFER_COUNT];
static unsigned next_buffer;
static JWMixer mixer;
static DWORD result_code;
static const char *phase="idle", *operation="init";
static ULONGLONG samples,last_raw,last_progress,last_publish,last_log;
static unsigned long long seen_drink,seen_win;
static UINT position_type;
static BOOL clock_logged;

static Request snapshot(void) {
    Request value; AcquireSRWLockShared(&request_lock); value=request; ReleaseSRWLockShared(&request_lock); return value;
}
static const char *track_name(int track) { return track==1 ? "armed" : track==2 ? "drunk" : "none"; }
static void log_line(const char *fmt,...) {
    char line[1400],text[1100]; SYSTEMTIME t; GetLocalTime(&t);
    va_list ap; va_start(ap,fmt); vsnprintf(text,sizeof(text),fmt,ap); va_end(ap);
    int n=snprintf(line,sizeof(line),"%04u-%02u-%02u %02u:%02u:%02u %s\r\n",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,text);
    if(n<=0 || n>=(int)sizeof(line)) return;
    HANDLE f=CreateFileW(log_path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f!=INVALID_HANDLE_VALUE) { DWORD count; WriteFile(f,line,(DWORD)n,&count,NULL); CloseHandle(f); }
}
static int queued_tag(int kind) {
    for(unsigned i=0;i<BUFFER_COUNT;i++) if(buffers[i].header.dwFlags&WHDR_INQUEUE) {
        JWBlock b=buffers[i].tags;
        if(kind==0 || (kind==1 && b.music) || (kind==2 && b.drink) || (kind==3 && b.win)) return 1;
    }
    return 0;
}
static void publish(void) {
    char data[1024];
    int n=snprintf(data,sizeof(data),
        "version=%s\nsession=%s\npid=%lu\nseq=%llu\nepoch=%llu\ntick=%llu\ntrack=%s\nphase=%s\n"
        "samples=%llu\nmusic_frames=%llu\nrate=48000\nready=%d\nmusic_stopped=%d\n"
        "drink_playing=%d\nwin_playing=%d\nmusic_gain=%.6f\ndrink_gain=%.6f\nwin_gain=%.6f\n"
        "menu=%d\nmenu_mix=%.6f\n"
        "emergency=%ld\ncode=%lu\noperation=%s\n",
        VERSION,applied.session,GetCurrentProcessId(),applied.seq,applied.epoch,(unsigned long long)GetTickCount64(),
        track_name(applied.track),phase,(unsigned long long)samples,(unsigned long long)mixer.music_rendered,
        loaded&&output!=NULL, !mixer.music&&!queued_tag(1),
        mixer.cue_active[0]||queued_tag(2),mixer.cue_active[1]||queued_tag(3),
        mixer.gain,mixer.cue_volume[0],mixer.cue_volume[1],mixer.menu.target,mixer.menu.mix,
        InterlockedCompareExchange(&emergency,0,0),result_code,operation);
    if(n<=0 || n>=(int)sizeof(data)) return;
    HANDLE f=CreateFileW(temp_path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f==INVALID_HANDLE_VALUE) return;
    DWORD written=0; BOOL ok=WriteFile(f,data,(DWORD)n,&written,NULL); CloseHandle(f);
    if(ok && written==(DWORD)n) MoveFileExW(temp_path,status_path,MOVEFILE_REPLACE_EXISTING);
    last_publish=GetTickCount64();
}
static void fail(const char *where,DWORD code) {
    phase="failed"; operation=where; result_code=code;
    log_line("FAIL operation=%s; code=%lu; seq=%llu",where,code,applied.seq);
}
static void free_assets(void) {
    for(int i=0;i<4;i++) {
        if(mixer.assets[i].data) HeapFree(GetProcessHeap(),0,(void*)mixer.assets[i].data);
        mixer.assets[i].data=NULL; mixer.assets[i].frames=0;
    }
    loaded=FALSE;
}
static BOOL stop_output(void) {
    jw_clear(&mixer);
    if(output) {
        MMRESULT r=waveOutReset(output);
        if(r) { fail("waveOutReset",r); return FALSE; }
        for(unsigned i=0;i<BUFFER_COUNT;i++) if(buffers[i].header.dwFlags&WHDR_PREPARED) {
            r=waveOutUnprepareHeader(output,&buffers[i].header,sizeof(WAVEHDR));
            if(r) { fail("waveOutUnprepareHeader",r); return FALSE; }
        }
        r=waveOutClose(output); if(r) { fail("waveOutClose",r); return FALSE; }
        output=NULL;
    }
    ZeroMemory(buffers,sizeof(buffers)); next_buffer=0;
    return TRUE;
}
static BOOL read_exact(HANDLE f,void *data,DWORD size) {
    DWORD count=0; return ReadFile(f,data,size,&count,NULL)&&count==size;
}
static BOOL load_asset(int index) {
    wchar_t path[PATH_CAP];
    if(swprintf(path,PATH_CAP,L"%ls\\Audio\\%ls.wav",root,asset_names[index])<0) { fail("asset_path",ERROR_FILENAME_EXCED_RANGE); return FALSE; }
    HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f==INVALID_HANDLE_VALUE) { fail("open_pcm",GetLastError()); return FALSE; }
    LARGE_INTEGER length; BYTE riff[12]; WAVEFORMATEX format={0}; BYTE *pcm=NULL;
    BOOL ok=FALSE,has_format=FALSE; DWORD data_offset=0,data_size=0;
    if(!GetFileSizeEx(f,&length)||length.QuadPart<44||length.QuadPart>MAX_PCM+65536) goto done;
    if(!read_exact(f,riff,12)||memcmp(riff,"RIFF",4)||memcmp(riff+8,"WAVE",4)) goto done;
    uint32_t declared; memcpy(&declared,riff+4,4);
    if((uint64_t)declared+8!=(uint64_t)length.QuadPart) goto done;
    uint64_t pos=12;
    while(pos+8<=(uint64_t)length.QuadPart) {
        BYTE chunk[8]; DWORD size;
        if(!read_exact(f,chunk,8)) goto done;
        memcpy(&size,chunk+4,4); pos+=8;
        if(pos+size+(size&1)>(uint64_t)length.QuadPart) goto done;
        if(!memcmp(chunk,"fmt ",4)) {
            if(has_format||size<16||!read_exact(f,&format,16)) goto done;
            has_format=TRUE;
        } else if(!memcmp(chunk,"data",4)) {
            if(data_offset) goto done;
            data_offset=(DWORD)pos; data_size=size;
        }
        pos+=size+(size&1); LARGE_INTEGER offset; offset.QuadPart=(LONGLONG)pos;
        if(!SetFilePointerEx(f,offset,NULL,FILE_BEGIN)) goto done;
    }
    if(!has_format||!data_size||data_size>MAX_PCM||format.wFormatTag!=WAVE_FORMAT_PCM||format.nChannels!=2||
        format.wBitsPerSample!=16||format.nBlockAlign!=4||format.nSamplesPerSec!=48000||format.nAvgBytesPerSec!=192000||data_size%4) goto done;
    pcm=HeapAlloc(GetProcessHeap(),0,data_size);
    if(!pcm) { fail("allocate_pcm",ERROR_NOT_ENOUGH_MEMORY); goto done; }
    LARGE_INTEGER offset; offset.QuadPart=data_offset;
    if(!SetFilePointerEx(f,offset,NULL,FILE_BEGIN)||!read_exact(f,pcm,data_size)) goto done;
    mixer.assets[index].data=(int16_t*)pcm; mixer.assets[index].frames=data_size/4; ok=TRUE;
done:
    CloseHandle(f);
    if(!ok) { if(pcm) HeapFree(GetProcessHeap(),0,pcm); if(strcmp(phase,"failed")) fail("validate_pcm",ERROR_INVALID_DATA); }
    return ok;
}
static BOOL prepare(void) {
    if(output&&loaded) return TRUE;
    phase="loading"; operation="prepare"; publish();
    if(!loaded) {
        for(int i=0;i<4;i++) if(!load_asset(i)) { free_assets(); return FALSE; }
        loaded=TRUE;
    }
    WAVEFORMATEX format={WAVE_FORMAT_PCM,2,48000,192000,4,16,0}; HWAVEOUT opened=NULL;
    MMRESULT r=waveOutOpen(&opened,WAVE_MAPPER,&format,(DWORD_PTR)wake_event,0,CALLBACK_EVENT);
    if(r) { fail("waveOutOpen",r); return FALSE; }
    output=opened;
    for(unsigned i=0;i<BUFFER_COUNT;i++) {
        buffers[i].header.lpData=(LPSTR)buffers[i].pcm;
        buffers[i].header.dwBufferLength=sizeof(buffers[i].pcm);
        r=waveOutPrepareHeader(output,&buffers[i].header,sizeof(WAVEHDR));
        if(r) { fail("waveOutPrepareHeader",r); stop_output(); return FALSE; }
    }
    samples=last_raw=0; position_type=0; clock_logged=FALSE; last_progress=GetTickCount64();
    phase="ready"; result_code=0;
    log_line("READY pid=%lu; assets=4; rate=48000; software_gain=true; queue_ms=80",GetCurrentProcessId());
    return TRUE;
}
static BOOL observe_output(void) {
    MMTIME t={0}; t.wType=TIME_SAMPLES;
    MMRESULT r=waveOutGetPosition(output,&t,sizeof(t)); if(r) { fail("waveOutGetPosition",r); return FALSE; }
    DWORD raw;
    if(t.wType==TIME_SAMPLES) raw=t.u.sample;
    else if(t.wType==TIME_BYTES) raw=t.u.cb;
    else if(t.wType==TIME_MS) raw=t.u.ms;
    else { fail("position_type",t.wType); return FALSE; }
    if(position_type&&position_type!=t.wType) { fail("position_type_changed",t.wType); return FALSE; }
    position_type=t.wType; DWORD delta=raw-(DWORD)last_raw; last_raw=raw;
    ULONGLONG frames=delta;
    if(t.wType==TIME_BYTES) frames/=4; else if(t.wType==TIME_MS) frames*=48;
    samples+=frames;
    if(frames) {
        last_progress=GetTickCount64();
        if(!clock_logged) { clock_logged=TRUE; log_line("DEVICE_CLOCK_ADVANCED; listener confirms audio"); }
    } else if(queued_tag(0)&&GetTickCount64()-last_progress>10000) {
        fail("device_clock_stalled",WAIT_TIMEOUT); return FALSE;
    } else if(!queued_tag(0)) last_progress=GetTickCount64();
    return TRUE;
}
static BOOL fill_buffers(void) {
    for(unsigned n=0;n<BUFFER_COUNT && jw_active(&mixer);n++) {
        Buffer *b=&buffers[next_buffer]; if(b->header.dwFlags&WHDR_INQUEUE) break;
        b->tags=jw_render(&mixer,b->pcm,BUFFER_FRAMES);
        MMRESULT r=waveOutWrite(output,&b->header,sizeof(WAVEHDR));
        if(r) { fail("waveOutWrite",r); return FALSE; }
        next_buffer=(next_buffer+1)%BUFFER_COUNT;
    }
    return TRUE;
}
static DWORD WINAPI worker(void *unused) {
    (void)unused;
    log_line("BOOT " VERSION "; pid=%lu; backend=WinMM; mixer=music+drink+win",GetCurrentProcessId());
    for(;;) {
        Request wanted=snapshot(); BOOL changed=wanted.seq!=applied.seq;
        if(changed) {
            BOOL reset=wanted.epoch!=applied.epoch;
            BOOL retry=reset||wanted.track!=applied.track;
            if(reset && applied.seq) { seen_drink=wanted.drink; seen_win=wanted.win; }
            applied=wanted;
            if(reset && !stop_output()) goto publish_state;
            if(retry && !strcmp(phase,"failed")) { if(!stop_output()) goto publish_state; phase="idle"; }
            mixer.music_volume=wanted.music_gain; mixer.cue_volume[0]=wanted.drink_gain; mixer.cue_volume[1]=wanted.win_gain;
        }
        if(InterlockedCompareExchange(&emergency,0,0)||!wanted.active) {
            if(output||jw_active(&mixer)) { if(!stop_output()) goto publish_state; log_line("STOP_ACK seq=%llu",applied.seq); }
            free_assets(); phase="idle"; operation="stop"; result_code=0;
            seen_drink=wanted.drink; seen_win=wanted.win;
            goto publish_state;
        }
        if(!strcmp(phase,"failed")) { stop_output(); goto publish_state; }
        if(GetTickCount64()-(ULONGLONG)InterlockedCompareExchange64(&heartbeat,0,0)>WATCHDOG_MS) {
            fail("heartbeat_expired",WAIT_TIMEOUT); stop_output(); goto publish_state;
        }
        if((wanted.track||wanted.drink>seen_drink||wanted.win>seen_win)&&!prepare()) { stop_output(); goto publish_state; }
        // A changed command during disk loading must be handled before rendering.
        if(snapshot().seq!=wanted.seq || InterlockedCompareExchange(&emergency,0,0)) continue;
        if(mixer.menu.target!=wanted.menu) {
            log_line("MENU %s seq=%llu; samples=%llu; music_frames=%llu; cutoff=1200; transition_ms=400",
                wanted.menu?"ENTER":"EXIT",applied.seq,(unsigned long long)samples,(unsigned long long)mixer.music_rendered);
        }
        jw_menu(&mixer,wanted.menu);
        jw_music(&mixer,wanted.allow ? wanted.track : 0);
        if(!wanted.menu && (!wanted.track||wanted.allow)) {
            if(wanted.drink>seen_drink) { jw_cue(&mixer,0); seen_drink=wanted.drink; log_line("CUE drink id=%llu",seen_drink); }
            if(wanted.win>seen_win) { jw_cue(&mixer,1); seen_win=wanted.win; log_line("CUE win id=%llu",seen_win); }
        }
        if(output) {
            if(!fill_buffers()) { stop_output(); goto publish_state; }
            if(!observe_output()) { stop_output(); goto publish_state; }
        }
        phase=jw_active(&mixer)||queued_tag(0) ? "playing" : "ready";
        operation="mix";
publish_state:
        if(changed||GetTickCount64()-last_publish>=200) publish();
        if(output && GetTickCount64()-last_log>=5000) {
            last_log=GetTickCount64(); log_line("STATUS track=%s; phase=%s; samples=%llu; music_gain=%.3f; drink=%d; win=%d; menu=%d; menu_mix=%.3f",
                track_name(applied.track),phase,(unsigned long long)samples,mixer.gain,mixer.cue_active[0]||queued_tag(2),mixer.cue_active[1]||queued_tag(3),mixer.menu.target,mixer.menu.mix);
        }
        WaitForSingleObject(wake_event,20);
    }
}
__declspec(dllexport) int JamieNative_Init(void *state) {
    (void)state; AcquireSRWLockExclusive(&request_lock);
    if(!initialized) {
        DWORD length=GetModuleFileNameW(module_handle,root,PATH_CAP);
        if(!length||length>=PATH_CAP) { ReleaseSRWLockExclusive(&request_lock); return 0; }
        wchar_t *slash=wcsrchr(root,L'\\'); if(slash) *slash=0;
        slash=wcsrchr(root,L'\\'); if(slash) *slash=0;
        swprintf(status_path,PATH_CAP,L"%ls\\runtime\\native-status.txt",root);
        swprintf(temp_path,PATH_CAP,L"%ls\\runtime\\native-status.tmp",root);
        swprintf(log_path,PATH_CAP,L"%ls\\runtime\\native-output.log",root);
        swprintf(command_path,PATH_CAP,L"%ls\\runtime\\native-command.txt",root);
        HMODULE pinned;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)&JamieNative_Init,&pinned)) {
            fail("pin_module",GetLastError()); publish(); ReleaseSRWLockExclusive(&request_lock); return 0;
        }
        wake_event=CreateEventW(NULL,FALSE,FALSE,NULL); InterlockedExchange64(&heartbeat,(LONG64)GetTickCount64());
        HANDLE thread=wake_event?CreateThread(NULL,0,worker,NULL,0,NULL):NULL;
        if(!thread) { fail("create_worker",GetLastError()); publish(); if(wake_event)CloseHandle(wake_event); wake_event=NULL; }
        else { initialized=TRUE; CloseHandle(thread); }
    }
    ReleaseSRWLockExclusive(&request_lock); return 0;
}
__declspec(dllexport) int JamieNative_Apply(void *state) {
    (void)state; char text[512]={0}; DWORD size=0;
    HANDLE f=CreateFileW(command_path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f==INVALID_HANDLE_VALUE) return 0;
    BOOL ok=ReadFile(f,text,sizeof(text)-1,&size,NULL); CloseHandle(f);
    if(!ok||size>=sizeof(text)-1) return 0;
    Request value={0}; int consumed=0;
    int fields=sscanf(text,"JWN5|%63[a-zA-Z0-9-]|%llu|%llu|%d|%d|%d|%d|%f|%f|%f|%llu|%llu|END\n%n",
        value.session,&value.seq,&value.epoch,&value.active,&value.track,&value.menu,&value.allow,
        &value.music_gain,&value.drink_gain,&value.win_gain,&value.drink,&value.win,&consumed);
    if(fields!=12||consumed!=(int)size||!size||text[size-1]!='\n'||!value.seq||value.seq>9007199254740991ull||
        value.epoch>9007199254740991ull||value.drink>9007199254740991ull||value.win>9007199254740991ull||
        value.active<0||value.active>1||value.track<0||value.track>2||value.menu<0||value.menu>1||value.allow<0||value.allow>1||
        !isfinite(value.music_gain)||!isfinite(value.drink_gain)||!isfinite(value.win_gain)||
        value.music_gain<0||value.music_gain>1||value.drink_gain<0||value.drink_gain>1||value.win_gain<0||value.win_gain>1) return 0;
    AcquireSRWLockExclusive(&request_lock);
    if(value.seq>request.seq && (!request.session[0]||!strcmp(value.session,request.session)) &&
        value.epoch>=request.epoch && value.drink>=request.drink && value.win>=request.win) {
        request=value; InterlockedExchange(&emergency,0); InterlockedExchange64(&heartbeat,(LONG64)GetTickCount64());
        if(wake_event)SetEvent(wake_event);
    }
    ReleaseSRWLockExclusive(&request_lock); return 0;
}
__declspec(dllexport) int JamieNative_Stop(void *state) {
    (void)state; InterlockedExchange(&emergency,1); if(wake_event)SetEvent(wake_event); return 0;
}
__declspec(dllexport) int JamieNative_Heartbeat(void *state) {
    (void)state; InterlockedExchange64(&heartbeat,(LONG64)GetTickCount64()); return 0;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved) {
    (void)reserved;
    if(reason==DLL_PROCESS_ATTACH) { module_handle=instance; DisableThreadLibraryCalls(instance); }
    return TRUE;
}
