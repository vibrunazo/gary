#pragma once
// Minimal JSON helpers for the adapter's own messages: one flat object per line, string values
// with only \" \\ and \n escapes, integer values. That is the whole grammar both sides emit
// (gary/scr_env.py builds the same shape); anything else is rejected, never guessed at.

#include <cstdint>
#include <string>

namespace garyscr {

inline bool json_get_string(const std::string& line, const char* key, std::string* out) {
    std::string pat = std::string("\"") + key + "\":";
    size_t at = line.find(pat);
    if (at == std::string::npos) return false;
    at += pat.size();
    while (at < line.size() && (line[at] == ' ' || line[at] == '\t')) ++at;
    if (at >= line.size() || line[at] != '"') return false;
    ++at;
    std::string r;
    for (size_t i = at; i < line.size(); ++i) {
        char c = line[i];
        if (c == '\\') {
            if (i + 1 >= line.size()) return false;
            char n = line[++i];
            r += (n == 'n') ? '\n' : n;
        } else if (c == '"') {
            *out = r;
            return true;
        } else {
            r += c;
        }
    }
    return false;
}

inline bool json_get_int(const std::string& line, const char* key, int64_t* out) {
    std::string pat = std::string("\"") + key + "\":";
    size_t at = line.find(pat);
    if (at == std::string::npos) return false;
    at += pat.size();
    while (at < line.size() && (line[at] == ' ' || line[at] == '\t')) ++at;
    size_t i = at;
    bool neg = false;
    if (i < line.size() && line[i] == '-') {
        neg = true;
        ++i;
    }
    int64_t v = 0;
    bool any = false;
    for (; i < line.size() && line[i] >= '0' && line[i] <= '9'; ++i) {
        v = v * 10 + (line[i] - '0');
        any = true;
    }
    if (!any) return false;
    *out = neg ? -v : v;
    return true;
}

}  // namespace garyscr
