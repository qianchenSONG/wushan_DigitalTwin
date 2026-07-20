export function featureInBounds(feature, bounds) {
  const geom = feature.geometry;
  if (!geom) return false;
  if (geom.type === "Point") {
    const [lon, lat] = geom.coordinates;
    return bounds.contains([lat, lon]);
  }
  if (geom.type === "LineString") {
    return geom.coordinates.some(([lon, lat]) => bounds.contains([lat, lon]));
  }
  return false;
}

export function visiblePipe(feature, state) {
  const p = feature.properties;
  return state.waterVisible && state.activeMaterials.has(p.material) && (state.activeDiameter === "all" || String(p.diameter) === state.activeDiameter);
}

export function formatKm(meters) {
  return `${(meters / 1000).toFixed(2)} km`;
}

export function topicFeatureCount(topicState) {
  let count = 0;
  topicState.forEach((entry) => {
    if (!entry.visible || !entry.data) return;
    count += entry.data.points?.features?.length || 0;
    count += entry.data.lines?.features?.length || 0;
  });
  return count;
}

export function topicFeatureCountInBounds(topicState, bounds) {
  let count = 0;
  topicState.forEach((entry) => {
    if (!entry.visible || !entry.data) return;
    const points = entry.data.points?.features || [];
    const lines = entry.data.lines?.features || [];
    count += points.filter((f) => featureInBounds(f, bounds)).length;
    count += lines.filter((f) => featureInBounds(f, bounds)).length;
  });
  return count;
}
