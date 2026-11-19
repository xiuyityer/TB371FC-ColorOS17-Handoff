// Exercise the Android media route with a very quiet stereo signal.
#include <aaudio/AAudio.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    AAudioStreamBuilder* builder = NULL;
    AAudioStream* stream = NULL;
    aaudio_result_t rc = AAudio_createStreamBuilder(&builder);
    if (rc != AAUDIO_OK) goto done;
    AAudioStreamBuilder_setDirection(builder, AAUDIO_DIRECTION_OUTPUT);
    AAudioStreamBuilder_setUsage(builder, AAUDIO_USAGE_MEDIA);
    AAudioStreamBuilder_setPerformanceMode(builder, AAUDIO_PERFORMANCE_MODE_NONE);
    AAudioStreamBuilder_setChannelCount(builder, 2);
    AAudioStreamBuilder_setFormat(builder, AAUDIO_FORMAT_PCM_I16);
    AAudioStreamBuilder_setSampleRate(builder, 48000);
    rc = AAudioStreamBuilder_openStream(builder, &stream);
    if (rc != AAUDIO_OK) goto done;
    if (AAudioStream_getChannelCount(stream) != 2 ||
        AAudioStream_getFormat(stream) != AAUDIO_FORMAT_PCM_I16) {
        rc = AAUDIO_ERROR_INVALID_FORMAT;
        goto done;
    }
    rc = AAudioStream_requestStart(stream);
    if (rc != AAUDIO_OK) goto done;
    const int rate = AAudioStream_getSampleRate(stream);
    printf("rate=%d device=%d\n", rate, AAudioStream_getDeviceId(stream));
    fflush(stdout);
    int16_t buffer[480 * 2];
    int frame = 0;
    while (frame < 16 * rate) {
        for (int i = 0; i < 480; ++i) {
            buffer[2*i] = (int16_t)(32 * sin(2 * M_PI * 330 * (frame+i) / rate));
            buffer[2*i+1] = (int16_t)(32 * sin(2 * M_PI * 550 * (frame+i) / rate));
        }
        rc = AAudioStream_write(stream, buffer, 480, 1000000000LL);
        if (rc <= 0) break;
        frame += rc;
    }
    printf("frames=%d xruns=%d\n", frame, AAudioStream_getXRunCount(stream));
    if (rc >= 0 && frame < 16 * rate) rc = AAUDIO_ERROR_TIMEOUT;
done:
    if (stream) AAudioStream_close(stream);
    if (builder) AAudioStreamBuilder_delete(builder);
    if (rc < 0) fprintf(stderr, "%s\n", AAudio_convertResultToText(rc));
    return rc < 0;
}
