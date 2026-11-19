#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <sys/mount.h>
#include <unistd.h>

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    if (unshare(CLONE_NEWNS) || mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)) {
        perror("private mount namespace");
        return 1;
    }
    execv(argv[1], argv + 1);
    perror("execv");
    return 1;
}
