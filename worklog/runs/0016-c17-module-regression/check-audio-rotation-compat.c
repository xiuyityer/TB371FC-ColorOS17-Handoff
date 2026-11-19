#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>

struct str_parms;
int main(void) {
    void* cutils = dlopen("libcutils.so", RTLD_NOW | RTLD_GLOBAL);
    if (!cutils) return 2;
    struct str_parms* (*create)(const char*) = dlsym(cutils, "str_parms_create_str");
    void (*destroy)(struct str_parms*) = dlsym(cutils, "str_parms_destroy");
    int (*read_value)(struct str_parms*, const char*, int*) = dlsym(RTLD_DEFAULT, "str_parms_get_int");
    if (!create || !destroy || !read_value) return 2;
    Dl_info info;
    if (!dladdr((void*)create, &info)) return 2;
    printf("cutils=%s\n", info.dli_fname);
    const struct {
        const char* params;
        const char* key;
        int value;
        int should_find;
    } cases[] = {
        {"rotation=0", "gsensor_rotation", 0, 1},
        {"rotation=90", "gsensor_rotation", 90, 1},
        {"rotation=180", "gsensor_rotation", 180, 1},
        {"rotation=270", "gsensor_rotation", 270, 1},
        {"rotation=270;gsensor_rotation=90", "gsensor_rotation", 90, 1},
        {"rotation=91", "gsensor_rotation", 0, 0},
        {"rotation=360", "gsensor_rotation", 0, 0},
        {"rotation=nan", "gsensor_rotation", 0, 0},
        {"screen_state=1", "gsensor_rotation", 0, 0},
        {"rotation=270", "other", 0, 0},
        {"rotation=270", "rotation", 270, 1},
    };
    int failed = 0;
    for (size_t i = 0; i < sizeof(cases)/sizeof(*cases); ++i) {
        struct str_parms* params = create(cases[i].params);
        if (!params) return 2;
        int value = -999;
        int rc = read_value(params, cases[i].key, &value);
        destroy(params);
        int matched = cases[i].should_find ? rc >= 0 && value == cases[i].value
                                        : rc == -ENOENT && value == -999;
        printf("%s, %s -> rc=%d val=%d %s\n", cases[i].params, cases[i].key, rc, value,
               matched ? "PASS" : "FAIL");
        failed |= !matched;
    }
    return failed;
}
