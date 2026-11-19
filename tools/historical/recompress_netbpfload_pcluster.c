// Recompress the first EROFS pcluster without changing its allocated size.
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lz4.h"
#include "lz4hc.h"

#define PCLUSTER_BYTES 40960
#define PCLUSTER_OFFSET 335015936LL

static void *read_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    void *buf;
    long n;
    if (!f) { perror(path); exit(1); }
    if (fseek(f, 0, SEEK_END) || (n = ftell(f)) < 0 || fseek(f, 0, SEEK_SET)) {
        perror("seek"); exit(1);
    }
    buf = malloc((size_t)n + 1);
    if (!buf || fread(buf, 1, (size_t)n, f) != (size_t)n) {
        perror("read"); exit(1);
    }
    fclose(f);
    *size = (size_t)n;
    return buf;
}

int main(int argc, char **argv) {
    void *old_data, *new_data, *compressed, *decompressed, *recompressed, *encoded_raw, *verified;
    size_t old_size, new_size;
    unsigned int inputmargin = 0, newmargin = 0;
    FILE *image, *out;
    LZ4_streamHC_t *stream;
    int decoded, source_consumed, encoded, roundtrip;

    if (argc != 5) {
        fprintf(stderr, "usage: %s IMAGE OLD_PAYLOAD NEW_PAYLOAD OUTPUT_PCLUSTER\n", argv[0]);
        return 2;
    }
    old_data = read_file(argv[2], &old_size);
    new_data = read_file(argv[3], &new_size);
    if (old_size != new_size || old_size == 0) {
        fprintf(stderr, "payload sizes differ or are empty\n"); return 1;
    }
    compressed = calloc(1, PCLUSTER_BYTES);
    decompressed = calloc(1, old_size);
    recompressed = calloc(1, PCLUSTER_BYTES);
    encoded_raw = calloc(1, PCLUSTER_BYTES);
    verified = calloc(1, old_size);
    stream = LZ4_createStreamHC();
    if (!compressed || !decompressed || !recompressed || !encoded_raw || !verified || !stream) return 1;

    image = fopen(argv[1], "rb");
    if (!image || fseeko(image, PCLUSTER_OFFSET, SEEK_SET) ||
        fread(compressed, 1, PCLUSTER_BYTES, image) != PCLUSTER_BYTES) {
        perror("image read"); return 1;
    }
    fclose(image);

    while (inputmargin < PCLUSTER_BYTES && !((unsigned char *)compressed)[inputmargin]) ++inputmargin;
    if (inputmargin >= PCLUSTER_BYTES) {
        fprintf(stderr, "compressed pcluster is all zero\n"); return 1;
    }
    decoded = LZ4_decompress_safe_partial((char *)compressed + inputmargin, decompressed,
                                          PCLUSTER_BYTES - inputmargin,
                                          (int)old_size, (int)old_size);
    if (decoded < 0 || (size_t)decoded > old_size) {
        fprintf(stderr, "original pcluster decode failed: %d\n", decoded); return 1;
    }
    if (memcmp(decompressed, old_data, (size_t)decoded)) {
        size_t i;
        for (i = 0; i < (size_t)decoded && ((unsigned char *)decompressed)[i] == ((unsigned char *)old_data)[i]; ++i) {}
        fprintf(stderr, "original compare first mismatch=%zu decoded=%d\n", i, decoded);
        if (i + 72 != old_size || decoded != (int)old_size) return 1;
        decoded = (int)i;
        printf("tail_bytes_handled_by_second_pcluster=%zu\n", old_size - i);
    }

    source_consumed = decoded;
    encoded = LZ4_compress_HC_destSize(stream, new_data, encoded_raw,
                                       &source_consumed, PCLUSTER_BYTES, 9);
    if (!encoded || source_consumed != decoded || encoded > PCLUSTER_BYTES) {
        fprintf(stderr, "recompression failed: encoded=%d consumed=%d decoded=%d\n",
                encoded, source_consumed, decoded); return 1;
    }
    memcpy((char *)recompressed + PCLUSTER_BYTES - encoded, encoded_raw, (size_t)encoded);
    while (newmargin < PCLUSTER_BYTES && !((unsigned char *)recompressed)[newmargin]) ++newmargin;
    roundtrip = LZ4_decompress_safe_partial((char *)recompressed + newmargin, verified,
                                            PCLUSTER_BYTES - newmargin, decoded, decoded);
    if (roundtrip != decoded || memcmp(verified, new_data, (size_t)decoded)) {
        fprintf(stderr, "new pcluster roundtrip failed: %d\n", roundtrip); return 1;
    }

    out = fopen(argv[4], "wb");
    if (!out || fwrite(recompressed, 1, PCLUSTER_BYTES, out) != PCLUSTER_BYTES || fclose(out)) {
        perror("output"); return 1;
    }
    printf("decoded_bytes=%d\nencoded_bytes=%d\nsource_consumed=%d\npcluster_bytes=%d\nroundtrip=ok\n",
           decoded, encoded, source_consumed, PCLUSTER_BYTES);
    return 0;
}
