// Replays as OpenBW's decoded stream ("reRS" | 633-byte game info | commands | map), shared by
// gary_resim and the env. Remastered-era replays are brought to this stream by
// resim/scr_format.py (to_flat); legacy ones by decode_legacy_replay below.

#pragma once

#include <cstdint>
#include <cstring>
#include <set>
#include <vector>

// Legacy (pre-1.18) replays: decompress the sections with OpenBW's own reader.
inline std::vector<uint8_t> decode_legacy_replay(const std::vector<uint8_t>& file) {
	bwgame::data_loading::data_reader_le raw(file.data(), file.data() + file.size());
	auto r = bwgame::data_loading::make_replay_file_reader(raw);
	std::vector<uint8_t> out(4 + 633);
	uint32_t id = r.template get<uint32_t>();
	memcpy(out.data(), &id, 4);
	r.get_bytes(out.data() + 4, 633);
	for (int section = 0; section != 2; ++section) {  // commands, then map data
		uint32_t n = r.template get<uint32_t>();
		size_t at = out.size();
		out.resize(at + 4 + n);
		memcpy(out.data() + at, &n, 4);
		r.get_bytes(out.data() + at + 4, n);
	}
	return out;
}

// The map section of a decoded stream.
inline std::vector<uint8_t> stream_map_data(const std::vector<uint8_t>& stream) {
	size_t pos = 4 + 633;
	uint32_t cmd_len;
	memcpy(&cmd_len, stream.data() + pos, 4);
	pos += 4 + cmd_len;
	uint32_t map_len;
	memcpy(&map_len, stream.data() + pos, 4);
	pos += 4;
	return std::vector<uint8_t>(stream.begin() + pos, stream.begin() + pos + map_len);
}

// Many 1v1 maps are "use map settings" maps whose triggers only show text, play sounds or keep
// leaderboards. OpenBW implements the triggers that affect the game, not these, and stops with
// "unknown trigger action". Marking them disabled (flag 2, which BW itself skips) changes nothing
// about the game.
inline void disable_cosmetic_trigger_actions(std::vector<uint8_t>& stream) {
	static const std::set<int> cosmetic = {
		8,   // play sound
		9,   // display text message
		10,  // center view
		12,  // set mission objectives
		17, 18, 19, 20, 21, 32, 33, 34, 35, 36, 37, 40,  // leaderboards
		28,  // minimap ping
		29,  // talking portrait
		30, 31,  // mute / unmute unit speech
		47,  // comment
	};
	size_t pos = 4 + 633;
	uint32_t cmd_len;
	memcpy(&cmd_len, stream.data() + pos, 4);
	pos += 4 + cmd_len;
	uint32_t map_len;
	memcpy(&map_len, stream.data() + pos, 4);
	pos += 4;
	size_t map_end = pos + map_len;
	while (pos + 8 <= map_end) {
		int32_t size;
		memcpy(&size, stream.data() + pos + 4, 4);
		if (size < 0 || pos + 8 + (size_t)size > map_end) break;
		if (!memcmp(stream.data() + pos, "TRIG", 4)) {
			for (size_t t = 0; t + 2400 <= (size_t)size; t += 2400) {
				for (size_t i = 0; i != 64; ++i) {
					uint8_t* action = stream.data() + pos + 8 + t + 320 + i * 32;
					if (cosmetic.count(action[26])) action[28] |= 2;
				}
			}
		}
		pos += 8 + (size_t)size;
	}
}
