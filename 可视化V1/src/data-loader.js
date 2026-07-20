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
  const pointVar = layerVarName(layer.id, "points");
  const lineVar = layerVarName(layer.id, "lines");
  await Promise.all([
    window[pointVar] ? Promise.resolve() : loadScript(`./data/layers/${layer.id}.points.js`),
    window[lineVar] ? Promise.resolve() : loadScript(`./data/layers/${layer.id}.lines.js`)
  ]);
  return {
    points: window[pointVar],
    lines: window[lineVar]
  };
}
