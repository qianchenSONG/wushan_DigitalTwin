const loadedScripts = new Map();

export function loadScript(src) {
  if (loadedScripts.has(src)) {
    return loadedScripts.get(src);
  }
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`无法加载 ${src}`));
    document.body.appendChild(script);
  });
  loadedScripts.set(src, promise);
  return promise;
}

export function layerVarName(layerId, type) {
  return `LAYER_${layerId.toUpperCase().replaceAll("-", "_")}_${type.toUpperCase()}`;
}

export async function loadTopicLayer(layer) {
  const pointLayerId = layer.pointsDataId || layer.id;
  const lineLayerId = layer.linesDataId || layer.id;
  const pointVar = layerVarName(pointLayerId, "points");
  const lineVar = layerVarName(lineLayerId, "lines");
  const empty = { type: "FeatureCollection", features: [] };
  await Promise.all([
    layer.hasPoints === false || window[pointVar] ? Promise.resolve() : loadScript(`./data/layers/${pointLayerId}.points.js`),
    layer.hasLines === false || window[lineVar] ? Promise.resolve() : loadScript(`./data/layers/${lineLayerId}.lines.js`)
  ]);
  return {
    points: layer.hasPoints === false ? empty : window[pointVar],
    lines: layer.hasLines === false ? empty : window[lineVar]
  };
}
