/* Check the ring buffer map ABI used by native Android clients. Run as root. */
#include <errno.h>
#include <linux/bpf.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

static int fail(const char *operation)
{
    perror(operation);
    return 1;
}

#define INSN(op, dst, src, offset, immediate) \
    { .code = (op), .dst_reg = (dst), .src_reg = (src), \
      .off = (offset), .imm = (immediate) }

static int write_sample(int map_fd, int finish_helper)
{
    static const char license[] = "GPL";
    char verifier_log[8192] = {0};
    const struct bpf_insn copy_insns[] = {
        INSN(BPF_LD | BPF_DW | BPF_IMM, BPF_REG_1, BPF_PSEUDO_MAP_FD, 0, map_fd),
        INSN(0, 0, 0, 0, 0),
        INSN(BPF_ST | BPF_W | BPF_MEM, BPF_REG_10, 0, -4, 0x11223344),
        INSN(BPF_ALU64 | BPF_MOV | BPF_X, BPF_REG_2, BPF_REG_10, 0, 0),
        INSN(BPF_ALU64 | BPF_ADD | BPF_K, BPF_REG_2, 0, 0, -4),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_3, 0, 0, 4),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_4, 0, 0, BPF_RB_FORCE_WAKEUP),
        INSN(BPF_JMP | BPF_CALL, 0, 0, 0, BPF_FUNC_ringbuf_output),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_0, 0, 0, 1),
        INSN(BPF_JMP | BPF_EXIT, 0, 0, 0, 0),
    };
    const struct bpf_insn reservation_insns[] = {
        INSN(BPF_LD | BPF_DW | BPF_IMM, BPF_REG_1, BPF_PSEUDO_MAP_FD, 0, map_fd),
        INSN(0, 0, 0, 0, 0),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_2, 0, 0, 4),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_3, 0, 0, 0),
        INSN(BPF_JMP | BPF_CALL, 0, 0, 0, BPF_FUNC_ringbuf_reserve),
        INSN(BPF_JMP | BPF_JEQ | BPF_K, BPF_REG_0, 0, 4, 0),
        INSN(BPF_ST | BPF_W | BPF_MEM, BPF_REG_0, 0, 0, 0x11223344),
        INSN(BPF_ALU64 | BPF_MOV | BPF_X, BPF_REG_1, BPF_REG_0, 0, 0),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_2, 0, 0, BPF_RB_FORCE_WAKEUP),
        INSN(BPF_JMP | BPF_CALL, 0, 0, 0, finish_helper),
        INSN(BPF_ALU64 | BPF_MOV | BPF_K, BPF_REG_0, 0, 0, 1),
        INSN(BPF_JMP | BPF_EXIT, 0, 0, 0, 0),
    };
    const struct bpf_insn *insns = finish_helper ? reservation_insns : copy_insns;
    unsigned int insn_count = (finish_helper ? sizeof(reservation_insns) : sizeof(copy_insns))
                              / sizeof(*insns);
    union bpf_attr load = {
        .prog_type = BPF_PROG_TYPE_CGROUP_SKB,
        .expected_attach_type = BPF_CGROUP_INET_INGRESS,
        .insn_cnt = insn_count,
        .insns = (uintptr_t)insns,
        .license = (uintptr_t)license,
        .log_level = 1,
        .log_size = sizeof(verifier_log),
        .log_buf = (uintptr_t)verifier_log,
    };
    int prog = syscall(__NR_bpf, BPF_PROG_LOAD, &load, sizeof(load));
    if (prog < 0) {
        fail("BPF_PROG_LOAD (ringbuf writer)");
        fputs(verifier_log, stderr);
        return 1;
    }

    /* Execute the writer once on a synthetic Ethernet/IP frame. No attach. */
    unsigned char packet[64] = {[12] = 0x08, [14] = 0x45};
    union bpf_attr test = {
        .test = {
            .prog_fd = prog,
            .data_size_in = sizeof(packet),
            .data_in = (uintptr_t)packet,
            .repeat = 1,
        },
    };
    int ret = syscall(__NR_bpf, BPF_PROG_TEST_RUN, &test, sizeof(test));
    if (ret < 0)
        fail("BPF_PROG_TEST_RUN");
    close(prog);
    return ret < 0;
}

