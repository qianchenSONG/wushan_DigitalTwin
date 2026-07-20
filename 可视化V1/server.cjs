const http = require("http");
const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = __dirname;
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml"
};

function send(res, code, body, type = "text/plain; charset=utf-8") {
  res.writeHead(code, {
    "Content-Type": type,
    "Cache-Control": "no-cache"
  });
  res.end(body);
}

function makeServer() {
  return http.createServer((req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    const safePath = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
    const filePath = path.resolve(root, safePath);
    if (!filePath.startsWith(root)) {
      send(res, 403, "Forbidden");
      return;
    }
    fs.readFile(filePath, (error, data) => {
      if (error) {
        send(res, 404, "Not found");
        return;
      }
      send(res, 200, data, mime[path.extname(filePath).toLowerCase()] || "application/octet-stream");
    });
  });
}

function listen(port) {
  const server = makeServer();
  server.on("error", (error) => {
    if (error.code === "EADDRINUSE" && port < 8795) {
      listen(port + 1);
      return;
    }
    console.error(error.message);
  });
  server.listen(port, "127.0.0.1", () => {
    const url = `http://127.0.0.1:${port}/`;
    console.log(`巫山数字孪生系统已启动：${url}`);
    if (process.platform === "win32") {
      childProcess.exec(`start "" "${url}"`);
    }
  });
}

listen(8765);
