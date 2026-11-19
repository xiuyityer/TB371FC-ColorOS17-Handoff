#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <string.h>

struct str_parms;
typedef int (*get_int_fn)(struct str_parms*, const char*, int*);
static pthread_once_t init = PTHREAD_ONCE_INIT;
static get_int_fn real_get_int;

static void resolve(void) {
    // On C17 vendor uses libcutils from the linked VNDK namespace.
    void* libcutils = dlopen("libcutils.so", RTLD_NOW | RTLD_LOCAL);
    if (libcutils) real_get_int = (get_int_fn)dlsym(libcutils, "str_parms_get_int");
}

// Retain the vendor-specific parameter. Only use Android's standard key when
// the Lenovo key is absent; the HAL still owns all route and call-mode checks.
int str_parms_get_int(struct str_parms* params, const char* key, int* value) {
    pthread_once(&init, resolve);
    if (!real_get_int) return -ENOSYS;
    int result = real_get_int(params, key, value);
    if (result != -ENOENT || strcmp(key, "gsensor_rotation") != 0) return result;
    int standard_rotation;
    int fallback = real_get_int(params, "rotation", &standard_rotation);
    if (fallback < 0 || standard_rotation < 0 || standard_rotation >= 360 ||
        standard_rotation % 90 != 0) return result;
    *value = standard_rotation;
    return fallback;
}
