#include "mixer.h"
void jw_music(JWMixer *m, int track) {
    if (m->music == track) return;
    m->music = track; m->music_frame = 0; m->music_rendered = 0; m->gain = 0;
    jw_filter_reset_history(&m->menu);
}
void jw_menu(JWMixer *m, int open) { jw_filter_set_menu(&m->menu, open); }
void jw_cue(JWMixer *m, int cue) {
    if (cue < 0 || cue > 1 || !m->assets[cue+2].frames) return;
    m->cue_frame[cue] = 0; m->cue_active[cue] = 1;
}
void jw_clear(JWMixer *m) {
    jw_music(m,0); m->cue_active[0] = m->cue_active[1] = 0;
    m->gain = 0;
    jw_filter_clear(&m->menu);
}
int jw_active(const JWMixer *m) { return m->music || (!m->menu.target && (m->cue_active[0] || m->cue_active[1])); }
JWBlock jw_render(JWMixer *m, int16_t *output, size_t frames) {
    JWBlock block = {0,0,0,0};
    for (size_t f=0; f<frames; ++f) {
        // Mr.Top.Player is 20% louder than 1.0.1. Cues overlay music without ducking.
        float track_gain = m->music == 1 ? 1.44f : 1.0f;
        float target = m->music_volume * track_gain;
        float step = 1.0f / 960.0f; // At most 20 ms for a full-scale gain change.
        float delta = target - m->gain;
        m->gain += delta > step ? step : delta < -step ? -step : delta;
        double menu_weight = jw_filter_weight(&m->menu);
        for (int channel=0; channel<2; ++channel) {
            float sample = 0;
            if (m->music && m->assets[m->music-1].frames) {
                double dry = m->assets[m->music-1].data[m->music_frame*2+channel];
                sample += (float)(jw_filter_sample(&m->menu, channel, dry, menu_weight) * m->gain);
                block.music = 1;
            }
            for (int cue=0; cue<2; ++cue) if (m->cue_active[cue] && !m->menu.target) {
                sample += m->assets[cue+2].data[m->cue_frame[cue]*2+channel] * m->cue_volume[cue];
                if (cue==0) block.drink=1; else block.win=1;
            }
            if (sample > 32767) sample=32767;
            if (sample < -32768) sample=-32768;
            int value=(int)sample;
            output[f*2+channel]=(int16_t)value;
            int magnitude=value<0 ? -value : value;
            if (magnitude>block.peak) block.peak=magnitude;
        }
        if (m->music && m->assets[m->music-1].frames) {
            m->music_frame=(m->music_frame+1)%m->assets[m->music-1].frames;
            m->music_rendered++;
        }
        for (int cue=0; cue<2; ++cue) if (m->cue_active[cue] && !m->menu.target) {
            if (++m->cue_frame[cue] >= m->assets[cue+2].frames) m->cue_active[cue]=0;
        }
    }
    return block;
}
