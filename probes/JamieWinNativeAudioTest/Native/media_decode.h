#ifndef JAMIE_MEDIA_DECODE_H
#define JAMIE_MEDIA_DECODE_H
#include <windows.h>
#include "mixer.h"

/* Decode a local audio file to 48 kHz stereo PCM16. The caller owns the process-heap buffer. */
HRESULT jw_decode_audio(const wchar_t *path, JWAsset *asset, size_t max_bytes);
#endif
