#ifndef JAMIE_MIXER_H
#define JAMIE_MIXER_H
#include <stdint.h>
#include <stddef.h>
#include "menu_filter.h"
typedef struct { const int16_t *data; size_t frames; } JWAsset;
typedef struct {
    JWAsset assets[4];
    int music;
    size_t music_frame, cue_frame[2];
    int cue_active[2];
    float music_volume, cue_volume[2], gain;
    uint64_t music_rendered;
    JWMenuFilter menu;
} JWMixer;
typedef struct { int music, drink, win, peak; } JWBlock;
void jw_music(JWMixer *m, int track);
void jw_cue(JWMixer *m, int cue);
void jw_menu(JWMixer *m, int open);
void jw_clear(JWMixer *m);
int jw_active(const JWMixer *m);
JWBlock jw_render(JWMixer *m, int16_t *output, size_t frames);
#endif
