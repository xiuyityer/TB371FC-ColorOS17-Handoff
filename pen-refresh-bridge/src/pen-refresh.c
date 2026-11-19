// SPDX-License-Identifier: GPL-3.0-or-later
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Observe evdev without EVIOCGRAB. Never write touch or panel registers. */
#define VERSION "0.4.1"
#define LEAVE_MS 2200
#define ENTER_GRACE_MS 2500
static volatile sig_atomic_t stopping;
static char state_dir[512], module_dir[512], checkpoint[600], pidpath[600];
static bool active;
static long long entered, last_activity, last_fw_present;
static long long last_attempt;
static long long last_native_check;
static unsigned long detection_count;
struct snapshot { char min[32], peak[32], hz[32], native[32], pencil[32]; int width, height; };
static struct snapshot saved;

static long long now_ms(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static void logmsg(const char *fmt, ...) {
    fprintf(stdout, "[%lld] ", now_ms());
    va_list ap; va_start(ap, fmt); vfprintf(stdout, fmt, ap); va_end(ap);
    fputc('\n', stdout); fflush(stdout);
}
static void stop_signal(int sig) { (void)sig; stopping = 1; }
static bool numeric(const char *s) {
    if (!s[0] || strlen(s) > 24) return false;
    char *end; double v = strtod(s, &end);
    return !*end && v >= 0 && v <= 1000;
}
static bool valid_setting(const char *s) { return !strcmp(s, "null") || numeric(s); }
static bool owned_rate(const char *s) {
    if (!numeric(s)) return false;
    double v = strtod(s, NULL); return v > 119.99 && v < 120.01;
}
static int wait_child(pid_t pid) {
    int status = -1;
    while (waitpid(pid, &status, 0) < 0) { if (errno != EINTR) return -1; }
    return WIFEXITED(status) ? WEXITSTATUS(status) : -1;
}
/* Binder shellCommand checks every supplied descriptor. system_server cannot
 * use our private /data/adb log FD. Give commands /dev/null for stdin/stderr,
 * and either a pipe or /dev/null for stdout, rather than inheriting that FD. */
static void command_stdio(bool capture_stdout) {
    int fd = open("/dev/null", O_RDWR);
    if (fd < 0) _exit(126);
    if (dup2(fd, STDIN_FILENO) < 0 || dup2(fd, STDERR_FILENO) < 0 ||
        (!capture_stdout && dup2(fd, STDOUT_FILENO) < 0)) _exit(126);
    if (fd > STDERR_FILENO) close(fd);
}
static FILE *command_pipe(const char *cmd, pid_t *pid) {
    int fds[2]; if (pipe2(fds, O_CLOEXEC)) return NULL;
    *pid = fork();
    if (*pid < 0) { close(fds[0]); close(fds[1]); return NULL; }
    if (!*pid) {
        command_stdio(true);
        dup2(fds[1], STDOUT_FILENO); close(fds[0]); close(fds[1]);
        execl("/system/bin/timeout", "timeout", "-s", "KILL", "8", "/system/bin/sh", "-c", cmd, (char *)NULL); _exit(127);
    }
    close(fds[1]); FILE *f = fdopen(fds[0], "r");
    if (!f) { close(fds[0]); wait_child(*pid); }
    return f;
}
static int run(const char *cmd) {
    pid_t pid = fork(); if (pid < 0) return -1;
    if (!pid) {
        command_stdio(false);
        execl("/system/bin/timeout", "timeout", "-s", "KILL", "8", "/system/bin/sh", "-c", cmd, (char *)NULL); _exit(127);
    }
    int status = wait_child(pid);
    if (status) {
        logmsg("COMMAND_FAILED status=%d cmd=%s", status, cmd); return -1;
    }
    return 0;
}
static int output(const char *cmd, char *buf, size_t size) {
    pid_t pid; FILE *f = command_pipe(cmd, &pid); if (!f) return -1;
    size_t len = fread(buf, 1, size - 1, f); buf[len] = 0;
    char discard[4096]; while (fread(discard, 1, sizeof(discard), f)) {}
    fclose(f); int rc = wait_child(pid);
    while (len && (buf[len-1] == '\n' || buf[len-1] == '\r')) buf[--len] = 0;
    if (rc) logmsg("COMMAND_READ_FAILED status=%d cmd=%s", rc, cmd);
    return rc == 0 ? 0 : -1;
}
static int get_setting(const char *key, char *value, size_t size) {
    char cmd[160]; snprintf(cmd, sizeof(cmd), "/system/bin/settings get system %s", key);
    return output(cmd, value, size) || !valid_setting(value) ? -1 : 0;
}
static int set_setting(const char *key, const char *value) {
    char cmd[200];
    if (!valid_setting(value)) return -1;
    if (!strcmp(value, "null")) snprintf(cmd, sizeof(cmd), "/system/bin/settings delete system %s >/dev/null", key);
    else snprintf(cmd, sizeof(cmd), "/system/bin/settings put system %s %s", key, value);
    return run(cmd);
}
static int get_native(char *value, size_t size) {
    return output("/system/bin/settings get secure oplus_customize_screen_refresh_rate", value, size) || !valid_setting(value) ? -1 : 0;
}
static int set_native(const char *value) {
    char cmd[200]; if (!valid_setting(value)) return -1;
    if (!strcmp(value, "null")) strcpy(cmd, "/system/bin/settings delete secure oplus_customize_screen_refresh_rate");
    else snprintf(cmd, sizeof(cmd), "/system/bin/settings put secure oplus_customize_screen_refresh_rate %s", value);
    return run(cmd);
}
static int get_pencil(char *value, size_t size) {
    return output("/system/bin/settings get global settings_enable_oppo_pencil", value, size) || !valid_setting(value) ? -1 : 0;
}
static int set_pencil(const char *value) {
    char cmd[200]; if (!valid_setting(value)) return -1;
    if (!strcmp(value, "null")) strcpy(cmd, "/system/bin/settings delete global settings_enable_oppo_pencil");
    else snprintf(cmd, sizeof(cmd), "/system/bin/settings put global settings_enable_oppo_pencil %s", value);
    return run(cmd);
}
static int get_preferred(struct snapshot *s) {
    char text[256];
    if (output("/system/bin/cmd display get-user-preferred-display-mode 0", text, sizeof(text))) return -1;
    if (strstr(text, ": null")) { s->width = -1; s->height = -1; strcpy(s->hz, "0.0"); return 0; }
    if (sscanf(text, "User preferred display mode: %d %d %31s", &s->width, &s->height, s->hz) != 3) return -1;
    if (!numeric(s->hz)) return -1;
    if (s->width == -1 && s->height == -1 && strtod(s->hz, NULL) == 0) return 0;
    return s->width > 0 && s->width <= 10000 && s->height > 0 && s->height <= 10000 ? 0 : -1;
}
static int set_preferred(const struct snapshot *s) {
    char cmd[200];
    if (s->width == -1 && s->height == -1) return run("/system/bin/cmd display clear-user-preferred-display-mode 0");
    snprintf(cmd, sizeof(cmd), "/system/bin/cmd display set-user-preferred-display-mode %d %d %s 0", s->width, s->height, s->hz);
    return run(cmd);
}
static int save_checkpoint(void) {
    char tmp[620]; snprintf(tmp, sizeof(tmp), "%s.tmp", checkpoint);
    FILE *f = fopen(tmp, "we"); if (!f) return -1;
    fprintf(f, "PEN_REFRESH_V3\n%s\n%s\n%d %d %s\n%s\n%s\n", saved.min, saved.peak, saved.width, saved.height, saved.hz, saved.native, saved.pencil);
    int rc = fflush(f); if (!rc) rc = fsync(fileno(f));
    if (fclose(f)) rc = -1;
    return rc ? -1 : rename(tmp, checkpoint);
}
static int load_checkpoint(void) {
    FILE *f = fopen(checkpoint, "re"); if (!f) return errno == ENOENT ? 1 : -1;
    char magic[32]; int rc = fscanf(f, "%31s %31s %31s %d %d %31s", magic, saved.min, saved.peak, &saved.width, &saved.height, saved.hz);
    saved.native[0] = saved.pencil[0] = 0;
    if (rc == 6 && (!strcmp(magic, "PEN_REFRESH_V2") || !strcmp(magic, "PEN_REFRESH_V3")) && (fscanf(f, "%31s", saved.native) != 1 || !valid_setting(saved.native))) rc = -1;
    if (rc == 6 && !strcmp(magic, "PEN_REFRESH_V3") && (fscanf(f, "%31s", saved.pencil) != 1 || !valid_setting(saved.pencil))) rc = -1;
    fclose(f);
    if (rc != 6 || (strcmp(magic, "PEN_REFRESH_V1") && strcmp(magic, "PEN_REFRESH_V2") && strcmp(magic, "PEN_REFRESH_V3")) || !valid_setting(saved.min) || !valid_setting(saved.peak) || !numeric(saved.hz)) return -1;
    bool no_pref = saved.width == -1 && saved.height == -1 && strtod(saved.hz, NULL) == 0;
    return no_pref || (saved.width > 0 && saved.width <= 10000 && saved.height > 0 && saved.height <= 10000) ? 0 : -1;
}
/* Only restore fields still set to our vote; preserve a later user change. */
static int restore(const char *reason) {
    char value[32]; struct snapshot current; int rc = 0;
    if (get_setting("peak_refresh_rate", value, sizeof(value))) rc = -1;
    else if (owned_rate(value) && set_setting("peak_refresh_rate", saved.peak)) rc = -1;
    if (get_setting("min_refresh_rate", value, sizeof(value))) rc = -1;
    else if (owned_rate(value) && set_setting("min_refresh_rate", saved.min)) rc = -1;
    if (get_preferred(&current)) rc = -1;
    else if (current.width == 1840 && current.height == 2944 && owned_rate(current.hz) && set_preferred(&saved)) rc = -1;
    if (saved.native[0]) {
        if (get_native(value, sizeof(value))) rc = -1;
        else if (!strcmp(value, "3") && set_native(saved.native)) rc = -1;
    }
    if (saved.pencil[0]) {
        if (get_pencil(value, sizeof(value))) rc = -1;
        else if (!strcmp(value, "1") && set_pencil(saved.pencil)) rc = -1;
    }
    if (!rc) unlink(checkpoint);
    active = false;
    logmsg("RESTORE reason=%s rc=%d detection_notifications=%lu", reason, rc, detection_count);
    return rc;
}
static int read_int(const char *path) {
    FILE *f = fopen(path, "re"); if (!f) return -1;
    int n = -1; if (fscanf(f, "%d", &n) != 1) n = -1; fclose(f); return n;
}
static bool screen_on(void) {
    char buf[32]; FILE *f = fopen("/sys/class/drm/card0-DSI-1/dpms", "re");
    if (!f) return false;
    bool on = fgets(buf, sizeof(buf), f) && !strncmp(buf, "On", 2); fclose(f); return on;
}
static double active_rate(void) {
    pid_t pid;
    FILE *f = command_pipe("/system/bin/dumpsys display 2>/dev/null", &pid); if (!f) return -1;
    char *line = NULL; size_t cap = 0; double rate = -1;
    while (getline(&line, &cap, f) > 0) {
        if (rate < 0 && strstr(line, "DisplayDeviceInfo{")) {
            char *p = strstr(line, "renderFrameRate "); if (p) rate = strtod(p + 16, NULL);
        }
    }
    free(line); fclose(f); if (wait_child(pid)) return -1; return rate;
}
static int apply_vote(void) {
    struct snapshot target = {.width = 1840, .height = 2944}; strcpy(target.hz, "120.00001");
    return set_pencil("1") || set_native("3") || set_setting("peak_refresh_rate", "120.00001") ||
           set_setting("min_refresh_rate", "120.00001") || set_preferred(&target) ? -1 : 0;
}
static int enter_vote(const char *reason) {
    if (!screen_on()) return 0;
    double rate = active_rate();
    if (rate < 0) return -1;
    if (get_setting("min_refresh_rate", saved.min, sizeof(saved.min)) ||
        get_setting("peak_refresh_rate", saved.peak, sizeof(saved.peak)) || get_preferred(&saved) || get_native(saved.native, sizeof(saved.native)) || get_pencil(saved.pencil, sizeof(saved.pencil))) return -1;
    /* ColorOS selector 2 is an explicit 60-Hz choice; never raise it. */
    if (!strcmp(saved.native, "2") || (numeric(saved.peak) && strtod(saved.peak, NULL) < 119.9)) return 0;
    if (save_checkpoint()) return -1;
    active = true; entered = last_activity = last_fw_present = now_ms();
    last_native_check = entered;
    if (apply_vote()) {
        restore("enter_failed"); return -1;
    }
    logmsg("VOTE_120 reason=%s from=%.5f native_before=%s saved_min=%s saved_peak=%s", reason, rate, saved.native, saved.min, saved.peak);
    return 0;
}
static int sync_native_policy(void) {
    char value[32], native[32], pencil[32];
    if (get_native(native, sizeof(native)) || get_setting("peak_refresh_rate", value, sizeof(value)) || get_pencil(pencil, sizeof(pencil))) return -1;
    if (!strcmp(native, "3") && owned_rate(value) && !strcmp(pencil, "1")) return 0;
    if (!strcmp(native, "2")) return restore("user_selected_60");
    /* Remember a later high/auto selection for pen-up, but keep the native
     * selector at 120 while this pen session needs it. No framework patch. */
    if (strcmp(native, "3")) strcpy(saved.native, native);
    if (strcmp(pencil, "1")) strcpy(saved.pencil, pencil);
    if (!owned_rate(value)) strcpy(saved.peak, value);
    if (get_setting("min_refresh_rate", value, sizeof(value))) return -1;
    if (!owned_rate(value)) strcpy(saved.min, value);
    struct snapshot current;
    if (get_preferred(&current)) return -1;
    if (!(current.width == 1840 && current.height == 2944 && owned_rate(current.hz))) {
        saved.width = current.width; saved.height = current.height; strcpy(saved.hz, current.hz);
    }
    if (save_checkpoint() || apply_vote()) return -1;
    logmsg("POLICY_REASSERT native_requested=%s deferred_until_pen_left", saved.native);
    return 0;
}
static int open_input(const char *wanted) {
    char name[128], node[128], sys[160];
    for (int i = 0; i < 64; i++) {
        snprintf(sys, sizeof(sys), "/sys/class/input/event%d/device/name", i);
        FILE *f = fopen(sys, "re"); if (!f) continue;
        if (!fgets(name, sizeof(name), f)) name[0] = 0; fclose(f);
        name[strcspn(name, "\n")] = 0;
        if (strcmp(name, wanted)) continue;
        snprintf(node, sizeof(node), "/dev/input/event%d", i);
        int fd = open(node, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd >= 0) {
            int clock = CLOCK_MONOTONIC;
            if (ioctl(fd, EVIOCSCLOCKID, &clock)) { logmsg("INPUT_CLOCK_FAILED errno=%d", errno); close(fd); return -1; }
            logmsg("INPUT %s %s", wanted, node);
        }
        return fd;
    }
    return -1;
}
static bool disabled(void) {
    char p[600];
    snprintf(p, sizeof(p), "%s/disable", module_dir); if (!access(p, F_OK)) return true;
    snprintf(p, sizeof(p), "%s/remove", module_dir); return !access(p, F_OK);
}
static int input_events(int fd, bool touch) {
    static bool touch_dropped, pen_dropped;
    bool *dropped = touch ? &touch_dropped : &pen_dropped;
    struct input_event events[64]; ssize_t n;
    while ((n = read(fd, events, sizeof(events))) > 0) {
        if ((size_t)n % sizeof(events[0])) { logmsg("INPUT_BAD_LENGTH touch=%d n=%ld", touch, (long)n); return -1; }
        for (size_t i = 0; i < (size_t)n / sizeof(events[0]); i++) {
            struct input_event *e = &events[i];
            if (e->type == EV_SYN && e->code == SYN_DROPPED) {
                *dropped = true;
                logmsg("INPUT_DROPPED touch=%d resynchronizing_without_releasing_vote", touch);
                continue;
            }
            if (*dropped) {
                /* evdev requires ignoring the incomplete frame through the
                 * next SYN_REPORT, then querying current state. Retain the
                 * lease: queue overflow is not a physical pen departure. */
                if (e->type == EV_SYN && e->code == SYN_REPORT) {
                    unsigned char keys[(KEY_MAX + 8) / 8] = {0};
                    int rc = ioctl(fd, EVIOCGKEY(sizeof(keys)), keys);
                    bool present = !touch && rc >= 0 &&
                        ((keys[BTN_TOOL_PEN/8] & (1u << (BTN_TOOL_PEN%8))) ||
                         (keys[BTN_TOUCH/8] & (1u << (BTN_TOUCH%8))));
                    *dropped = false;
                    if (present || read_int("/proc/fw_pen_state") == 1) {
                        if (!active && enter_vote("evdev_resync")) return -1;
                        if (active) last_activity = now_ms();
                    }
                    logmsg("INPUT_RESYNC touch=%d key_query_rc=%d active=%d", touch, rc, active);
                }
                continue;
            }
            if (touch && e->type == EV_KEY && e->code == 606 && e->value == 1) {
                detection_count++;
                long long event_ms = (long long)e->time.tv_sec * 1000 + e->time.tv_usec / 1000;
                long long now = now_ms();
                if (!active && now - event_ms >= 0 && now - event_ms < 2000 && now - last_attempt > 2000) {
                    last_attempt = now;
                    if (enter_vote("detect_606")) return -1;
                }
            } else if (!touch) {
                if (!active && e->type == EV_KEY && (e->code == BTN_TOOL_PEN || e->code == BTN_TOUCH) && e->value == 1) {
                    if (enter_vote("real_pen_input")) return -1;
                }
                if (active && e->type != EV_SYN) last_activity = now_ms();
            }
        }
    }
    if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)) {
        logmsg("INPUT_READ_FAILED touch=%d n=%ld errno=%d", touch, (long)n, errno); return -1;
    }
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[1], "--run") && strcmp(argv[1], "--restore"))) {
        fprintf(stderr, "pen-refresh %s: --run|--restore MODULE_DIR STATE_DIR\n", VERSION); return 2;
    }
    umask(077);
    signal(SIGCHLD, SIG_DFL);
    if (strlen(argv[2]) >= sizeof(module_dir) || strlen(argv[3]) >= sizeof(state_dir)) return 2;
    strcpy(module_dir, argv[2]); strcpy(state_dir, argv[3]);
    mkdir(state_dir, 0700);
    snprintf(checkpoint, sizeof(checkpoint), "%s/checkpoint", state_dir);
    snprintf(pidpath, sizeof(pidpath), "%s/pid", state_dir);
    char lockpath[600]; snprintf(lockpath, sizeof(lockpath), "%s/lock", state_dir);
    int lock = open(lockpath, O_CREAT | O_RDWR | O_CLOEXEC, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) { logmsg("ALREADY_RUNNING_OR_LOCK_FAILED"); return 1; }
    int cp = load_checkpoint();
    if (cp < 0 || (!cp && restore("startup_recovery"))) { logmsg("CHECKPOINT_RECOVERY_FAILED"); return 1; }
    if (!strcmp(argv[1], "--restore")) return 0;
    char board[64] = {0}, user[32] = {0};
    int board_rc = output("/system/bin/getprop ro.product.board", board, sizeof(board));
    int user_rc = output("/system/bin/am get-current-user", user, sizeof(user));
    if (board_rc || strcmp(board, "spinel") || user_rc || strcmp(user, "0")) {
        logmsg("UNSUPPORTED_DEVICE_OR_USER board=%s board_rc=%d user=%s user_rc=%d", board, board_rc, user, user_rc); return 1;
    }
    if (disabled()) return 0;
    signal(SIGTERM, stop_signal); signal(SIGINT, stop_signal); signal(SIGHUP, stop_signal);
    int touch = open_input("NVTCapacitiveTouchScreen"), pen = open_input("NVTCapacitivePen");
    if (touch < 0 || pen < 0) { logmsg("INPUT_MISSING"); return 1; }
    int notify = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
    if (notify < 0 || inotify_add_watch(notify, module_dir, IN_CREATE | IN_MOVED_TO | IN_DELETE_SELF | IN_MOVE_SELF) < 0) { logmsg("MODULE_WATCH_FAILED"); return 1; }
    FILE *pid = fopen(pidpath, "we"); if (!pid) return 1;
    fprintf(pid, "%ld\n", (long)getpid()); fclose(pid);
    struct pollfd fds[] = {{touch, POLLIN, 0}, {pen, POLLIN, 0}, {notify, POLLIN, 0}};
    logmsg("READY version=%s idle=blocking active_check_ms=250 leave_ms=%d", VERSION, LEAVE_MS);
    int result = 0;
    if (screen_on() && read_int("/proc/fw_pen_state") == 1 && enter_vote("startup_pen_present")) result = 1;
    while (!result && !stopping && !disabled()) {
        int n = poll(fds, 3, active ? 250 : -1);
        if (n < 0) { if (errno == EINTR) continue; logmsg("POLL_FAILED errno=%d", errno); result = 1; break; }
        if (fds[2].revents) { char buf[4096]; while (read(notify, buf, sizeof(buf)) > 0) {} if (disabled() || access(module_dir, F_OK)) break; }
        if ((fds[0].revents & (POLLERR | POLLHUP)) || (fds[1].revents & (POLLERR | POLLHUP))) { logmsg("INPUT_POLL_FAILED touch=%d pen=%d", fds[0].revents, fds[1].revents); result = 1; break; }
        if ((fds[0].revents & POLLIN) && input_events(touch, true)) { result = 1; break; }
        if ((fds[1].revents & POLLIN) && input_events(pen, false)) { result = 1; break; }
        if (!active) continue;
        long long now = now_ms();
        if (!screen_on()) { if (restore("screen_off")) { result = 1; break; } continue; }
        int fw = read_int("/proc/fw_pen_state");
        if (fw < 0) { logmsg("FW_STATE_READ_FAILED"); result = 1; break; }
        if (fw == 1) last_fw_present = now;
        if (now - last_native_check >= 1000) {
            last_native_check = now;
            if (sync_native_policy()) { logmsg("NATIVE_POLICY_SYNC_FAILED"); result = 1; break; }
            if (!active) continue;
        }
        if (now - entered > ENTER_GRACE_MS && now - last_fw_present > LEAVE_MS && now - last_activity > LEAVE_MS) {
            if (restore("pen_left")) { result = 1; break; }
        }
    }
    if (active && restore("stop_or_error")) result = 1;
    unlink(pidpath); close(touch); close(pen); close(notify); close(lock);
    logmsg("STOP result=%d", result); return result;
}
