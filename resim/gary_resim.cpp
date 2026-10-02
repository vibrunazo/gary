// gary_resim: re-simulates a Brood War replay in OpenBW (headless) and prints periodic state
// snapshots as JSON lines on stdout.
//
// Usage:
//   gary_resim --data <dir> --replay <file.rep> [--every <frames>]
//
// --data is either a folder with the three 1.16.1/1.18 MPQs (StarDat.mpq, BrooDat.mpq,
// Patch_rt.mpq) or a folder of loose files extracted from a newer install (e.g. SC:R's CASC
// storage), laid out with their in-archive paths (arr/units.dat, scripts/iscript.bin, ...).
//
// Output, one JSON object per line:
//   {"type":"header", ...}                      replay info
//   {"type":"snapshot","frame":F,"players":[...]} every --every frames (default 24 = 1 s)
//   {"type":"end", ...}                          totals
//
// Each snapshot reports, per player: minerals, gas, supply (in BW's displayed units), unit counts
// by unit type ID (all / completed), and how many replay actions the engine accepted or rejected
// since the previous snapshot. Rejected actions have a low baseline from spam; a sustained spike
// is the main desync signal (the replay's commands stop making sense in the simulated state).

#include <stdexcept>  // OpenBW's util.h uses std::runtime_error without including it

#include "bwgame.h"
#include "replay.h"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <optional>
#include <string>

using namespace bwgame;

namespace {

bool file_exists(const std::string& path) {
	std::ifstream f(path, std::ios::binary);
	return f.good();
}

// Game data from the classic MPQs if present, else from a folder of extracted files.
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

std::string json_escape(const a_string& s) {
	std::string r;
	for (unsigned char c : s) {
		if (c == '"' || c == '\\') { r += '\\'; r += (char)c; }
		else if (c < 0x20) { char buf[8]; snprintf(buf, sizeof buf, "\\u%04x", c); r += buf; }
		else r += (char)c;  // replay strings are raw bytes (often CP949); consumers decode leniently
	}
	return r;
}

// Same as replay_functions::next_frame, but counts accepted / rejected actions per player.
struct counting_replay_functions : replay_functions {
	std::array<int, 12> accepted{};
	std::array<int, 12> rejected{};
	std::array<int, 12> total_rejected{};

	using replay_functions::replay_functions;

	void execute_actions_counted() {
		uint8_t* begin = replay_st.actions_data_buffer.data();
		uint8_t* end_all = begin + replay_st.actions_data_buffer.size();
		if (st.current_frame != action_st.next_action_frame) return;
		while (action_st.actions_data_position != size_t(end_all - begin)) {
			data_loading::data_reader_le r(begin + action_st.actions_data_position, end_all);
			int frame = r.get<int32_t>();
			if (frame != st.current_frame) {
				action_st.next_action_frame = frame;
				return;
			}
			size_t actions_size = r.get<uint8_t>();
			const uint8_t* ptr = r.get_n(actions_size);
			const uint8_t* end = ptr + actions_size;
			data_loading::data_reader_le r2(ptr, end);
			while (r2.ptr != end) {
				int player_id = r2.ptr[0];
				auto i = std::find(action_st.player_id.begin(), action_st.player_id.end(), player_id);
				int owner = i == action_st.player_id.end() ? -1 : (int)(i - action_st.player_id.begin());
				bool ok = read_action(r2);
				if (owner >= 0 && owner < 12) {
					if (ok) ++accepted[owner];
					else { ++rejected[owner]; ++total_rejected[owner]; }
				}
			}
			action_st.actions_data_position = end - begin;
		}
	}

