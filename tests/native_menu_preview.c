/* Offline render through the shipping mixer; never opens an audio device. */
#include <stdio.h>
#include <stdlib.h>
#include "../probes/JamieWinNativeAudioTest/Native/mixer.h"

int main(int argc, char **argv) {
    const size_t frames = 24u * 48000u;
    if (argc != 3) return 1;
    int16_t *source = malloc(frames * 4);
    FILE *input = fopen(argv[1], "rb");
    if (!source || !input) return 2;
    if (fread(source, 4, frames, input) != frames) return 3;
    fclose(input);
    FILE *output = fopen(argv[2], "wb");
    if (!output) return 4;
    JWMixer mixer = {0};
    mixer.assets[1] = (JWAsset){source, frames};
    mixer.music_volume = .45f;
    jw_music(&mixer, 2);
    int16_t block[960 * 2];
    for (size_t frame = 0; frame < frames; frame += 960) {
        jw_menu(&mixer, frame >= 6u * 48000u && frame < 16u * 48000u);
        jw_render(&mixer, block, 960);
        if (fwrite(block, 4, 960, output) != 960) return 5;
    }
    fclose(output);
    free(source);
    return mixer.music_rendered == frames && mixer.music_frame == 0 && mixer.menu.mix == 0 ? 0 : 6;
}
