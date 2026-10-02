// gary_env: a headless Brood War game (OpenBW) that Python code can play, through a small C API.
//
// v0 scope: start a game on a replay's map with that replay's players and races (the replay's
// own commands are ignored), step it frame by frame, send each player's commands in the
// replay command format, read the full game state as JSON, and save the game as a replay.
//
// Players' commands use the same bytes as replay commands (select = 0x09, right click = 0x14,
// train = 0x1f, build = 0x0c, ...), which is also what Gary's human interface will emit.
//
// The state returned by gary_env_observe is the full, unfiltered game state. Fog of war is
// applied by the caller using each unit's "visible_to" bitmask (bit p = visible to player p).

#include <stdexcept>  // OpenBW's util.h uses std::runtime_error without including it

#include "bwgame.h"
#include "replay.h"
#include "replay_saver.h"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#ifdef _WIN32
#define GARY_API extern "C" __declspec(dllexport)
#else
#define GARY_API extern "C"
#endif

using namespace bwgame;

namespace {

bool file_exists(const std::string& path) {
	std::ifstream f(path, std::ios::binary);
	return f.good();
}

// Same loader as gary_resim: classic MPQs if present, else extracted loose files.
struct data_loader {
	std::optional<data_loading::data_files_loader<>> mpqs;
	std::string dir;
	explicit data_loader(std::string d) : dir(std::move(d)) {
		if (!dir.empty() && dir.back() != '/' && dir.back() != '\\') dir += '/';
		if (file_exists(dir + "StarDat.mpq")) mpqs.emplace(data_loading::data_files_directory(dir.c_str()));
	}
	void operator()(a_vector<uint8_t>& dst, a_string filename) {
		if (mpqs) {
			(*mpqs)(dst, std::move(filename));
			return;
		}
		std::string path = dir;
		for (char c : filename) path += (c == '\\') ? '/' : c;
		std::ifstream f(path, std::ios::binary | std::ios::ate);
		if (!f) error("data file not found: %s", path.c_str());
		dst.resize((size_t)f.tellg());
		f.seekg(0);
		f.read((char*)dst.data(), (std::streamsize)dst.size());
	}
};

struct env {
	game_player player;
	action_state action_st;
	replay_state replay_st;
	std::optional<replay_functions> funcs;
	std::vector<uint8_t> map_data;
	std::array<uint8_t, 633> header{};  // the source replay's game info, reused when saving
	replay_saver_state saver_st;
	std::string observation;
	std::string last_error;

	explicit env(const std::string& data_dir) : player(data_loader(data_dir)) {}
};

std::string json_escape(const a_string& s) {
	std::string r;
	for (unsigned char c : s) {
		if (c == '"' || c == '\\') { r += '\\'; r += (char)c; }
		else if (c < 0x20) { char buf[8]; snprintf(buf, sizeof buf, "\\u%04x", c); r += buf; }
		else r += (char)c;
	}
	return r;
}

}  // namespace

// Creates a game on the map of the given replay file. Returns null on error (see gary_env_error
// with a null handle for the message).
static std::string g_create_error;

GARY_API void* gary_env_create(const char* data_dir, const char* replay_path) {
	try {
		auto e = std::make_unique<env>(data_dir);
		std::ifstream in(replay_path, std::ios::binary);
		if (!in) error("can't open replay: %s", replay_path);
		std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
		e->funcs.emplace(e->player.st(), e->action_st, e->replay_st);
		std::vector<uint8_t> map;
		data_loading::data_reader_le raw(bytes.data(), bytes.data() + bytes.size());
		e->funcs->load_replay(data_loading::make_replay_file_reader(raw), true, &map);
		e->map_data = map;
		{
			data_loading::data_reader_le raw2(bytes.data(), bytes.data() + bytes.size());
			auto rr = data_loading::make_replay_file_reader(raw2);
			rr.template get<uint32_t>();
			rr.get_bytes(e->header.data(), e->header.size());
		}
		// keep the game, drop the replay's own commands
		e->replay_st.actions_data_buffer.clear();
		e->action_st.actions_data_position = 0;
		e->action_st.next_action_frame = -1;
		e->replay_st.end_frame = 0x7fffffff;

		auto& sv = e->saver_st;
		sv.map_data = e->map_data.data();
		sv.map_data_size = e->map_data.size();
		sv.map_name = e->replay_st.map_name;
		sv.game_name = "Gary";
		sv.player_name = "Gary";
		const state& st = e->player.st();
		sv.map_tile_width = st.game->map_tile_width;
		sv.map_tile_height = st.game->map_tile_height;
		sv.tileset = (int)st.game->tileset_index;
		sv.random_seed = st.lcg_rand_state;
		sv.players = st.players;
		for (size_t i = 0; i != 12; ++i) sv.player_names[i] = e->replay_st.player_name[i];
		int active = 0;
		for (int i = 0; i != 8; ++i) active += st.players[i].controller == player_t::controller_occupied;
		sv.active_player_count = active;
		sv.slot_count = active;
		sv.game_type = e->replay_st.game_type;
		return e.release();
	} catch (const std::exception& ex) {
		g_create_error = ex.what();
		return nullptr;
	}
}

