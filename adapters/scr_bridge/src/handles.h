#pragma once
// Unit handles: Gary's 16-bit tags and SC:R's extended unit ids are the SAME encoding — the
// game's own command-stream unit id — so gary/commands.py's <H> fields work unchanged and the
// translation to 1.21 packets is an identity on unit references.
//
// classic 1700-unit table (resim/gary_resim.cpp: "unit_limit <= 1700: ids unchanged"):
//     handle = (vector_index + 1) | ((generation % 32) << 11)      11-bit index, 5-bit generation
//     ... which is exactly the OpenBW unit_id layout gary_env emits as "tag".
// 3400-unit tables (LMTS; recent ladder games):
//     handle = (vector_index + 1) | ((generation % 8) << 13)       13-bit index, 3-bit generation
// The generation modulo keeps the id inside the 1.21 wire format (u16 id + a zero u16).
//
// A handle is stale when its generation no longer matches the unit at that vector slot (or the
// slot is dead): resolve fails then, exactly like gary_env_unit_type returning -1 and OpenBW's
// get_unit missing. Commands referencing stale handles are rejected before reaching the engine.

#include <cstdint>

#include "scr_profile.h"

namespace garyscr {

struct UnitRef {
    uint32_t ptr = 0;        // absolute address of the unit struct, 0 = none
    uint32_t index1 = 0;     // vector index + 1
    uint8_t generation = 0;  // unit struct generation counter (minor_unique_index)
};

inline uint16_t unit_handle(const UnitRef& u, uint32_t unit_count) {
    if (!u.ptr) return 0;
    if (unit_count > profile::kClassicUnitLimit) {
        return (uint16_t)((u.index1 & 0x1fff) | ((uint32_t)(u.generation % 8) << 13));
    }
    return (uint16_t)((u.index1 & 0x7ff) | ((uint32_t)(u.generation % 32) << 11));
}

// Gary's tag and the SC:R command id are one and the same.
inline uint16_t tag_of(const UnitRef& u, uint32_t unit_count) {
    return unit_handle(u, unit_count);
}

inline uint32_t scr_id_of(const UnitRef& u, uint32_t unit_count) {
    return unit_handle(u, unit_count);
}

inline bool handle_split(uint16_t handle, uint32_t unit_count, uint32_t* index1, uint8_t* gen) {
    if (!handle) return false;
    if (unit_count > profile::kClassicUnitLimit) {
        *index1 = handle & 0x1fff;
        *gen = (uint8_t)(handle >> 13);
    } else {
        *index1 = handle & 0x7ff;
        *gen = (uint8_t)(handle >> 11);
    }
    return *index1 != 0;
}

}  // namespace garyscr
