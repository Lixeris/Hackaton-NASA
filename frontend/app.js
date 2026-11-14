// Jezero crater : 18.4°N, 77.7°E
const JEZERO_LAT = 18.4;
const JEZERO_LON = 77.7;

const map = L.map('map', {
  crs: L.CRS.EPSG4326,
  minZoom: 0,
  maxZoom: 8
}).setView([JEZERO_LAT, JEZERO_LON], 6);

const marsTrekLayer = L.tileLayer(
  'https://trek.nasa.gov/tiles/Mars/EQ/Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg',
  {
    attribution: 'NASA/JPL-Caltech / Mars Trek',
    tileSize: 256,
    noWrap: true
  }
).addTo(map);

const molaLayer = L.tileLayer(
  'https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg',
  { attribution: 'NASA MGS/MOLA', tileSize: 256, noWrap: true }
);

L.control.layers(
  { "Mars Trek (visible)": marsTrekLayer },
  { "Relief MOLA": molaLayer }
).addTo(map);