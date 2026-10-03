// gary_scr: the in-process side of the SC:R adapter (adapters/scr_bridge/README.md).
//
// Shieldbattery's skeleton (verify-first init, hook-side vs pipe-side split) + Pluto's control
// path (commands into the game's own turn queue via send_command, JSONL packet log, fail-safe).
// Gary's contract is served over the named pipe to gary/scr_env.py.
//
// Nothing in the game is modified at all: a watcher thread polls the game's own frame counter
// (Game.frame_count) and treats each advance as a frame boundary, flushing queued commands there.

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <bcrypt.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "commands.h"
#include "handles.h"
#include "json_min.h"
#include "observe.h"
#include "pipe_server.h"
#include "scr_profile.h"

#pragma comment(lib, "bcrypt.lib")

namespace garyscr {
namespace {

struct Config {
    std::wstring pipe = L"\\\\.\\pipe\\gary_scr";
    std::wstring log_dir = L"logs";
    std::string expect_sha256 = profile::kExeSha256;
};

struct OutboxItem {
    uint32_t due_frame = 0;
    std::vector<uint8_t> packet;
};

Config g_config;
std::atomic<uint32_t> g_frames{0};
HANDLE g_frame_event = nullptr;       // signaled at every completed simulation frame
HANDLE g_command_log = INVALID_HANDLE_VALUE;
CRITICAL_SECTION g_outbox_lock;
std::vector<OutboxItem> g_outbox;
volatile bool g_stop = false;
volatile bool g_frame_source_ok = false;  // the watcher has seen the game's frame counter advance
bool g_verified = false;  // exe hash verified (the build identity pin)
std::string g_warning;

void log_line(const std::string& s) {
    if (g_command_log == INVALID_HANDLE_VALUE) return;
    std::string line = s + "\r\n";
    DWORD written = 0;
    WriteFile(g_command_log, line.data(), (DWORD)line.size(), &written, nullptr);
    FlushFileBuffers(g_command_log);
}

std::string hex_encode(const uint8_t* data, size_t n) {
    static const char* d = "0123456789abcdef";
    std::string r;
    r.reserve(n * 2);
    for (size_t i = 0; i < n; ++i) {
        r += d[data[i] >> 4];
        r += d[data[i] & 0xf];
    }
    return r;
}

bool hex_decode(const std::string& s, std::vector<uint8_t>* out) {
    if (s.size() % 2) return false;
    auto nib = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    };
    out->clear();
    for (size_t i = 0; i < s.size(); i += 2) {
        int hi = nib(s[i]), lo = nib(s[i + 1]);
        if (hi < 0 || lo < 0) return false;
        out->push_back((uint8_t)((hi << 4) | lo));
    }
    return true;
}

// SHA-256 of a file, via the Windows crypto API (no third-party code needed).
bool file_sha256(const wchar_t* path, std::string* out_hex) {
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE alg = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = false;
    std::vector<uint8_t> digest(32);
    if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0) == 0 &&
        BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0) == 0) {
        ok = true;
        char buf[1 << 16];
        DWORD read_n = 0;
        while (ReadFile(f, buf, sizeof buf, &read_n, nullptr) && read_n) {
            if (BCryptHashData(hash, (PUCHAR)buf, read_n, 0) != 0) {
                ok = false;
                break;
            }
        }
        if (ok && BCryptFinishHash(hash, digest.data(), (ULONG)digest.size(), 0) == 0) {
            *out_hex = hex_encode(digest.data(), digest.size());
        } else {
            ok = false;
        }
    }
    if (hash) BCryptDestroyHash(hash);
    if (alg) BCryptCloseAlgorithmProvider(alg, 0);
    CloseHandle(f);
    return ok;
}

std::string w_to_utf8(const std::wstring& w) {
    if (w.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string r(n, 0);
    WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &r[0], n, nullptr, nullptr);
    return r;
}

