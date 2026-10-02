// gary_view: watch a replay in OpenBW's game window, optionally from a player's point of view.
//
//   gary_view --data <dir> --replay <file.rep> [--pov <file.pov.jsonl>] [--size 640x400]
//             [--record out.mp4 [--from SECONDS] [--to SECONDS] [--speed N]]
//
// --record renders the game (as fast as possible, not in real time) into a video through
// ffmpeg, which must be on PATH. --speed N plays N game frames per video frame (default 1:
// real time at Fastest; 4 = a 4x time-lapse).
//
// With --pov (written by gary.interface.HumanInterface.save_pov), the view follows that
// player's camera frame by frame and draws their mouse: a cross for the cursor, a green ring
// where a left click landed and a red ring for a right click. The window is the player's
// screen size, so you see exactly the area they saw. (v1: no fog of war; the window shows
// everything inside that area.)
//
// Controls (OpenBW's viewer): space pauses, the slider at the bottom seeks, the minimap and
// arrow keys move the view (in POV mode the view snaps back to the player's camera).

#include <stdexcept>  // OpenBW's util.h uses std::runtime_error without including it

#include "ui.h"
#include "common.h"
#include "bwgame.h"
#include "replay.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace bwgame;

namespace bwgame {
namespace ui {
void log_str(a_string str) {
	fwrite(str.data(), str.size(), 1, stdout);
	fflush(stdout);
}
void fatal_error_str(a_string str) {
	fprintf(stderr, "fatal error: %s\n", str.c_str());
	std::terminate();
}
}  // namespace ui
}  // namespace bwgame

namespace {

bool file_exists(const std::string& path) {
	std::ifstream f(path, std::ios::binary);
	return f.good();
}

struct data_loader {
	std::shared_ptr<data_loading::data_files_loader<>> mpqs;
	std::string dir;
	explicit data_loader(std::string d) : dir(std::move(d)) {
		if (!dir.empty() && dir.back() != '/' && dir.back() != '\\') dir += '/';
		if (file_exists(dir + "StarDat.mpq"))
			mpqs = std::make_shared<data_loading::data_files_loader<>>(data_loading::data_files_directory(dir.c_str()));
	}
	void operator()(a_vector<uint8_t>& dst, a_string filename) {
		if (mpqs) {
			(*mpqs)(dst, std::move(filename));
			return;
		}
		std::string path = dir;
		for (char c : filename) path += (c == '\\') ? '/' : c;
		if (path.compare(dir.size(), 6, "sound/") == 0) {
			dst.clear();  // the viewer is silent: sound files aren't extracted
			return;
		}
		std::ifstream f(path, std::ios::binary | std::ios::ate);
		if (!f) error("data file not found: %s", path.c_str());
		dst.resize((size_t)f.tellg());
		f.seekg(0);
		f.read((char*)dst.data(), (std::streamsize)dst.size());
	}
};

// One line of a POV log: {"frame":F,"camera":[x,y],"cursor":[x,y],"click":"left"|"right"|null}
struct pov_entry {
	int frame;
	int cam_x, cam_y, cur_x, cur_y;
	int click;  // 0 none, 1 left, 2 right
};

int json_int_after(const std::string& line, const char* key, int index = 0) {
	size_t p = line.find(key);
	if (p == std::string::npos) return 0;
	p += strlen(key);
	for (int i = 0; i != index; ++i) p = line.find(',', p) + 1;
	while (p < line.size() && (line[p] == ' ' || line[p] == '[' || line[p] == ':')) ++p;
	return atoi(line.c_str() + p);
}

std::vector<pov_entry> load_pov(const std::string& path) {
	std::vector<pov_entry> out;
	std::ifstream in(path);
	std::string line;
	while (std::getline(in, line)) {
		if (line.find("\"frame\"") == std::string::npos) continue;
		pov_entry e{};
		e.frame = json_int_after(line, "\"frame\":");
		e.cam_x = json_int_after(line, "\"camera\":", 0);
		e.cam_y = json_int_after(line, "\"camera\":", 1);
		e.cur_x = json_int_after(line, "\"cursor\":", 0);
		e.cur_y = json_int_after(line, "\"cursor\":", 1);
		e.click = line.find("\"click\":\"left\"") != std::string::npos ? 1
		        : line.find("\"click\":\"right\"") != std::string::npos ? 2 : 0;
		out.push_back(e);
	}
	return out;
}

struct pov_ui : ui_functions {
	std::vector<pov_entry> pov;
	size_t pov_index = 0;
	struct mark { int x, y, kind, until; };
	std::vector<mark> marks;
	int cursor_x = -1, cursor_y = -1;

	using ui_functions::ui_functions;

	// The latest POV entry at or before the current frame.
	void follow() {
		if (pov.empty()) return;
		if (pov_index >= pov.size() || pov[pov_index].frame > st.current_frame) pov_index = 0;  // seek back
		while (pov_index + 1 < pov.size() && pov[pov_index + 1].frame <= st.current_frame) {
			++pov_index;
			const auto& e = pov[pov_index];
			if (e.click) marks.push_back({e.cam_x + e.cur_x, e.cam_y + e.cur_y, e.click, st.current_frame + 12});
		}
		const auto& e = pov[pov_index];
		screen_pos = xy(e.cam_x, e.cam_y);
		cursor_x = e.cur_x;
		cursor_y = e.cur_y;
	}