int main(int argc, char **argv)
{
    int test_events = argc == 2;
    int finish_helper = 0;
    if (test_events && strcmp(argv[1], "--submit") == 0)
        finish_helper = BPF_FUNC_ringbuf_submit;
    else if (test_events && strcmp(argv[1], "--discard") == 0)
        finish_helper = BPF_FUNC_ringbuf_discard;
    else if (argc > 2 || (test_events && strcmp(argv[1], "--events") != 0)) {
        fprintf(stderr, "Usage: %s [--events|--submit|--discard]\n", argv[0]);
        return 1;
    }
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || (unsigned long)page > UINT32_MAX) {
        fprintf(stderr, "Unexpected page size: %ld\n", page);
        return 1;
    }

    union bpf_attr create = {
        .map_type = BPF_MAP_TYPE_RINGBUF,
        .max_entries = (uint32_t)page,
    };
    int fd = syscall(__NR_bpf, BPF_MAP_CREATE, &create, sizeof(create));
    if (fd < 0)
        return fail("BPF_MAP_CREATE (RINGBUF)");

    struct bpf_map_info info = {0};
    union bpf_attr query = {
        .info = {
            .bpf_fd = fd,
            .info_len = sizeof(info),
            .info = (uintptr_t)&info,
        },
    };
    if (syscall(__NR_bpf, BPF_OBJ_GET_INFO_BY_FD, &query, sizeof(query)) < 0)
        return fail("BPF_OBJ_GET_INFO_BY_FD");
    if (info.type != BPF_MAP_TYPE_RINGBUF || info.max_entries != (uint32_t)page) {
        fprintf(stderr, "Unexpected map type or size: %u, %u\n", info.type, info.max_entries);
        return 1;
    }

    void *consumer = mmap(NULL, page, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (consumer == MAP_FAILED)
        return fail("mmap consumer");

    /* Producer counter plus the duplicated data region. */
    void *producer = mmap(NULL, 3 * page, PROT_READ, MAP_SHARED, fd, page);
    if (producer == MAP_FAILED)
        return fail("mmap producer");
    void *writable_producer = mmap(NULL, page, PROT_READ | PROT_WRITE, MAP_SHARED, fd, page);
    if (writable_producer != MAP_FAILED) {
        munmap(writable_producer, page);
        fprintf(stderr, "Producer mapping unexpectedly writable\n");
        return 1;
    }
    if (errno != EPERM && errno != EACCES) {
        return fail("writable producer returned unexpected errno");
    }

    if (mprotect(producer, page, PROT_READ | PROT_WRITE) == 0) {
        fprintf(stderr, "Producer mapping unexpectedly upgraded to writable\n");
        return 1;
    }
    if (errno != EPERM && errno != EACCES)
        return fail("mprotect producer returned unexpected errno");

    struct pollfd pollfd = {.fd = fd, .events = POLLIN};
    int ready = poll(&pollfd, 1, 0);
    if (ready < 0)
        return fail("poll");
    if (ready != 0 || *(const volatile uint64_t *)consumer ||
        *(const volatile uint64_t *)producer) {
        fprintf(stderr, "A newly created ring should be empty\n");
        return 1;
    }

    if (test_events) {
        if (write_sample(fd, finish_helper))
            return 1;
        ready = poll(&pollfd, 1, 1000);
        if (ready != 1 || !(pollfd.revents & POLLIN)) {
            fprintf(stderr, "Ring did not become readable\n");
            return 1;
        }
        const unsigned char *data = (const unsigned char *)producer + page;
        uint32_t payload, alias;
        uint32_t length = __atomic_load_n((const uint32_t *)data, __ATOMIC_ACQUIRE);
        uint64_t position = __atomic_load_n((const uint64_t *)producer, __ATOMIC_ACQUIRE);
        memcpy(&payload, data + BPF_RINGBUF_HDR_SZ, sizeof(payload));
        memcpy(&alias, data + page + BPF_RINGBUF_HDR_SZ, sizeof(alias));
        uint32_t expected_length = 4;
        if (finish_helper == BPF_FUNC_ringbuf_discard)
            expected_length |= BPF_RINGBUF_DISCARD_BIT;
        if (position != 16 || length != expected_length || payload != 0x11223344 || alias != payload) {
            fprintf(stderr, "Unexpected ring record or alias\n");
            return 1;
        }
        __atomic_store_n((uint64_t *)consumer, position, __ATOMIC_RELEASE);
        if (poll(&pollfd, 1, 0) != 0) {
            fprintf(stderr, "Ring remains readable after consumption\n");
            return 1;
        }
        puts("PASS: BPF output, record read, alias, and consumption");
    }

    munmap(producer, 3 * page);
    munmap(consumer, page);
    close(fd);
    puts("PASS: ring map creation, info, mmap protection, and empty poll");
    return 0;
}
