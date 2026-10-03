#include "observe.h"

#include <Windows.h>

#include <cstdio>
#include <cstring>
#include <set>
#include <string>

#include "scr_profile.h"
#include "unit_dat.h"

namespace garyscr {

// --- raw reads ----------------------------------------------------------------------------------

template <typename T>
T read(uintptr_t addr) {
    T v;
    memcpy(&v, reinterpret_cast<const void*>(addr), sizeof v);
    return v;
}

// The game's memory speaks 32-bit addresses (x86 client).
template <typename T>
T read_at(uint32_t game_addr) {
    return read<T>((uintptr_t)game_addr);
}

uint32_t read_ptr(uint32_t game_addr) { return read_at<uint32_t>(game_addr); }

uint32_t game_ptr(uintptr_t module_base, uint32_t va) {
    return read<uint32_t>(module_base + (va - profile::kAnalyzedBase));
}

// --- world and units ----------------------------------------------------------------------------

bool world_read(World* w, std::string* error) {
    *w = World{};
    w->module_base = (uintptr_t)GetModuleHandleW(nullptr);
    // SC:R scrambles a few globals; the de-scrambling is part of this build's facts [PL].
    w->game = game_ptr(w->module_base, profile::kGameXorPtr) ^ profile::kGameXorConst;
    uint32_t sub = game_ptr(w->module_base, profile::kPlayersSubPtr);
    uint32_t x = game_ptr(w->module_base, profile::kPlayersXorPtr);
    w->players = (profile::kPlayersConst - sub) ^ x;
    w->units_base = game_ptr(w->module_base, profile::kUnitsBase);
    w->unit_count = game_ptr(w->module_base, profile::kUnitCount);
    w->local_player = game_ptr(w->module_base, profile::kLocalPlayerId);
    if (!w->game || !w->players || !w->units_base) {
        *error = "game globals did not resolve (menu, or wrong build)";
        return false;
    }
    if (w->unit_count > 4096) {
        *error = "unit vector length implausible; profile mismatch";
        return false;
    }
    int mw = read_at<uint16_t>(w->game + profile::kGameMapWidthTiles);
    int mh = read_at<uint16_t>(w->game + profile::kGameMapHeightTiles);
    w->in_game = mw >= 1 && mw <= 256 && mh >= 1 && mh <= 256 && w->local_player < 8;
    return true;
}

// Read one unit struct into a view; false if the slot is dead (no sprite) or the type field is
// implausible (the liveness sanity check the reference implementations use).
bool unit_view(uint32_t ptr, UnitView* u) {
    if (!ptr) return false;
    u->ref.ptr = ptr;
    u->ref.index1 = ptr / profile::kUnitSize + 1;  // fixed up by callers that know the base
    u->sprite = (int)read_ptr(ptr + profile::kUnitSprite);
    if (!u->sprite) return false;
    u->type = read_at<uint16_t>(ptr + profile::kUnitTypeId);
    if (u->type >= 228) return false;
    u->ref.generation = read_at<uint8_t>(ptr + profile::kUnitGenIndex);
    u->owner = read_at<uint8_t>(ptr + profile::kUnitPlayer);
    u->order = read_at<uint8_t>(ptr + profile::kUnitOrder);
    u->flags = read_at<uint32_t>(ptr + profile::kUnitFlags);
    u->completed = (u->flags & profile::kStatusCompleted) != 0;
    u->hp = (int)read_at<uint32_t>(ptr + profile::kUnitHp) >> 8;
    u->shields = (int)read_at<uint32_t>(ptr + profile::kUnitShields) >> 8;
    u->x = read_at<uint16_t>(ptr + profile::kUnitPosition);
    u->y = read_at<uint16_t>(ptr + profile::kUnitPosition + 2);
    uint32_t sprite = (uint32_t)u->sprite;
    u->visible_to = read_at<uint8_t>(sprite + profile::kSpriteVisibility);
    u->elevation = read_at<uint8_t>(sprite + profile::kSpriteElevation);
    u->resources = read_at<uint16_t>(ptr + profile::kUnitResources);
    // queue: entries from the ring start; an empty slot holds 228 ("no unit" type id), the same
    // test snapshot.cpp uses when it rebuilds BWAPI training queues.
    u->raw_build_slot = read_at<uint8_t>(ptr + profile::kUnitBuildSlot) % 5;
    u->queue = 0;
    for (unsigned n = 0; n < 5; ++n) {
        uint16_t q =
            read_at<uint16_t>(ptr + profile::kUnitBuildQueue + ((u->raw_build_slot + n) % 5) * 2);
        u->raw_queue[n] = q;
        if (q < 228) ++u->queue;
        else break;
    }
    u->raw_shields = read_at<uint32_t>(ptr + profile::kUnitShields);
    u->raw_energy = read_at<uint16_t>(ptr + profile::kUnitEnergy);
    u->raw_resources = read_at<uint16_t>(ptr + profile::kUnitResources);
    u->raw_type_at_36 = read_at<uint16_t>(ptr + 36);
    // A raw window over the worker/building union so the probe can locate fields like the
    // shields offset when an offset is still unverified (README verification step 3).
    memcpy(u->raw_window, (const void*)(uintptr_t)(ptr + profile::kProbeWindowStart),
           sizeof u->raw_window);
    return true;
}

bool walk_list(uint32_t first, std::set<uint32_t>* seen, std::vector<UnitView>* out,
               std::string* error) {
    // `first` is the first unit's address (already resolved from the head variable).
    for (uint32_t ptr = first; ptr; ptr = read_ptr(ptr + profile::kUnitNext)) {
        if (!seen->insert(ptr).second) {
            *error = "unit list cycle; refusing to continue";
            return false;
        }
        if (seen->size() > 20000) {
            *error = "unit list implausibly long; profile mismatch";
            return false;
        }
        UnitView u;
        if (unit_view(ptr, &u)) out->push_back(u);
    }
    return true;
}

bool units_collect(const World& w, std::vector<UnitView>* out, std::string* error) {
    out->clear();
    std::set<uint32_t> seen;
    // List heads are profile VAs: relocate them against the loaded module (the fact convention
    // addr = module + va - analyzed_base), same as world_read does for the globals.
    if (!walk_list(game_ptr(w.module_base, profile::kFirstActiveUnit), &seen, out, error))
        return false;
    if (!walk_list(game_ptr(w.module_base, profile::kFirstHiddenUnit), &seen, out, error))
        return false;
    for (auto& u : *out) {  // index1 now known relative to the unit vector base
        u.ref.index1 = (u.ref.ptr - w.units_base) / profile::kUnitSize + 1;
    }
    return true;
}

bool unit_by_tag(const World& w, uint16_t tag, UnitView* out) {
    uint32_t index1;
    uint8_t gen;
    if (!handle_split(tag, w.unit_count, &index1, &gen)) return false;
    if (!w.unit_count || index1 > w.unit_count) return false;
    uint32_t ptr = w.units_base + (index1 - 1) * profile::kUnitSize;
    if ((ptr - w.units_base) % profile::kUnitSize) return false;
    if (!unit_view(ptr, out)) return false;
    out->ref.index1 = index1;
    uint8_t mask = w.unit_count > profile::kClassicUnitLimit ? 8 : 32;
    return (uint8_t)(out->ref.generation % mask) == gen;
}

std::string json_escape(const char* s) {
    std::string r;
    for (const unsigned char* p = (const unsigned char*)s; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            r += '\\';
            r += (char)*p;
        } else if (*p < 0x20) {
            char buf[8];
            snprintf(buf, sizeof buf, "\\u%04x", *p);
            r += buf;
        } else {
            r += (char)*p;
        }
    }
    return r;
}

