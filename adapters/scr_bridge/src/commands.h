#pragma once
// Legacy (pre-1.21 / replay-format) command records -> Remastered 1.21+ command records.
// Gary emits legacy bytes (gary/commands.py); the SC:R turn queue wants the 1.21 variants of
// six commands with 32-bit unit ids (resim/gary_resim.cpp translates the reverse direction and
// is the tested reference; external/screp/rep/repcmd/types.go names both families).
//
// Legacy record lengths come from the replay format (screp's repparser, gary/commands.py). A
// record with an unknown id is an error: we reject instead of guessing, so a command can never
// be misparsed and corrupt the stream.

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace garyscr {

// Length in bytes of one legacy command record at p (only the first byte is the id; n is the
// number of bytes available). Returns false on truncation or unknown/unsupported id.
bool legacy_record_length(const uint8_t* p, size_t n, size_t* out_len);

// Translate one legacy record (exactly one command) into zero or more 1.21 records.
// `resolve_tag` maps a legacy unit tag to the SC:R extended unit id; returning 0 means the
// handle is stale and the command is rejected (error set). Returns false and fills `error` on
// any problem; on success `out` receives the full 1.21 records, ready for send_command().
bool translate_one(const uint8_t* p, size_t n,
                   const std::function<uint32_t(uint16_t)>& resolve_tag,
                   std::vector<std::vector<uint8_t>>* out, std::string* error);

// Translate a buffer that may hold several concatenated legacy records.
bool translate(const uint8_t* data, size_t n,
               const std::function<uint32_t(uint16_t)>& resolve_tag,
               std::vector<std::vector<uint8_t>>* out, std::string* error);

}  // namespace garyscr
