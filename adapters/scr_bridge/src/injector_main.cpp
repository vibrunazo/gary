// scr_inject: launch StarCraft (x86) and load gary_scr.dll into it (or attach to a running
// process). Kept as its own 32-bit exe because the remote LoadLibraryW must be the 32-bit one;
// a 64-bit Python cannot create that thread (adapters/scr_bridge/README.md).
//
// Usage:
//   scr_inject.exe <starcraft_exe> <gary_scr_dll> [workdir]   start suspended, inject, resume
//   scr_inject.exe attach <pid> <gary_scr_dll>                inject into a running process
// Prints "pid <N>" on success; nonzero exit on failure.

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <cstdio>
#include <string>

namespace {

bool inject(HANDLE process, const wchar_t* dll_path) {
    size_t bytes = (wcslen(dll_path) + 1) * sizeof(wchar_t);
    void* remote = VirtualAllocEx(process, nullptr, bytes, MEM_COMMIT | MEM_RESERVE,
                                  PAGE_READWRITE);
    if (!remote) return false;
    if (!WriteProcessMemory(process, remote, dll_path, bytes, nullptr)) return false;
    HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    auto load_library = (LPTHREAD_START_ROUTINE)GetProcAddress(kernel32, "LoadLibraryW");
    if (!load_library) return false;
    HANDLE thread =
        CreateRemoteThread(process, nullptr, 0, load_library, remote, 0, nullptr);
    if (!thread) return false;
    WaitForSingleObject(thread, 15000);
    DWORD code = 0;
    GetExitCodeThread(thread, &code);
    CloseHandle(thread);
    VirtualFreeEx(process, remote, 0, MEM_RELEASE);
    return code != 0;  // LoadLibraryW returns the module handle
}

int fail(const char* what) {
    printf("error: %s (win32 %lu)\n", what, GetLastError());
    return 1;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc >= 4 && wcscmp(argv[1], L"attach") == 0) {
        DWORD pid = (DWORD)_wtoi(argv[2]);
        HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION |
                                         PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
                                     FALSE, pid);
        if (!process) return fail("OpenProcess");
        bool ok = inject(process, argv[3]);
        CloseHandle(process);
        if (!ok) return fail("inject");
        printf("pid %lu\n", pid);
        return 0;
    }
    if (argc < 3) {
        printf("usage: scr_inject.exe <starcraft_exe> <gary_scr_dll> [workdir] [args...]\n");
        return 2;
    }
    const wchar_t* exe = argv[1];
    const wchar_t* dll = argv[2];
    const wchar_t* workdir = argc > 3 ? argv[3] : nullptr;

    STARTUPINFOW si{};
    si.cb = sizeof si;
    PROCESS_INFORMATION pi{};
    std::wstring cmd = std::wstring(L"\"") + exe + L"\"";
    for (int i = 4; i < argc; ++i) {  // e.g. -launch: SC:R exits immediately without it
        cmd += L" ";
        cmd += argv[i];
    }
    if (!CreateProcessW(exe, &cmd[0], nullptr, nullptr, FALSE, CREATE_SUSPENDED, nullptr,
                        workdir, &si, &pi))
        return fail("CreateProcessW");
    bool ok = inject(pi.hProcess, dll);
    if (!ok) {
        TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return fail("inject");
    }
    ResumeThread(pi.hThread);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    printf("pid %lu\n", pi.dwProcessId);
    return 0;
}