// Gary's observe() JSON — the schema of gary_env_observe (env/gary_env.cpp) exactly.
bool observe_json(const World& w, std::string* out, std::string* error) {
    std::vector<UnitView> units;
    if (!units_collect(w, &units, error)) return false;
    std::string& o = *out;
    o = "{\"frame\":" + std::to_string(read_at<uint32_t>(w.game + profile::kGameFrameCount));
    o += ",\"map\":{\"w\":" +
         std::to_string(read_at<uint16_t>(w.game + profile::kGameMapWidthTiles) * 32) +
         ",\"h\":" + std::to_string(read_at<uint16_t>(w.game + profile::kGameMapHeightTiles) * 32) +
         "},";
    o += "\"players\":[";
    bool first = true;
    for (int p = 0; p != 8; ++p) {
        uint32_t pl = w.players + (uint32_t)p * profile::kPlayerSize;
        uint8_t ptype = read_at<uint8_t>(pl + profile::kPlayerType);
        if (ptype != 1 && ptype != 2) continue;  // occupied slot: human or computer (probe check)
        if (!first) o += ',';
        first = false;
        int race = read_at<uint8_t>(pl + profile::kPlayerRace);
        int ri = (race >= 0 && race < 3) ? race : 0;
        uint32_t supplies =
            w.game + profile::kGameSupplies + (uint32_t)ri * profile::kSuppliesSize;
        uint32_t used = read_at<uint32_t>(supplies + profile::kSuppliesUsed + p * 4);
        // gary_env's "supply_max" is the supply *available* from depots (the provided array);
        // the max array is the 200-cap. (env/gary_env.cpp: supply_available -> supply_max.)
        uint32_t provided = read_at<uint32_t>(supplies + profile::kSuppliesProvided + p * 4);
        char name[28];
        memcpy(name, (const void*)(uintptr_t)(pl + profile::kPlayerName), 25);
        name[25] = 0;
        char buf[320];
        snprintf(buf, sizeof buf,
                 "{\"slot\":%d,\"name\":\"%s\",\"race\":%d,\"minerals\":%d,\"gas\":%d,"
                 "\"supply_used\":%g,\"supply_max\":%g,\"victory_state\":%d}",
                 p, json_escape(name).c_str(), race,
                 read_at<int32_t>(w.game + profile::kGameMinerals + p * 4),
                 read_at<int32_t>(w.game + profile::kGameGas + p * 4), used / 2.0, provided / 2.0,
                 (int)read_at<uint8_t>(w.game + profile::kGameVictoryState + p));
        o += buf;
    }
    o += "],\"units\":[";
    first = true;
    for (const UnitView& u : units) {
        if (!first) o += ',';
        first = false;
        char buf[320];
        snprintf(buf, sizeof buf,
                 "{\"tag\":%u,\"owner\":%d,\"type\":%d,\"x\":%d,\"y\":%d,\"hp\":%d,"
                 "\"shields\":%d,\"completed\":%d,\"visible_to\":%d,\"order\":%d,"
                 "\"resources\":%d,\"queue\":%d}",
                 (unsigned)tag_of(u.ref, w.unit_count), (int)u.owner, (int)u.type, u.x, u.y, u.hp, u.shields,
                 u.completed ? 1 : 0, (int)u.visible_to, (int)u.order, u.resources, u.queue);
        o += buf;
    }
    o += "]}";
    return true;
}

