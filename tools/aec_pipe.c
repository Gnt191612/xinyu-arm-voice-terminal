/* 独立SpeexDSP进程：输入麦克风帧与播放参考帧，输出消回声后的PCM。 */
#include <stdio.h>
#include <io.h>
#include <fcntl.h>
#include <speex/speex_echo.h>

int main(void) {
    short microphone[320], reference[320], clean[320];
    int rate = 16000;
    SpeexEchoState *echo = speex_echo_state_init(320, 8000);
    if (!echo) return 2;
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    speex_echo_ctl(echo, SPEEX_ECHO_SET_SAMPLING_RATE, &rate);
    while (fread(microphone, sizeof(short), 320, stdin) == 320) {
        if (fread(reference, sizeof(short), 320, stdin) != 320) break;
        speex_echo_cancellation(echo, microphone, reference, clean);
        if (fwrite(clean, sizeof(short), 320, stdout) != 320) break;
        fflush(stdout);
    }
    speex_echo_state_destroy(echo);
    return 0;
}
