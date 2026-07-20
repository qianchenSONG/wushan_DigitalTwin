const fs = require("fs");

const html = fs.readFileSync("index.html", "utf8");
const files = [
  "src/main.js",
  "src/styles.css",
  "data/pipes.js",
  "data/summary.js",
  "data/layers/catalog.js",
  "vendor/leaflet/leaflet.js"
];

for (const file of files) {
  if (!fs.existsSync(file)) {
    throw new Error(`Missing ${file}`);
  }
}

if (!html.includes("./src/main.js")) {
  throw new Error("index.html does not reference src/main.js");
}

const catalog = JSON.parse(fs.readFileSync("data/layers/catalog.json", "utf8"));
if (catalog.length < 2) {
  throw new Error("Layer catalog is incomplete");
}

const summary = JSON.parse(fs.readFileSync("data/summary.json", "utf8"));
const pipes = JSON.parse(fs.readFileSync("data/pipes.geojson", "utf8"));
if (summary.pipe_segment_count !== pipes.features.length) {
  throw new Error("Pipe count mismatch");
}

console.log(JSON.stringify({
  ok: true,
  catalog: catalog.map((item) => item.id),
  pipeSegments: pipes.features.length,
  pipeLengthKm: summary.total_length_km
}, null, 2));
