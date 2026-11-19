/* SPDX-License-Identifier: GPL-2.0-or-later */
/* PID 1 shim: load the ABI-matched EROFS module, then delegate to KSU init.
 * No libc, no command channel, no partition writes, no module-force flags.
 */
typedef unsigned long ulong;
void *memcpy(void *dst, const void *src, ulong n)
{
    volatile unsigned char *d = dst;
    const unsigned char *s = src;
    for (ulong i = 0; i < n; ++i) d[i] = s[i];
    return dst;
}
static long call(long nr, long a, long b, long c, long d)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x8 __asm__("x8") = nr;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x8) : "memory", "cc");
    return x0;
}
static void report(long result)
{
    const char *path = "/c17_kmsg";
    call(33, -100, (long)path, 0020600, 267); /* mknodat: char 1:11 */
    long fd = call(56, -100, (long)path, 1, 0);
    if (fd < 0) return;
    char line[96] = "<6>C17_EARLY_EROFS finit_module=";
    ulong n = 0;
    while (line[n]) ++n;
    if (result < 0) { line[n++] = '-'; result = -result; }
    char digits[24]; ulong count = 0;
    do { digits[count++] = '0' + result % 10; result /= 10; } while (result);
    while (count) line[n++] = digits[--count];
    line[n++] = '\n';
    call(64, fd, (long)line, n, 0);
    call(57, fd, 0, 0, 0);
}
__attribute__((noreturn,used)) void entry(ulong *stack)
{
    char **argv = (char **)(stack + 1);
    char **envp = argv + stack[0] + 1;
    long fd = call(56, -100, (long)"/erofs.ko", 0, 0);
    long result = fd;
    if (fd >= 0) {
        result = call(273, fd, (long)"", 0, 0); /* finit_module, flags=0 */
        call(57, fd, 0, 0, 0);
    }
    report(result);
    call(221, (long)"/ksu_init", (long)argv, (long)envp, 0);
    for (;;) call(93, 127, 0, 0, 0);
}
__asm__(".global _start\n_start:\nmov x0, sp\nbl entry\nb .\n");
