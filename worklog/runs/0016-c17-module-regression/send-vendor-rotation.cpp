#include <cstdio>
#include <cstring>
#include <dlfcn.h>

// Match the platform's String8 ABI. Its buffer is managed by libutils.
struct String8 { char* value; };

int main(int argc, char** argv) {
    if (argc != 2 ||
        (strcmp(argv[1], "0") && strcmp(argv[1], "90") &&
         strcmp(argv[1], "180") && strcmp(argv[1], "270"))) {
        std::fprintf(stderr, "Expected 0, 90, 180, or 270\n");
        return 2;
    }
    auto* utils = dlopen("/system/lib64/libutils.so", RTLD_NOW | RTLD_LOCAL);
    auto* audio = dlopen("/system/lib64/libaudiobase.so", RTLD_NOW | RTLD_LOCAL);
    if (!utils || !audio) return 2;
    using NewString = void (*)(String8*, const char*);
    using DropString = void (*)(String8*);
    using SetParameters = int (*)(const String8*);
    auto construct = reinterpret_cast<NewString>(dlsym(utils, "_ZN7android7String8C1EPKc"));
    auto destroy = reinterpret_cast<DropString>(dlsym(utils, "_ZN7android7String8D1Ev"));
    auto set = reinterpret_cast<SetParameters>(dlsym(audio, "_ZN7android11AudioSystem13setParametersERKNS_7String8E"));
    if (!construct || !destroy || !set) return 2;
    char parameter[32];
    std::snprintf(parameter, sizeof(parameter), "gsensor_rotation=%s", argv[1]);
    String8 value{};
    construct(&value, parameter);
    int status = set(&value);
    destroy(&value);
    std::printf("%s status=%d\n", parameter, status);
    return status != 0;
}
