// Test dispatch before asynchronous PreCache initialization.
#include <cerrno>
#include <cstdio>
#include <dlfcn.h>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    void* library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        std::fprintf(stderr, "%s\n", dlerror());
        return 2;
    }
    using OnTransact = int (*)(void*, unsigned, const void*, void*, unsigned);
    auto transact = reinterpret_cast<OnTransact>(dlsym(
        library, "_ZN7android17GpuServiceExtImpl10onTransactEjRKNS_6ParcelEPS1_j"));
    if (!transact) return 2;
    alignas(16) unsigned char uninitialized_service[0x90]{};
    const unsigned precache[] = {0xbb9, 0xbba, 0xbbb, 0xbc5, 0xbc6, 0xbc7};
    const unsigned other[] = {0, 0xbb8, 0xbbc, 0xbc4, 0xbc8, 0xfa1, 0xffffffff};
    for (unsigned code : precache) {
        const int result = transact(uninitialized_service, code, nullptr, nullptr, 0);
        std::printf("%04x -> %d\n", code, result);
        if (result != -ENODEV) return 1;
    }
    for (unsigned code : other) {
        const int result = transact(uninitialized_service, code, nullptr, nullptr, 0);
        std::printf("%04x -> %d\n", code, result);
        if (result != 0) return 1;
    }
}