	void draw_callback(uint8_t* data, size_t pitch) override {
		if (pov.empty()) return;
		auto put = [&](int x, int y, uint8_t c) {
			if (x >= 0 && y >= 0 && x < (int)screen_width && y < (int)screen_height) data[y * pitch + x] = c;
		};
		const uint8_t white = 255, green = 117, red = 111;
		for (auto& m : marks) {
			if (m.until < st.current_frame) continue;
			int sx = m.x - screen_pos.x, sy = m.y - screen_pos.y;
			for (int a = 0; a != 32; ++a) {
				double t = a * 3.14159265 / 16;
				put(sx + (int)(6 * cos(t)), sy + (int)(6 * sin(t)), m.kind == 1 ? green : red);
			}
		}
		marks.erase(std::remove_if(marks.begin(), marks.end(), [&](const mark& m) { return m.until < st.current_frame; }), marks.end());
		for (int d = -6; d <= 6; ++d) {
			put(cursor_x + d, cursor_y, white);
			put(cursor_x, cursor_y + d, white);
		}
	}
};

}  // namespace

int run(int argc, char** argv);

int main(int argc, char** argv) {
	try {
		return run(argc, argv);
	} catch (const std::exception& e) {
		fprintf(stderr, "error: %s\n", e.what());
		return 1;
	}
}

int run(int argc, char** argv) {
	std::string data_dir, replay_file, pov_file, record_file;
	int width = 640, height = 400;
	double from_s = 0, to_s = 1e9;
	int speed = 1;
	for (int i = 1; i < argc; ++i) {
		if (!strcmp(argv[i], "--data") && i + 1 < argc) data_dir = argv[++i];
		else if (!strcmp(argv[i], "--replay") && i + 1 < argc) replay_file = argv[++i];
		else if (!strcmp(argv[i], "--pov") && i + 1 < argc) pov_file = argv[++i];
		else if (!strcmp(argv[i], "--size") && i + 1 < argc) sscanf(argv[++i], "%dx%d", &width, &height);
		else if (!strcmp(argv[i], "--record") && i + 1 < argc) record_file = argv[++i];
		else if (!strcmp(argv[i], "--from") && i + 1 < argc) from_s = atof(argv[++i]);
		else if (!strcmp(argv[i], "--to") && i + 1 < argc) to_s = atof(argv[++i]);
		else if (!strcmp(argv[i], "--speed") && i + 1 < argc) speed = std::max(1, atoi(argv[++i]));
	}
	if (data_dir.empty() || replay_file.empty()) {
		fprintf(stderr, "usage: gary_view --data <dir> --replay <file.rep> [--pov <file.pov.jsonl>] [--size WxH]\n");
		return 2;
	}
	data_loader loader(data_dir);
	game_player player(loader);
	pov_ui ui(std::move(player));
	ui.load_all_image_data(loader);
	ui.load_data_file = [&](a_vector<uint8_t>& data, a_string filename) { loader(data, std::move(filename)); };
	ui.init();
	ui.load_replay_file(replay_file.c_str());
	if (!pov_file.empty()) ui.pov = load_pov(pov_file);
	ui.wnd.create("Gary viewer", 0, 0, width, height);
	ui.resize(width, height);
	ui.screen_pos = {0, 0};
	ui.set_image_data();

	if (!record_file.empty()) {
		// Pipe raw frames into ffmpeg: H.264, ~24 frames per second like the game at Fastest.
		char cmd[1024];
		snprintf(cmd, sizeof cmd,
		         "ffmpeg -loglevel error -y -f rawvideo -pix_fmt rgba -s %dx%d -r 24 -i - "
		         "-c:v libx264 -pix_fmt yuv420p -crf 20 \"%s\"", width, height, record_file.c_str());
#ifdef _WIN32
		FILE* out = _popen(cmd, "wb");
#else
		FILE* out = popen(cmd, "w");
#endif
		if (!out) {
			fprintf(stderr, "can't start ffmpeg\n");
			return 1;
		}
		int first = (int)(from_s * 1000 / 42), last = (int)(to_s * 1000 / 42);
		ui.draw_ui_elements = false;  // no replay slider in videos
		while (!ui.is_done() && ui.st.current_frame < last) {
			for (int i = 0; i != speed && !ui.is_done(); ++i) ui.replay_functions::next_frame();
			ui.replay_frame = ui.st.current_frame;
			if (ui.st.current_frame < first) continue;
			ui.follow();
			ui.update();
			const uint8_t* px = (const uint8_t*)ui.rgba_surface->lock();
			for (int y = 0; y != height; ++y) fwrite(px + (size_t)y * ui.rgba_surface->pitch, 4, width, out);
			ui.rgba_surface->unlock();
		}
#ifdef _WIN32
		_pclose(out);
#else
		pclose(out);
#endif
		printf("wrote %s\n", record_file.c_str());
		return 0;
	}

	auto clock = std::chrono::high_resolution_clock();
	auto last_tick = clock.now();
	const auto tick = std::chrono::milliseconds(42);  // Fastest
	while (true) {
		auto now = clock.now();
		if (!ui.is_paused && !ui.is_done()) {
			int n = 0;
			while (now - last_tick >= tick && n++ < 8 && !ui.is_done()) {
				ui.replay_functions::next_frame();
				last_tick += tick;
			}
			if (n >= 8) last_tick = now;
			ui.replay_frame = ui.st.current_frame;
		} else {
			last_tick = now;
		}
		ui.follow();
		ui.update();
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	return 0;
}