bool read_config(const std::wstring& path) {
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;  // defaults are fine
    char buf[4096];
    DWORD read_n = 0;
    ReadFile(f, buf, sizeof buf - 1, &read_n, nullptr);
    CloseHandle(f);
    buf[read_n] = 0;
    std::string text(buf);
    std::string s;
    if (json_get_string(text, "pipe", &s)) {
        g_config.pipe = std::wstring(s.begin(), s.end());
    }
    if (json_get_string(text, "log_dir", &s)) {
        g_config.log_dir = std::wstring(s.begin(), s.end());
    }
    json_get_string(text, "expect_sha256", &g_config.expect_sha256);
    return true;
}

uint32_t current_frame() {
    // The hook's own counter; observe() reports the game's Game.frame_count as ground truth.
    return g_frames.load();
}

}  // namespace

// --- command outbox ---------------------------------------------------------------------------

namespace {

// SEH needs a frame without C++ unwinding, so the guarded call is its own POD-only function.
bool send_packet_guarded(const uint8_t* data, size_t size) {
    bool submitted = false;
    __try {
        reinterpret_cast<void(__cdecl*)(const uint8_t*, size_t)>(
            (uintptr_t)GetModuleHandleW(nullptr) +
            (profile::kSendCommand - profile::kAnalyzedBase))(data, size);
        submitted = true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        submitted = false;
    }
    return submitted;
}

void drain_outbox(uint32_t frame) {
    std::vector<OutboxItem> due;
    EnterCriticalSection(&g_outbox_lock);
    for (auto it = g_outbox.begin(); it != g_outbox.end();) {
        if (it->due_frame <= frame) {
            due.push_back(std::move(*it));
            it = g_outbox.erase(it);
        } else {
            ++it;
        }
    }
    LeaveCriticalSection(&g_outbox_lock);
    for (const OutboxItem& item : due) {
        // The Pluto control path: hand the packet to the game's own turn queue. Any fault here
        // drops the command and logs it; the human's game is never crashed on purpose.
        bool submitted = send_packet_guarded(item.packet.data(), item.packet.size());
        char head[160];
        snprintf(head, sizeof head,
                 "{\"command_frame\":%u,\"queued_frame\":%u,\"packet_hex\":\"", frame,
                 item.due_frame);
        log_line(std::string(head) + hex_encode(item.packet.data(), item.packet.size()) +
                 "\",\"submitted\":" + (submitted ? "true" : "false") + "}");
    }
}

// --- frame source (watcher thread) ---------------------------------------------------------------
// The watcher polls Game.frame_count — the game's own frame counter — and treats every advance
// as one frame boundary. It patches NO game code at all and needs no call-site facts, so it
// cannot drift from the build the way a call-site hook can. (v0 hooked GetTickCount through the
// import table and the game's cached pointer; on this build neither engaged: the game imports no
// GetTickCount IAT slot and the cached pointer at kTimingTickPtr never became patchable — see
// README "Frame source". Commands never reached the game that way, so this replaced it.)

bool read_frame_guarded(uint32_t game, uint32_t* frame) {
    __try {
        *frame = *(const uint32_t*)(uintptr_t)(game + profile::kGameFrameCount);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

static DWORD WINAPI frame_watcher(LPVOID) {
    uint32_t last = 0;
    while (!g_stop) {
        World w;
        std::string err;
        uint32_t f = 0;
        if (world_read(&w, &err) && w.game && read_frame_guarded(w.game, &f) && f != last) {
            last = f;
            g_frame_source_ok = true;
            g_frames.store((int)f);
            if (g_frame_event) SetEvent(g_frame_event);
            drain_outbox(f);
        }
        Sleep(10);  // ~10ms granularity; one frame at Fastest is ~42ms
    }
    return 0;
}

bool start_frame_watcher() {
    log_line("{\"stage\":\"watcher\",\"frame_source\":\"game.frame_count\"}");
    HANDLE t = CreateThread(nullptr, 0, frame_watcher, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
    return true;
}


// --- request dispatch (pipe side) ---------------------------------------------------------------

std::string reply_ok(int64_t id, const std::string& result_json) {
    return "{\"id\":" + std::to_string(id) + ",\"ok\":true,\"result\":" + result_json + "}";
}

std::string reply_err(int64_t id, const std::string& error) {
    std::string e;
    for (char c : error) e += (c == '"' || c == '\\') ? '_' : c;
    return "{\"id\":" + std::to_string(id) + ",\"ok\":false,\"error\":\"" + e + "\"}";
}

std::string status_json() {
    World w;
    std::string err;
    bool resolved = world_read(&w, &err);
    std::string r = "{\"build\":\"" + std::string(profile::kBuildName) + "\"";
    r += ",\"hash_verified\":" + std::string(g_verified ? "true" : "false");
    r += ",\"frame_watcher\":" + std::string(g_frame_source_ok ? "true" : "false");
    r += ",\"frames\":" + std::to_string(g_frames.load());
    r += ",\"in_game\":" + std::string(resolved && w.in_game ? "true" : "false");
    if (resolved && w.in_game) {
        // The latency the game itself implies (calibration input; the adapter measures too).
        uint32_t table = (uint32_t)((uintptr_t)GetModuleHandleW(nullptr) +
                                    (profile::kGameTypeTable - profile::kAnalyzedBase));
        uint32_t turn_rate = *(uint32_t*)(table + 44);
        uint32_t user_delay = *(uint32_t*)(uintptr_t)((uintptr_t)GetModuleHandleW(nullptr) +
                                                      (profile::kUserDelay - profile::kAnalyzedBase));
        if (user_delay > 2) user_delay = 2;
        if (turn_rate < 8 || turn_rate > 24) turn_rate = 24;
        r += ",\"latency_frames\":" + std::to_string((24 * (2 + user_delay) + turn_rate - 1) / turn_rate);
        r += ",\"local_player\":" + std::to_string(w.local_player);
    }
    r += ",\"warning\":\"" + (g_warning.empty() ? (resolved ? w.warning : err) : g_warning) + "\"}";
    return r;
}

std::string dispatch(const std::string& line) {
    int64_t id = 0;
    json_get_int(line, "id", &id);
    std::string method;
    if (!json_get_string(line, "method", &method)) return reply_err(id, "missing method");
    std::string err;
    World w;

    if (method == "ping") return reply_ok(id, "\"pong\"");
    if (method == "status") return reply_ok(id, status_json());
    if (method == "shutdown") {
        g_stop = true;
        return reply_ok(id, "\"bye\"");
    }
    if (!g_verified) return reply_err(id, "build not verified; refusing: " + g_warning);

    if (method == "observe") {
        if (!world_read(&w, &err)) return reply_err(id, err);
        if (!w.in_game) return reply_err(id, "not in a game");
        std::string json;
        if (!observe_json(w, &json, &err)) return reply_err(id, err);
        return reply_ok(id, json);
    }
    if (method == "act") {
        int64_t slot = -1, dummy = 0;
        json_get_int(line, "slot", &slot);
        std::string hex;
        if (!json_get_string(line, "hex", &hex)) return reply_err(id, "missing hex");
        std::vector<uint8_t> legacy;
        if (!hex_decode(hex, &legacy)) return reply_err(id, "bad hex");
        if (!world_read(&w, &err)) return reply_err(id, err);
        if (!w.in_game) return reply_err(id, "not in a game");
        if (slot != (int64_t)w.local_player) return reply_ok(id, "0");  // only our own slot
        // legacy tags -> SC:R extended ids, resolved against live memory
        auto resolve = [&w](uint16_t tag) -> uint32_t {
            UnitView u;
            if (!unit_by_tag(w, tag, &u)) return 0;
            return scr_id_of(u.ref, w.unit_count);
        };
        std::vector<std::vector<uint8_t>> packets;
        if (!translate(legacy.data(), legacy.size(), resolve, &packets, &err))
            return reply_err(id, err);
        if (g_frame_source_ok) {
            EnterCriticalSection(&g_outbox_lock);
            for (auto& p : packets) g_outbox.push_back({current_frame() + 1, std::move(p)});
            LeaveCriticalSection(&g_outbox_lock);
        } else {
            // Degraded mode (hook not installed): submit immediately at request time and say so
            // in the log; turn-timing calibration is then unavailable (README "Known gaps").
            for (auto& p : packets) {
                bool submitted = send_packet_guarded(p.data(), p.size());
                log_line("{\"command_frame\":" + std::to_string(current_frame()) +
                         ",\"queued_frame\":-1,\"packet_hex\":\"" + hex_encode(p.data(), p.size()) +
                         "\",\"submitted\":" + (submitted ? "true" : "false") +
                         ",\"immediate\":true}");
            }
        }
        return reply_ok(id, "1");  // like gary_env_act: 1 = accepted into the queue
    }
    if (method == "step") {
        int64_t frames = 1;
        json_get_int(line, "frames", &frames);
        if (frames < 1) frames = 1;
        if (g_frame_source_ok) {
            uint32_t target = g_frames.load() + (uint32_t)frames;
            for (int waits = 0; g_frames.load() < target && waits < 12000; ++waits) {
                if (g_frame_event) WaitForSingleObject(g_frame_event, 10);
            }
        } else {
            // No hook: poll the game's own frame counter (observe reads it too).
            uint32_t start = 0, target = 0;
            for (int waits = 0; waits < 12000; ++waits) {
                World w;
                std::string werr;
                if (world_read(&w, &werr) && w.game) {
                    uint32_t frame;
                    memcpy(&frame, (const void*)(uintptr_t)(w.game + profile::kGameFrameCount), 4);
                    if (!start) {
                        start = frame;
                        target = frame + (uint32_t)frames;
                    } else if (frame >= target) {
                        break;
                    }
                }
                Sleep(10);
            }
        }
        return reply_ok(id, "{\"frame\":" + std::to_string(g_frames.load()) + "}");
    }
    if (method == "unit_at" || method == "box_select" || method == "unit_type" ||
        method == "can_place" || method == "depot_spot_ok" || method == "start_locations" ||
        method == "probe_unit") {
        if (!world_read(&w, &err)) return reply_err(id, err);
        if (!w.in_game) return reply_err(id, "not in a game");
        int64_t a = 0, b = 0, c = 0, d = 0, e2 = 0;
        if (method == "unit_at") {
            json_get_int(line, "slot", &a);
            json_get_int(line, "x", &b);
            json_get_int(line, "y", &c);
            return reply_ok(id, std::to_string(unit_at(w, (int)a, (int)b, (int)c)));
        }
        if (method == "box_select") {
            json_get_int(line, "slot", &a);
            json_get_int(line, "x0", &b);
            json_get_int(line, "y0", &c);
            json_get_int(line, "x1", &d);
            json_get_int(line, "y1", &e2);
            std::vector<uint16_t> tags = box_select(w, (int)a, (int)b, (int)c, (int)d, (int)e2);
            std::string r = "[";
            for (size_t i = 0; i < tags.size(); ++i) {
                if (i) r += ',';
                r += std::to_string(tags[i]);
            }
            return reply_ok(id, r + "]");
        }
        if (method == "unit_type") {
            json_get_int(line, "tag", &a);
            UnitView u;
            if (!unit_by_tag(w, (uint16_t)a, &u)) return reply_ok(id, "-1");
            return reply_ok(id, std::to_string(u.type));
        }
        if (method == "can_place") {
            json_get_int(line, "slot", &a);
            json_get_int(line, "builder", &b);
            json_get_int(line, "unit_type", &c);
            json_get_int(line, "tile_x", &d);
            json_get_int(line, "tile_y", &e2);
            return reply_ok(id, can_place(w, (int)a, (uint16_t)b, (int)c, (int)d, (int)e2) ? "1"
                                                                                          : "0");
        }
        if (method == "depot_spot_ok") {
            json_get_int(line, "tile_x", &a);
            json_get_int(line, "tile_y", &b);
            return reply_ok(id, depot_spot_ok(w, (int)a, (int)b) ? "1" : "0");
        }
        if (method == "start_locations") {
            std::string json;
            if (!start_locations_json(w, &json, &err)) return reply_err(id, err);
            return reply_ok(id, json);
        }
        std::string json;
        json_get_int(line, "tag", &a);
        if (!probe_unit_json(w, (uint16_t)a, &json, &err)) return reply_err(id, err);
        return reply_ok(id, json);
    }
    return reply_err(id, "unknown method: " + method);
}

// A dispatch call may touch live game memory; a bad read must degrade to an error reply, never
// take the pipe thread down (Shieldbattery's fail-safe rule). SEH needs a frame without C++
// unwinding, so the guarded call is its own POD-only function.
struct DispatchCtx {
    const std::string* line;
    std::string result;
};

void dispatch_thunk(void* ctx) {
    auto* c = (DispatchCtx*)ctx;
    c->result = dispatch(*c->line);
}

bool call_guarded(void (*fn)(void*), void* ctx) {
    bool ok = false;
    __try {
        fn(ctx);
        ok = true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    return ok;
}

std::string handle_request(const std::string& line) {
    DispatchCtx ctx{&line, {}};
    if (!call_guarded(dispatch_thunk, &ctx)) {
        return "{\"id\":0,\"ok\":false,\"error\":\"fault while reading game state (menu, or a "
               "profile mismatch); see logs/scr_bridge.log\"}";
    }
    return ctx.result;
}

}  // namespace

// --- init ---------------------------------------------------------------------------------------

DWORD WINAPI init_thread(LPVOID module) {
    wchar_t own[32768];
    GetModuleFileNameW((HMODULE)module, own, 32768);
    std::wstring dir(own);
    size_t slash = dir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) dir = dir.substr(0, slash);

    read_config(dir + L"\\gary_scr.json");
    std::wstring log_dir = g_config.log_dir;
    if (!log_dir.empty() && log_dir[0] != L'\\' && log_dir.find(L":") == std::wstring::npos)
        log_dir = dir + L"\\" + log_dir;
    CreateDirectoryW(log_dir.c_str(), nullptr);
    g_command_log = CreateFileW((log_dir + L"\\scr_bridge.log").c_str(), GENERIC_WRITE,
                                FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL,
                                nullptr);

    // Verify before trusting anything: the executable must be the pinned build.
    wchar_t exe[32768];
    GetModuleFileNameW(nullptr, exe, 32768);
    std::string hash;
    std::string expect = g_config.expect_sha256;
    for (char& c : expect) c = (char)tolower((unsigned char)c);
    bool hash_ok = file_sha256(exe, &hash) && hash == expect;
    start_frame_watcher();
    g_verified = hash_ok;  // the hash pin is the build identity; watcher state degrades, not blocks
    if (!hash_ok) {
        g_warning = "executable SHA-256 does not match the pinned build " +
                    std::string(profile::kBuildName);
        log_line("{\"stage\":\"verify\",\"hash\":\"" + hash + "\",\"expected\":\"" + expect +
                 "\",\"ok\":false}");
    }
    log_line("{\"stage\":\"ready\",\"verified\":" + std::string(g_verified ? "true" : "false") +
             ",\"pipe\":\"" + w_to_utf8(g_config.pipe) + "\"}");

    std::string err;
    pipe_serve(g_config.pipe, handle_request, &g_stop, &err);
    if (!err.empty()) log_line("{\"stage\":\"pipe\",\"error\":\"" + err + "\"}");
    log_line("{\"stage\":\"exit\"}");
    if (g_command_log != INVALID_HANDLE_VALUE) {
        CloseHandle(g_command_log);
        g_command_log = INVALID_HANDLE_VALUE;
    }
    return 0;
}

void bridge_attach(HINSTANCE module) {
    InitializeCriticalSection(&g_outbox_lock);
    g_frame_event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    HANDLE t = CreateThread(nullptr, 0, init_thread, module, 0, nullptr);
    if (t) CloseHandle(t);
}

}  // namespace garyscr

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        garyscr::bridge_attach(module);
    }
    return TRUE;
}

