import { MapSystem } from "./map-system.js";
import { SystemUi } from "./ui.js";

const mapSystem = new MapSystem({
  onLayerChange: () => ui?.renderLegend(),
  onStatus: (text) => ui?.updateStatus(text)
});

let ui;

mapSystem.init();
ui = new SystemUi(mapSystem);
ui.init();
