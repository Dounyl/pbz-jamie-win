/* Windows' in-process decoders read the original M4A/MP3; no intermediate WAV files. */
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include "media_decode.h"
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <mferror.h>
#include <string.h>

#define CHECK(call) do { hr=(call); if(FAILED(hr)) goto done; } while(0)

static HRESULT validate_format(IMFMediaType *type) {
    GUID major,subtype; UINT32 channels,rate,bits,alignment;
    if(FAILED(IMFMediaType_GetGUID(type,&MF_MT_MAJOR_TYPE,&major)) ||
       FAILED(IMFMediaType_GetGUID(type,&MF_MT_SUBTYPE,&subtype)) ||
       FAILED(IMFMediaType_GetUINT32(type,&MF_MT_AUDIO_NUM_CHANNELS,&channels)) ||
       FAILED(IMFMediaType_GetUINT32(type,&MF_MT_AUDIO_SAMPLES_PER_SECOND,&rate)) ||
       FAILED(IMFMediaType_GetUINT32(type,&MF_MT_AUDIO_BITS_PER_SAMPLE,&bits)) ||
       FAILED(IMFMediaType_GetUINT32(type,&MF_MT_AUDIO_BLOCK_ALIGNMENT,&alignment)) ||
       !IsEqualGUID(&major,&MFMediaType_Audio) || !IsEqualGUID(&subtype,&MFAudioFormat_PCM) ||
       channels!=2 || rate!=48000 || bits!=16 || alignment!=4) return MF_E_INVALIDMEDIATYPE;
    return S_OK;
}

HRESULT jw_decode_audio(const wchar_t *path, JWAsset *asset, size_t max_bytes) {
    if(!path || !asset || max_bytes<4) return E_INVALIDARG;
    asset->data=NULL; asset->frames=0;
    HRESULT hr=CoInitializeEx(NULL,COINIT_MULTITHREADED);
    if(FAILED(hr)) return hr;
    BOOL started=FALSE;
    IMFSourceReader *reader=NULL;
    IMFMediaType *type=NULL,*actual=NULL;
    IMFSample *sample=NULL;
    IMFMediaBuffer *buffer=NULL;
    BYTE *locked=NULL,*pcm=NULL;
    size_t size=0,capacity=0;
    ULONGLONG began=GetTickCount64();
    CHECK(MFStartup(MF_VERSION,MFSTARTUP_LITE)); started=TRUE;
    CHECK(MFCreateSourceReaderFromURL(path,NULL,&reader));
    CHECK(IMFSourceReader_SetStreamSelection(reader,MF_SOURCE_READER_ALL_STREAMS,FALSE));
    CHECK(IMFSourceReader_SetStreamSelection(reader,MF_SOURCE_READER_FIRST_AUDIO_STREAM,TRUE));
    CHECK(MFCreateMediaType(&type));
    CHECK(IMFMediaType_SetGUID(type,&MF_MT_MAJOR_TYPE,&MFMediaType_Audio));
    CHECK(IMFMediaType_SetGUID(type,&MF_MT_SUBTYPE,&MFAudioFormat_PCM));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_AUDIO_NUM_CHANNELS,2));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_AUDIO_SAMPLES_PER_SECOND,48000));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_AUDIO_BITS_PER_SAMPLE,16));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_AUDIO_BLOCK_ALIGNMENT,4));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_AUDIO_AVG_BYTES_PER_SECOND,192000));
    CHECK(IMFMediaType_SetUINT32(type,&MF_MT_ALL_SAMPLES_INDEPENDENT,TRUE));
    CHECK(IMFSourceReader_SetCurrentMediaType(reader,MF_SOURCE_READER_FIRST_AUDIO_STREAM,NULL,type));
    CHECK(IMFSourceReader_GetCurrentMediaType(reader,MF_SOURCE_READER_FIRST_AUDIO_STREAM,&actual));
    CHECK(validate_format(actual));
    for(;;) {
        DWORD flags=0,bytes=0;
        if(GetTickCount64()-began>8000) { hr=HRESULT_FROM_WIN32(WAIT_TIMEOUT); goto done; }
        CHECK(IMFSourceReader_ReadSample(reader,MF_SOURCE_READER_FIRST_AUDIO_STREAM,0,NULL,&flags,NULL,&sample));
        if(flags&(MF_SOURCE_READERF_ERROR|MF_SOURCE_READERF_CURRENTMEDIATYPECHANGED)) {
            hr=MF_E_INVALIDMEDIATYPE; goto done;
        }
        if(sample) {
            CHECK(IMFSample_ConvertToContiguousBuffer(sample,&buffer));
            CHECK(IMFMediaBuffer_Lock(buffer,&locked,NULL,&bytes));
            if(bytes%4 || bytes>max_bytes-size) { hr=HRESULT_FROM_WIN32(ERROR_INVALID_DATA); goto done; }
            if(size+bytes>capacity) {
                size_t next=capacity ? capacity : 1024u*1024u;
                if(next>max_bytes) next=max_bytes;
                while(next<size+bytes) next=next>max_bytes/2 ? max_bytes : next*2;
                BYTE *grown=pcm ? HeapReAlloc(GetProcessHeap(),0,pcm,next) : HeapAlloc(GetProcessHeap(),0,next);
                if(!grown) { hr=E_OUTOFMEMORY; goto done; }
                pcm=grown; capacity=next;
            }
            if(bytes) memcpy(pcm+size,locked,bytes);
            size+=bytes;
            hr=IMFMediaBuffer_Unlock(buffer); locked=NULL;
            if(FAILED(hr)) goto done;
            IMFMediaBuffer_Release(buffer); buffer=NULL;
            IMFSample_Release(sample); sample=NULL;
        }
        if(flags&MF_SOURCE_READERF_ENDOFSTREAM) break;
    }
    if(!size) { hr=HRESULT_FROM_WIN32(ERROR_INVALID_DATA); goto done; }
    /* Release growth slack: the decoded songs stay resident until playback stops. */
    BYTE *trimmed=HeapReAlloc(GetProcessHeap(),0,pcm,size);
    if(trimmed) pcm=trimmed;
    asset->data=(const int16_t*)pcm; asset->frames=size/4; pcm=NULL; hr=S_OK;
done:
    if(locked) IMFMediaBuffer_Unlock(buffer);
    if(buffer) IMFMediaBuffer_Release(buffer);
    if(sample) IMFSample_Release(sample);
    if(actual) IMFMediaType_Release(actual);
    if(type) IMFMediaType_Release(type);
    if(reader) IMFSourceReader_Release(reader);
    if(pcm) HeapFree(GetProcessHeap(),0,pcm);
    if(started) MFShutdown();
    CoUninitialize();
    return hr;
}
