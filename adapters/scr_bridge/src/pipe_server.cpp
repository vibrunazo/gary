#include "pipe_server.h"

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <string>
#include <vector>

namespace garyscr {

void LineSplitter::feed(const char* data, size_t n, std::vector<std::string>* lines) {
    for (size_t i = 0; i < n; ++i) {
        if (data[i] == '\n') {
            if (!remainder_.empty() && remainder_.back() == '\r') remainder_.pop_back();
            lines->push_back(remainder_);
            remainder_.clear();
        } else {
            remainder_ += data[i];
        }
    }
}

bool pipe_serve(const std::wstring& pipe_name, const RequestHandler& handler,
                volatile bool* stop, std::string* error) {
    while (!*stop) {
        HANDLE pipe = CreateNamedPipeW(pipe_name.c_str(), PIPE_ACCESS_DUPLEX,
                                       PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                                       1, 1 << 16, 1 << 16, 0, nullptr);
        if (pipe == INVALID_HANDLE_VALUE) {
            *error = "CreateNamedPipeW failed";
            return false;
        }
        BOOL ok = ConnectNamedPipe(pipe, nullptr);
        if (!ok && GetLastError() != ERROR_PIPE_CONNECTED) {
            CloseHandle(pipe);
            continue;  // client vanished between create and connect; loop
        }
        LineSplitter splitter;
        std::string pending;
        char buf[4096];
        for (;;) {
            DWORD read_n = 0;
            BOOL r = ReadFile(pipe, buf, sizeof buf, &read_n, nullptr);
            if (!r || read_n == 0) break;  // client closed
            std::vector<std::string> lines;
            splitter.feed(buf, read_n, &lines);
            for (const std::string& line : lines) {
                if (line.empty()) continue;
                std::string response = handler(line);
                response += '\n';
                DWORD written = 0;
                if (!WriteFile(pipe, response.data(), (DWORD)response.size(), &written, nullptr))
                    break;
                FlushFileBuffers(pipe);
            }
        }
        DisconnectNamedPipe(pipe);
        CloseHandle(pipe);
    }
    return true;
}

}  // namespace garyscr
