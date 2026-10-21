// One-off fix for site/vendor/countries-50m.json (world-atlas 2.0.2).
//
// world-atlas draws Morocco down to 21°N, including the Moroccan-administered part of
// Western Sahara, and leaves "W. Sahara" as only the thin eastern strip. This moves
// everything in Morocco's shape south of the 27°40'N border into Western Sahara.
//
//   npm install --prefix /tmp/mapfix polygon-clipping@0.15.7 topojson-server@3.0.1 topojson-client@3.1.0
//   DEPS=/tmp/mapfix/node_modules node tools/fix-western-sahara.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(process.env.DEPS.replace(/\/?$/, "/"));
const pc = require("polygon-clipping");
const { feature, quantize } = require("topojson-client");
const { topology } = require("topojson-server");

const FILE = new URL("../site/vendor/countries-50m.json", import.meta.url);
const BORDER_LAT = 27 + 40 / 60;

const world = JSON.parse(readFileSync(FILE, "utf8"));
const fc = feature(world, world.objects.countries);
const morocco = fc.features.find(f => f.properties.name === "Morocco");
const sahara = fc.features.find(f => f.properties.name === "W. Sahara");
if (!morocco || !sahara) throw new Error("Morocco / W. Sahara not found");

const coords = g => g.type === "Polygon" ? [g.coordinates] : g.coordinates;
const box = (s, n) => [[[-30, s], [10, s], [10, n], [-30, n], [-30, s]]];
const north = pc.intersection(coords(morocco.geometry), box(BORDER_LAT, 90));
const south = pc.intersection(coords(morocco.geometry), box(-90, BORDER_LAT));
if (!south.length) {
  console.log("Morocco already stops at the border; nothing to do.");
  process.exit(0);
}

// polygon-clipping outputs counter-clockwise outer rings; d3-geo wants clockwise.
const toD3 = mp => {
  const polys = mp.map(poly => poly.map(ring => ring.slice().reverse()));
  return polys.length === 1 ? { type: "Polygon", coordinates: polys[0] } : { type: "MultiPolygon", coordinates: polys };
};
morocco.geometry = toD3(north);
sahara.geometry = toD3(pc.union(coords(sahara.geometry), south));

const out = quantize(topology({ countries: fc }), 1e5);
writeFileSync(FILE, JSON.stringify(out));
console.log(`Morocco: ${north.length} polygon(s); W. Sahara now ${sahara.geometry.type}`);
