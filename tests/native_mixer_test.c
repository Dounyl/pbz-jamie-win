#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "../probes/JamieWinNativeAudioTest/Native/mixer.h"
static int16_t song[14], voice[4000], loud[4000], pcm[6000];
static JWMixer make_mixer(void) {
    JWMixer m={0};
    for(int i=0;i<7;i++){song[i*2]=10000;song[i*2+1]=-10000;}
    for(int i=0;i<2000;i++){voice[i*2]=1000;voice[i*2+1]=-1000;loud[i*2]=32767;loud[i*2+1]=-32768;}
    m.assets[0]=(JWAsset){song,7};m.assets[1]=(JWAsset){song,7};
    m.assets[2]=(JWAsset){voice,2000};m.assets[3]=(JWAsset){voice,2000};
    m.music_volume=.45f;m.cue_volume[0]=.9f;m.cue_volume[1]=1;
    jw_music(&m,1);return m;
}
static void expect_sample(int index,int left,int right) {
    assert(abs((int)pcm[index*2]-left)<=1);assert(abs((int)pcm[index*2+1]-right)<=1);
}
static void gain_and_silence(void) {
    JWMixer m=make_mixer();jw_render(&m,pcm,1000);expect_sample(999,6480,-6480);
    m.music_volume=.225f;jw_render(&m,pcm,1000);expect_sample(999,3240,-3240);
    m.music_volume=0;jw_render(&m,pcm,1000);expect_sample(999,0,0);
    assert(m.music_rendered==3000);puts("PASS software gain and zero volume preserve playback");
}
static void voice_overlay_preserves_music(void) {
    for(int track=1;track<=2;track++) for(int cues=1;cues<=3;cues++) {
        JWMixer m=make_mixer();jw_music(&m,track);jw_render(&m,pcm,1000);
        int music=track==1 ? 6480 : 4500;
        int voice_mix=((cues&1) ? 900 : 0)+((cues&2) ? 1000 : 0);
        float gain=m.gain;size_t cursor=m.music_frame;
        if(cues&1) jw_cue(&m,0);
        if(cues&2) jw_cue(&m,1);
        assert(m.music_frame==cursor&&m.music_rendered==1000);
        JWBlock b=jw_render(&m,pcm,1000);
        expect_sample(0,music+voice_mix,-music-voice_mix);
        expect_sample(999,music+voice_mix,-music-voice_mix);
        assert(b.music&&b.drink==!!(cues&1)&&b.win==!!(cues&2));
        assert(fabsf(m.gain-gain)<.00001f&&m.music_frame==2000%7);
        jw_render(&m,pcm,2000);expect_sample(1999,music,-music);
        assert(!m.cue_active[0]&&!m.cue_active[1]&&m.music_rendered==4000&&m.music_frame==4000%7);
        assert(fabsf(m.gain-gain)<.00001f);
    }
    puts("PASS either/both cues overlay both songs without gain changes, pauses or restarts");
}
static void simultaneous_voices(void) {
    JWMixer m=make_mixer();jw_cue(&m,0);jw_cue(&m,1);
    JWBlock b=jw_render(&m,pcm,1000);expect_sample(999,8380,-8380);
    assert(b.music&&b.drink&&b.win);
    jw_render(&m,pcm,2000);assert(!m.cue_active[0]&&!m.cue_active[1]);
    puts("PASS independent voice channels finish exactly once");
}
static void loops_and_no_restart(void) {
    JWMixer m=make_mixer();jw_render(&m,pcm,1000);
    size_t cursor=m.music_frame;uint64_t played=m.music_rendered;
    jw_music(&m,1);assert(m.music_frame==cursor&&m.music_rendered==played);
    jw_render(&m,pcm,1000);assert(m.music_frame==2000%7&&m.music_rendered==2000);
    jw_music(&m,2);assert(m.music_frame==0&&m.music_rendered==0);
    puts("PASS seamless short loops, same-track continuation and track switch");
}
static void saturating_mix(void) {
    JWMixer m=make_mixer();m.assets[2]=(JWAsset){loud,2000};m.assets[3]=(JWAsset){loud,2000};
    m.cue_volume[0]=m.cue_volume[1]=1;jw_cue(&m,0);jw_cue(&m,1);
    JWBlock b=jw_render(&m,pcm,1000);expect_sample(999,32767,-32768);assert(b.peak==32768);
    puts("PASS overload saturates without integer wrap");
}
static void stop_all_channels(void) {
    JWMixer m=make_mixer();jw_cue(&m,0);jw_cue(&m,1);jw_render(&m,pcm,100);
    jw_clear(&m);assert(!jw_active(&m));JWBlock b=jw_render(&m,pcm,1000);
    assert(!b.music&&!b.drink&&!b.win&&!b.peak);expect_sample(999,0,0);
    puts("PASS stop clears music and both voice channels");
}
static void menu_round_trip_keeps_music_position(void) {
    JWMixer m=make_mixer();jw_render(&m,pcm,1000);
    jw_menu(&m,1);
    for(int i=0;i<20;i++)jw_render(&m,pcm,1000);
    assert(m.menu.mix==1 && m.music_rendered==21000 && m.music_frame==21000%7);
    expect_sample(999,5832,-5832); /* Wet gain .9, boosted armed music gain .648. */
    jw_menu(&m,1);assert(m.menu.mix==1); /* Polling must not restart a ramp. */
    jw_menu(&m,0);
    for(int i=0;i<20;i++)jw_render(&m,pcm,1000);
    assert(m.menu.mix==0 && m.music_rendered==41000 && m.music_frame==41000%7);
    expect_sample(999,6480,-6480);
    puts("PASS menu fades in/out without rewinding, pausing or changing loop position");
}
static void menu_holds_voices_but_not_music(void) {
    JWMixer m=make_mixer();jw_cue(&m,0);jw_cue(&m,1);jw_render(&m,pcm,100);
    size_t cursor=m.cue_frame[0];jw_menu(&m,1);
    JWBlock b=jw_render(&m,pcm,1000);
    assert(b.music&&!b.drink&&!b.win&&m.cue_frame[0]==cursor&&m.cue_frame[1]==cursor);
    assert(m.music_rendered==1100&&m.cue_active[0]&&m.cue_active[1]);
    jw_menu(&m,0);jw_render(&m,pcm,2000);
    assert(!m.cue_active[0]&&!m.cue_active[1]&&m.music_rendered==3100);
    jw_menu(&m,1);jw_music(&m,2);assert(m.menu.target==1); /* Preserve menu on song switch. */
    jw_clear(&m);assert(!m.menu.target&&m.menu.mix==0&&!jw_active(&m));
    puts("PASS menu preserves voice positions, resumes once, and stop resets the effect");
}
static void rapid_menu_reversals_are_continuous(void) {
    JWMenuFilter filter;jw_filter_clear(&filter);jw_filter_set_menu(&filter,1);
    double previous=0;
    for(int i=0;i<48000;i++) {
        if(i%4800==4799) {
            double before=filter.mix;jw_filter_set_menu(&filter,!filter.target);
            assert(filter.mix==before);
        }
        double weight=jw_filter_weight(&filter);
        assert(weight>=0&&weight<=1&&fabs(weight-previous)<.0001);
        previous=weight;
    }
    jw_filter_set_menu(&filter,0);
    for(unsigned i=0;i<JW_MENU_RAMP_FRAMES;i++)jw_filter_weight(&filter);
    assert(filter.mix==0);
    puts("PASS rapid menu reversal has no blend discontinuity and ends fully clear");
}
static void drunk_music_keeps_original_gain(void) {
    JWMixer m=make_mixer();jw_music(&m,2);
    jw_render(&m,pcm,1000);expect_sample(999,4500,-4500);
    jw_cue(&m,0);jw_render(&m,pcm,1000);expect_sample(999,5400,-5400);
    assert(fabsf(m.gain-.45f)<.00001f);
    puts("PASS only Mr.Top.Player is boosted; drunk music and voices retain their levels");
}
int main(void) {
    gain_and_silence();voice_overlay_preserves_music();simultaneous_voices();
    loops_and_no_restart();saturating_mix();stop_all_channels();
    menu_round_trip_keeps_music_position();menu_holds_voices_but_not_music();
    rapid_menu_reversals_are_continuous();drunk_music_keeps_original_gain();return 0;
}