GARY_API const char* gary_env_error(void* h) {
	return h ? ((env*)h)->last_error.c_str() : g_create_error.c_str();
}

GARY_API void gary_env_destroy(void* h) { delete (env*)h; }

// Advances the game by n frames. Returns false on error.
GARY_API bool gary_env_step(void* h, int n) {
	auto* e = (env*)h;
	try {
		for (int i = 0; i != n; ++i) e->funcs->state_functions::next_frame();
		return true;
	} catch (const std::exception& ex) {
		e->last_error = ex.what();
		return false;
	}
}

// Executes one command for a player slot (bytes as in a replay, without the player id byte).
// Returns 1 if the engine accepted it, 0 if rejected, -1 on error.
GARY_API int gary_env_act(void* h, int slot, const uint8_t* data, int size) {
	auto* e = (env*)h;
	try {
		bool ok = e->funcs->read_action(slot, data, (size_t)size);
		// replays identify players by their player id, not their slot
		replay_saver_functions(e->saver_st).add_action(e->player.st().current_frame, e->action_st.player_id[slot], data, (size_t)size);
		return ok ? 1 : 0;
	} catch (const std::exception& ex) {
		e->last_error = ex.what();
		return -1;
	}
}

// The full game state as JSON (valid until the next call). Positions are in pixels.
GARY_API const char* gary_env_observe(void* h) {
	auto* e = (env*)h;
	const state& st = e->player.st();
	auto& f = *e->funcs;
	std::string& o = e->observation;
	o = "{\"frame\":" + std::to_string(st.current_frame) + ",\"players\":[";
	bool first = true;
	for (int p = 0; p != 8; ++p) {
		if (st.players[p].controller != player_t::controller_occupied) continue;
		if (!first) o += ',';
		first = false;
		int race = (int)st.players[p].race;
		int ri = race >= 0 && race < 3 ? race : 0;
		o += "{\"slot\":" + std::to_string(p) + ",\"name\":\"" + json_escape(e->replay_st.player_name[p]) +
		     "\",\"race\":" + std::to_string(race) + ",\"minerals\":" + std::to_string(st.current_minerals[p]) +
		     ",\"gas\":" + std::to_string(st.current_gas[p]) +
		     ",\"supply_used\":" + std::to_string(st.supply_used[p][ri].raw_value / 2.0) +
		     ",\"supply_max\":" + std::to_string(st.supply_available[p][ri].raw_value / 2.0) +
		     ",\"victory_state\":" + std::to_string(st.players[p].victory_state) + "}";
	}
	o += "],\"units\":[";
	first = true;
	for (const unit_t* u : ptr(st.visible_units)) {
		if (!first) o += ',';
		first = false;
		char buf[256];
		snprintf(buf, sizeof buf,
		         "{\"tag\":%u,\"owner\":%d,\"type\":%d,\"x\":%d,\"y\":%d,\"hp\":%d,\"shields\":%d,"
		         "\"completed\":%d,\"visible_to\":%d,\"order\":%d,\"resources\":%d}",
		         (unsigned)f.get_unit_id(u).raw_value, u->owner, (int)u->unit_type->id, u->sprite->position.x,
		         u->sprite->position.y, u->hp.integer_part(), u->shield_points.integer_part(),
		         f.u_completed(u) ? 1 : 0, u->sprite->visibility_flags, (int)u->order_type->id,
		         f.ut_resource(u->unit_type) ? u->building.resource.resource_count : 0);
		o += buf;
	}
	o += "]}";
	return o.c_str();
}

// Saves everything played so far as a (pre-1.18 format) replay. Returns false on error.
GARY_API bool gary_env_save_replay(void* h, const char* path) {
	auto* e = (env*)h;
	try {
		// Same game setup as the source replay (players, races, starting units), with this game's
		// length and commands.
		std::array<uint8_t, 633> header = e->header;
		uint32_t frames = (uint32_t)e->player.st().current_frame;
		memcpy(header.data() + 1, &frames, 4);
		data_loading::file_writer<> w(path);
		auto rw = data_loading::make_replay_file_writer(w);
		rw.template put<uint32_t>(0x53526572);
		rw.put_bytes(header.data(), header.size());
		std::vector<uint8_t> commands;
		for (auto& v : e->saver_st.history) commands.insert(commands.end(), v.begin(), v.end());
		rw.template put<uint32_t>((uint32_t)commands.size());
		rw.put_bytes(commands.data(), commands.size());
		rw.template put<uint32_t>((uint32_t)e->map_data.size());
		rw.put_bytes(e->map_data.data(), e->map_data.size());
		return true;
	} catch (const std::exception& ex) {
		e->last_error = ex.what();
		return false;
	}
}