bool probe_unit_json(const World& w, uint16_t tag, std::string* out, std::string* error) {
    UnitView u;
    if (!unit_by_tag(w, tag, &u)) {
        *error = "no live unit for that tag";
        return false;
    }
    char buf[1300];
    char window[400];
    size_t at = 0;
    for (unsigned i = 0; i < sizeof u.raw_window && at + 2 < sizeof window; ++i)
        at += (size_t)snprintf(window + at, sizeof window - at, "%02x", u.raw_window[i]);
    snprintf(buf, sizeof buf,
             "{\"tag\":%u,\"type\":%u,\"type_at_36\":%u,\"owner\":%u,\"hp\":%d,"
             "\"raw_shields\":%u,\"raw_energy\":%u,\"raw_resources\":%u,"
             "\"raw_build_slot\":%u,\"raw_queue\":[%u,%u,%u,%u,%u],"
             "\"raw_flags\":%u,\"gen\":%u,\"x\":%d,\"y\":%d,"
             "\"window_start\":%u,\"window_hex\":\"%s\"}",
             (unsigned)tag, (unsigned)u.type, (unsigned)u.raw_type_at_36, (unsigned)u.owner, u.hp,
             (unsigned)u.raw_shields, (unsigned)u.raw_energy, (unsigned)u.raw_resources,
             (unsigned)u.raw_build_slot, (unsigned)u.raw_queue[0], (unsigned)u.raw_queue[1],
             (unsigned)u.raw_queue[2], (unsigned)u.raw_queue[3], (unsigned)u.raw_queue[4],
             (unsigned)u.flags, (unsigned)u.ref.generation, u.x, u.y,
             (unsigned)profile::kProbeWindowStart, window);
    *out = buf;
    return true;
}

// --- click model (v1: sprite bbox + draw depth; see README "Known gaps") ------------------------

