// Diagnostic for this ROM's arm64 libvintf, outside the Java JNI wrapper.
// NDK r27d libc++ uses the same default string and shared_ptr object layouts.
#include <cstdio>
#include <dlfcn.h>
#include <memory>
#include <string>

int main() {
    auto* lib = dlopen("/system/lib64/libvintf.so", RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        std::fprintf(stderr, "%s\n", dlerror());
        return 2;
    }

    using GetInstance = std::shared_ptr<void> (*)();
    using Check = int (*)(void*, std::string*, int);
    auto get_instance = reinterpret_cast<GetInstance>(dlsym(
        lib, "_ZN7android5vintf11VintfObject11GetInstanceEv"));
    auto check = reinterpret_cast<Check>(dlsym(
        lib, "_ZN7android5vintf11VintfObject18checkCompatibility"
             "EPNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEE"
             "ENS0_10CheckFlags4TypeE"));
    if (!get_instance || !check) {
        std::fprintf(stderr, "Expected libvintf symbols not found\n");
        return 2;
    }

    auto vintf = get_instance();
    if (!vintf) return 2;
    std::string error;
    int status = check(vintf.get(), &error, ~1);
    std::printf("compatibility_status=%d\n%s\n", status, error.c_str());
    error.clear();
    status = check(vintf.get(), &error, 0);
    std::printf("manifest_only_status=%d\n%s\n", status, error.c_str());
}
