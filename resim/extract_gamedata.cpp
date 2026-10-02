// extract_gamedata: copies the game-logic files OpenBW needs out of a StarCraft install that
// stores its data in CASC (the free StarCraft / Remastered client, 1.23+), into a plain folder
// that gary_resim can read with --data.
//
// Usage:
//   extract_gamedata --install <StarCraft folder> --out <folder>   extract the needed files
//   extract_gamedata --install <StarCraft folder> --list <text>    list files whose name contains <text>
//
// The install folder is the one containing ".build.info". Extracted files are Blizzard's game
// data: keep them out of the repository (the default --out under data/ is gitignored).

#include "CascLib.h"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

// What OpenBW loads (bwgame.h): the data tables, the animation script, tilesets, the melee
// triggers and the classic unit graphics and overlay offset files (read for image sizes and
// attachment points). The viewer additionally needs the tileset graphics and palettes.
const char* const kWantedPrefixes[] = {
	"arr\\", "scripts\\iscript.bin", "tileset\\", "triggers\\melee.trg", "unit\\", "game\\",
};
const char* const kWantedExtensions[] = {".dat", ".tbl", ".bin", ".cv5", ".vf4", ".trg", ".grp"};

std::string lower(std::string s) {
	for (char& c : s) c = (char)tolower((unsigned char)c);
	return s;
}

bool ends_with(const std::string& s, const char* suffix) {
	size_t n = strlen(suffix);
	return s.size() >= n && s.compare(s.size() - n, n, suffix) == 0;
}

bool wanted(const std::string& name) {
	std::string n = lower(name);
	for (char& c : n) if (c == '/') c = '\\';
	bool prefix = false;
	for (const char* p : kWantedPrefixes) prefix |= n.rfind(p, 0) == 0;
	if (!prefix) return false;
	if (n.rfind("unit\\", 0) == 0) return true;  // graphics and overlay offsets (.grp, .lo?) listed in images.tbl
	if (n.rfind("tileset\\", 0) == 0) return true;  // terrain: also graphics and palettes for the viewer
	if (n.rfind("game\\", 0) == 0) return true;     // viewer: unit color tables (tunit.pcx, ...)
	for (const char* e : kWantedExtensions) if (ends_with(n, e)) return true;
	return false;
}

bool read_file(HANDLE storage, const char* name, std::vector<char>& out) {
	HANDLE f = nullptr;
	if (!CascOpenFile(storage, name, 0, CASC_OPEN_BY_NAME, &f)) return false;
	ULONGLONG size = 0;
	bool ok = CascGetFileSize64(f, &size);
	if (ok) {
		out.resize((size_t)size);
		DWORD read = 0;
		ok = CascReadFile(f, out.data(), (DWORD)size, &read) && read == size;
	}
	CascCloseFile(f);
	return ok;
}

}  // namespace

int main(int argc, char** argv) {
	std::string install, out, list;
	for (int i = 1; i < argc; ++i) {
		if (!strcmp(argv[i], "--install") && i + 1 < argc) install = argv[++i];
		else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
		else if (!strcmp(argv[i], "--list") && i + 1 < argc) list = lower(argv[++i]);
		else install.clear(), i = argc;
	}
	if (install.empty() || (out.empty() && list.empty())) {
		fprintf(stderr, "usage: extract_gamedata --install <dir> (--out <dir> | --list <text>)\n");
		return 2;
	}

	HANDLE storage = nullptr;
	if (!CascOpenStorage(install.c_str(), 0, &storage)) {
		fprintf(stderr, "error: can't open CASC storage in the given install folder (error %u)\n", GetCascError());
		return 1;
	}

	CASC_FIND_DATA fd{};
	HANDLE find = CascFindFirstFile(storage, "*", &fd, nullptr);
	if (!find) {
		fprintf(stderr, "error: can't enumerate files (error %u)\n", GetCascError());
		CascCloseStorage(storage);
		return 1;
	}
	int matched = 0, written = 0, failed = 0;
	std::vector<char> buf;
	do {
		std::string name = fd.szFileName;
		if (!list.empty()) {
			if (lower(name).find(list) != std::string::npos) {
				printf("%10llu  %s\n", (unsigned long long)fd.FileSize, name.c_str());
				++matched;
			}
			continue;
		}
		if (!wanted(name)) continue;
		++matched;
		if (!fd.bFileAvailable || !read_file(storage, name.c_str(), buf)) {
			fprintf(stderr, "  can't read: %s\n", name.c_str());
			++failed;
			continue;
		}
		std::string rel = name;
		for (char& c : rel) if (c == '\\') c = '/';
		fs::path dst = fs::path(out) / rel;
		fs::create_directories(dst.parent_path());
		std::ofstream(dst, std::ios::binary).write(buf.data(), (std::streamsize)buf.size());
		++written;
		// Remastered ships tileset graphics indices as .vx4ex (32-bit entries); OpenBW reads the
		// classic .vx4 (16-bit). Same data: bit 0 = flipped, the rest = minitile index.
		if (dst.extension() == ".vx4ex" && buf.size() % 4 == 0) {
			std::vector<char> vx4(buf.size() / 2);
			for (size_t i = 0; i != buf.size() / 4; ++i) {
				uint32_t v;
				memcpy(&v, buf.data() + 4 * i, 4);
				uint16_t w = (uint16_t)v;
				memcpy(vx4.data() + 2 * i, &w, 2);
			}
			fs::path classic = dst;
			classic.replace_extension(".vx4");
			std::ofstream(classic, std::ios::binary).write(vx4.data(), (std::streamsize)vx4.size());
		}
	} while (CascFindNextFile(find, &fd));
	CascFindClose(find);
	CascCloseStorage(storage);

	if (list.empty()) printf("extracted %d of %d matching files (%d failed)\n", written, matched, failed);
	else printf("%d files\n", matched);
	return failed ? 1 : 0;
}