// Unit types the click model refuses to select (env/gary_env.cpp's list; ids from
// external/openbw/bwenums.h, same numbering as gary/commands.py).
constexpr uint16_t kTypeNuclearMissile = 14;
constexpr uint16_t kTypeScarab = 85;
constexpr uint16_t kTypeDisruptionWeb = 105;
constexpr uint16_t kTypeDarkSwarm = 202;

bool selectable_type(uint16_t type) {
    return type != kTypeNuclearMissile && type != kTypeScarab && type != kTypeDisruptionWeb &&
           type != kTypeDarkSwarm;
}

bool seen_by(const UnitView& u, int slot) {
    return u.owner == slot || (u.visible_to & (1u << slot)) != 0;
}

bool is_building(const UnitView& u) { return (u.flags & profile::kStatusGroundedBuilding) != 0; }

bool clickable_rect(const World& w, const UnitView& u, int* x0, int* y0, int* x1, int* y1) {
    (void)w;
    uint32_t sprite = (uint32_t)u.sprite;
    int bw = read_at<uint8_t>(sprite + profile::kSpriteWidth);
    int bh = read_at<uint8_t>(sprite + profile::kSpriteHeight);
    if (bw <= 0 || bh <= 0) return false;
    *x0 = u.x - bw / 2;
    *y0 = u.y - bh / 2;
    *x1 = *x0 + bw;
    *y1 = *y0 + bh;
    return true;
}

uint32_t draw_depth(const UnitView& u) {
    return ((uint32_t)u.elevation << 14) | (uint32_t)(u.elevation <= 4 ? u.y : 0);
}

int footprint(const World& w, const UnitView& u) {
    (void)w;
    uint32_t sprite = (uint32_t)u.sprite;
    return (int)read_at<uint8_t>(sprite + profile::kSpriteWidth) *
           (int)read_at<uint8_t>(sprite + profile::kSpriteHeight);
}

uint16_t unit_at(const World& w, int slot, int x, int y) {
    std::vector<UnitView> units;
    std::string err;
    if (!units_collect(w, &units, &err)) return 0;
    const UnitView* best = nullptr;
    for (const UnitView& u : units) {
        if (!seen_by(u, slot) || !selectable_type(u.type)) continue;
        int x0, y0, x1, y1;
        if (!clickable_rect(w, u, &x0, &y0, &x1, &y1)) continue;
        if (x < x0 || y < y0 || x >= x1 || y >= y1) continue;
        if (!best || draw_depth(u) > draw_depth(*best) ||
            (draw_depth(u) == draw_depth(*best) && footprint(w, u) < footprint(w, *best)))
            best = &u;
    }
    return best ? tag_of(best->ref, w.unit_count) : 0;
}

std::vector<uint16_t> box_select(const World& w, int slot, int x0, int y0, int x1, int y1) {
    std::vector<UnitView> units;
    std::string err;
    std::vector<uint16_t> out;
    if (!units_collect(w, &units, &err)) return out;
    if (x0 > x1) std::swap(x0, x1);
    if (y0 > y1) std::swap(y0, y1);
    std::vector<const UnitView*> mobile, buildings;
    for (const UnitView& u : units) {
        if (u.owner != slot || !selectable_type(u.type)) continue;
        int rx0, ry0, rx1, ry1;
        if (!clickable_rect(w, u, &rx0, &ry0, &rx1, &ry1)) continue;
        if (rx1 <= x0 || ry1 <= y0 || rx0 > x1 || ry0 > y1) continue;
        (is_building(u) ? buildings : mobile).push_back(&u);
    }
    // mobile units before buildings; a lone building may be selected alone (gary_env_box_select)
    std::vector<const UnitView*> chosen = mobile;
    if (chosen.empty() && !buildings.empty()) chosen.push_back(buildings.front());
    for (const UnitView* u : chosen) {
        if (out.size() == 12) break;
        out.push_back(tag_of(u->ref, w.unit_count));
    }
    return out;
}

// --- placement and map knowledge ----------------------------------------------------------------

// "Buildable" test on the game's per-tile flags array. The bit value is UNVERIFIED: the live
// probe checks it against the game's own green/red grid (README verification step 3).
constexpr uint16_t kTileUnbuildable = 0x0001;

bool tile_unbuildable(int tile_x, int tile_y) {
    uint32_t flags = read_ptr(
        game_ptr((uintptr_t)GetModuleHandleW(nullptr), profile::kMapTileFlags));
    if (!flags) return true;  // no flags resolved: refuse rather than allow blind placement
    uint16_t v = read_at<uint16_t>(flags + (uint32_t)(tile_y * 256 + tile_x) * 2);
    return (v & kTileUnbuildable) != 0;
}

