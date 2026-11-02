#include "menu_filter.h"
#include <math.h>
#include <string.h>

static const double pi = 3.14159265358979323846;

void jw_filter_reset_history(JWMenuFilter *f) {
    memset(f->state, 0, sizeof(f->state));
    const double angle = 2.0 * pi * 1200.0 / 48000.0;
    const double cosine = cos(angle);
    const double alpha = sin(angle) / (2.0 * 0.70710678);
    f->b0 = (1.0 - cosine) / (2.0 * (1.0 + alpha));
    f->b1 = 2.0 * f->b0;
    f->a1 = -2.0 * cosine / (1.0 + alpha);
    f->a2 = (1.0 - alpha) / (1.0 + alpha);
}

void jw_filter_clear(JWMenuFilter *f) {
    memset(f, 0, sizeof(*f));
    f->ramp_frame = JW_MENU_RAMP_FRAMES;
    jw_filter_reset_history(f);
}

void jw_filter_set_menu(JWMenuFilter *f, int open) {
    open = open != 0;
    if (f->target == open) return;
    /* Reversing mid-transition starts at the current blend, never at an endpoint. */
    f->from = f->mix;
    f->target = open;
    f->ramp_frame = 0;
}

double jw_filter_weight(JWMenuFilter *f) {
    const double weight = f->mix;
    if (f->ramp_frame < JW_MENU_RAMP_FRAMES) {
        double t = (double)++f->ramp_frame / JW_MENU_RAMP_FRAMES;
        f->mix = f->from + ((double)f->target - f->from) * (0.5 - 0.5 * cos(pi * t));
    }
    return weight;
}

double jw_filter_sample(JWMenuFilter *f, int channel, double dry, double weight) {
    double wet = dry;
    /* Keep the wet branch warm even when bypassed, so entry has no cold-filter pop. */
    for (int stage = 0; stage < 2; ++stage) {
        double *z = f->state[channel][stage];
        double out = f->b0 * wet + z[0];
        z[0] = f->b1 * wet - f->a1 * out + z[1];
        z[1] = f->b0 * wet - f->a2 * out;
        wet = out;
    }
    return (1.0 - weight) * dry + weight * 0.9 * wet;
}