	void next_frame_counted() {
		if (st.current_frame == replay_st.end_frame) error("replay: attempt to play past end");
		execute_actions_counted();
		state_functions::next_frame();
	}
};

bool is_player(const state& st, int i) {
	return st.players[i].controller == player_t::controller_occupied ||
	       st.players[i].controller == player_t::controller_user_left ||
	       st.players[i].controller == player_t::controller_computer_game;
}

void print_snapshot(const state& st, const replay_state& rst, counting_replay_functions& f) {
	std::string out = "{\"type\":\"snapshot\",\"frame\":" + std::to_string(st.current_frame) + ",\"players\":[";
	bool first_player = true;
	for (int p = 0; p != 8; ++p) {
		if (!is_player(st, p)) continue;
		if (!first_player) out += ',';
		first_player = false;
		int race = (int)st.players[p].race;
		int ri = race >= 0 && race < 3 ? race : 0;
		out += "{\"slot\":" + std::to_string(p) +
		       ",\"minerals\":" + std::to_string(st.current_minerals[p]) +
		       ",\"gas\":" + std::to_string(st.current_gas[p]) +
		       // supply is stored in half units (a zergling is 1)
		       ",\"supply_used\":" + std::to_string(st.supply_used[p][ri].raw_value / 2.0) +
		       ",\"supply_max\":" + std::to_string(st.supply_available[p][ri].raw_value / 2.0) +
		       ",\"accepted\":" + std::to_string(f.accepted[p]) +
		       ",\"rejected\":" + std::to_string(f.rejected[p]) + ",\"units\":{";
		bool first_unit = true;
		for (int id = 0; id != 228; ++id) {
			int all = st.unit_counts[p][(UnitTypes)id];
			if (!all) continue;
			int done = st.completed_unit_counts[p][(UnitTypes)id];
			if (!first_unit) out += ',';
			first_unit = false;
			out += "\"" + std::to_string(id) + "\":[" + std::to_string(all) + "," + std::to_string(done) + "]";
		}
		out += "}}";
		f.accepted[p] = f.rejected[p] = 0;
	}
	out += "]}\n";
	fputs(out.c_str(), stdout);
}

}  // namespace

int main(int argc, char** argv) {
	std::string data_dir, replay_file;
	int every = 24;
	for (int i = 1; i < argc; ++i) {
		if (!strcmp(argv[i], "--data") && i + 1 < argc) data_dir = argv[++i];
		else if (!strcmp(argv[i], "--replay") && i + 1 < argc) replay_file = argv[++i];
		else if (!strcmp(argv[i], "--every") && i + 1 < argc) every = std::max(1, atoi(argv[++i]));
		else {
			fprintf(stderr, "usage: gary_resim --data <dir> --replay <file.rep> [--every <frames>]\n");
			return 2;
		}
	}
	if (data_dir.empty() || replay_file.empty()) {
		fprintf(stderr, "usage: gary_resim --data <dir> --replay <file.rep> [--every <frames>]\n");
		return 2;
	}

	try {
		game_player player{data_loader(data_dir)};
		action_state action_st;
		replay_state replay_st;
		counting_replay_functions f(player.st(), action_st, replay_st);
		f.load_replay_file(replay_file.c_str());
		const state& st = player.st();

		std::string header = "{\"type\":\"header\",\"end_frame\":" + std::to_string(replay_st.end_frame) +
		                     ",\"map\":\"" + json_escape(replay_st.map_name) + "\",\"players\":[";
		bool first = true;
		for (int p = 0; p != 8; ++p) {
			if (!is_player(st, p)) continue;
			if (!first) header += ',';
			first = false;
			header += "{\"slot\":" + std::to_string(p) + ",\"name\":\"" + json_escape(replay_st.player_name[p]) +
			          "\",\"race\":" + std::to_string((int)st.players[p].race) + "}";
		}
		header += "]}\n";
		fputs(header.c_str(), stdout);

		while (!f.is_done()) {
			f.next_frame_counted();
			if (st.current_frame % every == 0) print_snapshot(st, replay_st, f);
		}
		print_snapshot(st, replay_st, f);

		std::string end = "{\"type\":\"end\",\"frame\":" + std::to_string(st.current_frame) + ",\"total_rejected\":{";
		first = true;
		for (int p = 0; p != 8; ++p) {
			if (!is_player(st, p)) continue;
			if (!first) end += ',';
			first = false;
			end += "\"" + std::to_string(p) + "\":" + std::to_string(f.total_rejected[p]);
		}
		end += "}}\n";
		fputs(end.c_str(), stdout);
	} catch (const std::exception& e) {
		fprintf(stderr, "error: %s\n", e.what());
		return 1;
	}
	return 0;
}