bool is_resource_unit(const UnitView& u) {
    return u.resources > 0 || u.type == 176 || u.type == 177 || u.type == 178 || u.type == 188;
}

bool is_resource_depot_type(int type) {
    return type == 106 || type == 131 || type == 154;  // CC, Hatchery, Nexus (gary/commands.py)
}

// "resource depot fits here": terrain + 3-tile distance from resources (the algorithm of
// gary_env_depot_spot_ok, env/gary_env.cpp).
bool depot_spot_tiles(const World& w, int tile_x, int tile_y, int tw, int th,
                      const std::vector<UnitView>& units) {
    int mw = read_at<uint16_t>(w.game + profile::kGameMapWidthTiles);
    int mh = read_at<uint16_t>(w.game + profile::kGameMapHeightTiles);
    if (tile_x < 0 || tile_y < 0 || tile_x + tw > mw || tile_y + th > mh) return false;
    for (int y = tile_y; y != tile_y + th; ++y)
        for (int x = tile_x; x != tile_x + tw; ++x)
            if (tile_unbuildable(x, y)) return false;
    for (const UnitView& u : units) {
        if (!is_resource_unit(u)) continue;
        if (u.x >= 32 * (tile_x - 3) && u.x < 32 * (tile_x + tw + 3) &&
            u.y >= 32 * (tile_y - 3) && u.y < 32 * (tile_y + th + 3))
            return false;
    }
    return true;
}

bool depot_spot_ok(const World& w, int tile_x, int tile_y) {
    std::vector<UnitView> units;
    std::string err;
    if (!units_collect(w, &units, &err)) return false;
    return depot_spot_tiles(w, tile_x, tile_y, 4, 3, units);
}

bool can_place(const World& w, int slot, uint16_t builder_tag, int unit_type, int tile_x,
               int tile_y) {
    (void)slot;
    int tw, th;
    if (!placement_size(unit_type, &tw, &th)) return false;
    std::vector<UnitView> units;
    std::string err;
    if (!units_collect(w, &units, &err)) return false;
    if (is_resource_depot_type(unit_type) && !depot_spot_tiles(w, tile_x, tile_y, tw, th, units))
        return false;
    int mw = read_at<uint16_t>(w.game + profile::kGameMapWidthTiles);
    int mh = read_at<uint16_t>(w.game + profile::kGameMapHeightTiles);
    if (tile_x < 0 || tile_y < 0 || tile_x + tw > mw || tile_y + th > mh) return false;
    for (int y = tile_y; y != tile_y + th; ++y)
        for (int x = tile_x; x != tile_x + tw; ++x)
            if (tile_unbuildable(x, y)) return false;
    // units in the way (v1: sprite bounding boxes; the builder itself does not block)
    int px0 = 32 * tile_x, py0 = 32 * tile_y, px1 = px0 + 32 * tw, py1 = py0 + 32 * th;
    for (const UnitView& u : units) {
        if (tag_of(u.ref, w.unit_count) == builder_tag) continue;
        int x0, y0, x1, y1;
        if (!clickable_rect(w, u, &x0, &y0, &x1, &y1)) continue;
        if (x1 > px0 && y1 > py0 && x0 < px1 && y0 < py1) return false;
    }
    return true;
}

bool start_locations_json(const World& w, std::string* out, std::string* error) {
    (void)error;
    *out = "[";
    bool first = true;
    for (int i = 0; i != 8; ++i) {
        uint32_t at = w.game + profile::kGameStartPosition + (uint32_t)i * 4;
        uint16_t x = read_at<uint16_t>(at), y = read_at<uint16_t>(at + 2);
        if (!x && !y) continue;
        if (!first) *out += ',';
        first = false;
        char buf[64];
        snprintf(buf, sizeof buf, "{\"x\":%u,\"y\":%u,\"slot\":%d}", x, y, i);
        *out += buf;
    }
    *out += "]";
    return true;
}

bool placement_size(int unit_type, int* w_tiles, int* h_tiles) {
    if (unit_type < 0 || unit_type >= 228) return false;
    *w_tiles = kPlacementSize[unit_type][0];
    *h_tiles = kPlacementSize[unit_type][1];
    return *w_tiles > 0 && *h_tiles > 0;
}

}  // namespace garyscr



