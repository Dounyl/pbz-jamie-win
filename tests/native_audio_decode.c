/* Offline decoder harness. Never opens an audio output device. */
#define WIN32_LEAN_AND_MEAN
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "../probes/JamieWinNativeAudioTest/Native/media_decode.h"

int wmain(int argc, wchar_t **argv) {
    if(argc!=4) return 2;
    JWAsset asset={0};
    ULONGLONG began=GetTickCount64();
    HRESULT hr=jw_decode_audio(argv[1],&asset,(size_t)wcstoull(argv[3],NULL,10));
    if(FAILED(hr)) {
        fprintf(stderr,"decode failed: 0x%08lx\n",(unsigned long)hr);
        return asset.data || asset.frames ? 3 : 1;
    }
    FILE *output=_wfopen(argv[2],L"wb");
    if(!output) { HeapFree(GetProcessHeap(),0,(void*)asset.data); return 2; }
    size_t written=fwrite(asset.data,4,asset.frames,output);
    int closed=fclose(output);
    printf("{\"frames\":%llu,\"elapsed_ms\":%llu}\n",(unsigned long long)asset.frames,
        (unsigned long long)(GetTickCount64()-began));
    HeapFree(GetProcessHeap(),0,(void*)asset.data);
    return written==asset.frames && !closed ? 0 : 2;
}
