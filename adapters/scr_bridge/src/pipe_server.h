#pragma once
// Named-pipe server: newline-delimited JSON requests in, responses out. One request per line
// {"id":N,"method":"...","args":{...}} -> {"id":N,"ok":true,"result":...} or
// {"id":N,"ok":false,"error":"..."}. Runs on its own thread; the handler runs there too and
// must only read game state (see observe.h).

#include <functional>
#include <string>
#include <vector>

namespace garyscr {

// Handler: receives one request line, returns one response line.
using RequestHandler = std::function<std::string(const std::string& request)>;

// Serves until `stop` is set (checked between clients). Pipe name like \\.\pipe\gary_scr.
// Returns false and sets `error` if the pipe cannot be created.
bool pipe_serve(const std::wstring& pipe_name, const RequestHandler& handler,
                volatile bool* stop, std::string* error);

// Incremental line splitting used by the reader (exposed for tests): feed bytes, get whole
// lines. Returns the lines; keeps the partial remainder internally.
class LineSplitter {
  public:
    void feed(const char* data, size_t n, std::vector<std::string>* lines);
    const std::string& remainder() const { return remainder_; }

  private:
    std::string remainder_;
};

}  // namespace garyscr
