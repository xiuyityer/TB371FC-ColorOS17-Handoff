/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Export source inode metadata directly; host ownership is not Android metadata. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __APPLE__
#include <CommonCrypto/CommonDigest.h>
#else
#include <openssl/sha.h>
#define CC_SHA256_CTX SHA256_CTX
#define CC_LONG size_t
#define CC_SHA256_Init SHA256_Init
#define CC_SHA256_Update SHA256_Update
#define CC_SHA256_Final SHA256_Final
#define CC_SHA256_DIGEST_LENGTH SHA256_DIGEST_LENGTH
#endif
#include "erofs/config.h"
#include "erofs/dir.h"
#include "erofs/io.h"
#include "erofs/print.h"

struct walk { struct erofs_dir_context ctx; const char *path; };
static int hash_files;
static int visit(struct erofs_sb_info *sbi, erofs_nid_t nid, const char *path);

static void quoted(const char *s) {
    putchar('"');
    for (; *s; s++) {
        unsigned char c = *s;
        if (c == '"' || c == '\\') printf("\\%c", c);
        else if (c < 32) printf("\\u%04x", c);
        else putchar(c);
    }
    putchar('"');
}

static int child(struct erofs_dir_context *ctx) {
    struct walk *w = (struct walk *)ctx;
    if (ctx->dot_dotdot) return 0;
    char *path;
    if (asprintf(&path, "%s/%.*s", w->path, ctx->de_namelen, ctx->dname) < 0) return -1;
    int rc = visit(ctx->dir->sbi, ctx->de_nid, path);
    free(path);
    return rc;
}

static int visit(struct erofs_sb_info *sbi, erofs_nid_t nid, const char *path) {
    struct erofs_inode vi = { .sbi = sbi, .nid = nid };
    int rc = erofs_read_inode_from_disk(&vi);
    if (rc) return rc;
    printf("{\"path\":"); quoted(*path ? path : "/");
    printf(",\"nid\":%llu,\"mode\":%u,\"uid\":%u,\"gid\":%u,\"size\":%llu,\"mtime\":%llu,\"xattrs\":{",
           (unsigned long long)nid, vi.i_mode, vi.i_uid, vi.i_gid,
           (unsigned long long)vi.i_size, (unsigned long long)vi.i_mtime);
    int len = erofs_listxattr(&vi, NULL, 0), count = 0;
    if (len > 0) {
        char *names = malloc(len);
        if (!names) return -1;
        rc = erofs_listxattr(&vi, names, len);
        if (rc < 0) return rc;
        for (int pos = 0; pos < len; pos += strlen(names + pos) + 1) {
            char *name = names + pos;
            int size = erofs_getxattr(&vi, name, NULL, 0);
            if (size < 0) return size;
            unsigned char *value = malloc(size + 1);
            if (!value) return -1;
            rc = erofs_getxattr(&vi, name, (char *)value, size);
            if (rc != size) return -1;
            if (count++) putchar(',');
            quoted(name); printf(":\"");
            for (int i = 0; i < size; i++) printf("%02x", value[i]);
            putchar('"'); free(value);
        }
        free(names);
    } else if (len < 0) return len;
    printf("}");
    if (hash_files && (S_ISREG(vi.i_mode) || S_ISLNK(vi.i_mode))) {
        CC_SHA256_CTX ctx;
        CC_SHA256_Init(&ctx);
        char *buffer = malloc(1U << 20);
        if (!buffer) return -1;
        for (erofs_off_t offset = 0; offset < vi.i_size;) {
            erofs_off_t length = vi.i_size - offset;
            if (length > (1U << 20)) length = 1U << 20;
            rc = erofs_pread(&vi, buffer, length, offset);
            if (rc) { free(buffer); return rc; }
            CC_SHA256_Update(&ctx, buffer, (CC_LONG)length);
            offset += length;
        }
        unsigned char digest[CC_SHA256_DIGEST_LENGTH];
        CC_SHA256_Final(digest, &ctx);
        free(buffer);
        printf(",\"sha256\":\"");
        for (int i = 0; i < sizeof(digest); i++) printf("%02x", digest[i]);
        putchar('"');
    }
    printf("}\n");
    rc = 0;
    if (S_ISDIR(vi.i_mode)) {
        struct walk w = { .ctx = { .dir = &vi, .cb = child }, .path = path };
        rc = erofs_iterate_dir(&w.ctx, false);
    }
    return rc;
}

int main(int argc, char **argv) {
    struct erofs_sb_info sbi = {};
    if (argc != 2 && argc != 3) return 2;
    hash_files = argc == 3 && !strcmp(argv[2], "--hash");
    erofs_init_configure(); cfg.c_dbg_lvl = -1;
    int rc = erofs_dev_open(&sbi, argv[1], O_RDONLY);
    if (!rc) rc = erofs_read_superblock(&sbi);
    if (!rc) rc = visit(&sbi, sbi.root_nid, "");
    erofs_dev_close(&sbi);
    if (rc) fprintf(stderr, "metadata traversal failed: %d\n", rc);
    return rc ? 1 : 0;
}
