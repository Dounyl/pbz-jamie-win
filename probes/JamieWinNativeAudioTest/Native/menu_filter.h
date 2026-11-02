#ifndef JAMIE_MENU_FILTER_H
#define JAMIE_MENU_FILTER_H
#include <stdint.h>

/* Fixed 48 kHz stereo: the user-approved 1200 Hz, two-biquad preview. */
#define JW_MENU_RAMP_FRAMES 19200u
typedef struct {
    double b0, b1, a1, a2;
    double state[2][2][2]; /* channel, stage, transposed direct-form II state */
    double mix, from;
    uint32_t ramp_frame;
    int target;
} JWMenuFilter;

void jw_filter_clear(JWMenuFilter *f);
void jw_filter_reset_history(JWMenuFilter *f);
void jw_filter_set_menu(JWMenuFilter *f, int open);
double jw_filter_weight(JWMenuFilter *f);
double jw_filter_sample(JWMenuFilter *f, int channel, double dry, double weight);
#endif
