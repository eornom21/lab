// Builds talk maps as standalone SVG files (rendered to PNG by render.js).
const fs = require('fs');
const d3 = require('d3-geo');
const topo = require('topojson-client');
const us = JSON.parse(fs.readFileSync(__dirname + '/node_modules/us-atlas/states-10m.json'));
const states = topo.feature(us, us.objects.states).features;
const FIPS = {"01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE","11":"DC","12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY","72":"PR"};
const W = 1664, H = 960;
const proj = d3.geoAlbersUsa().fitExtent([[20, 20], [W - 20, H - 20]], {type: "FeatureCollection", features: states.filter(f => FIPS[f.id] !== "PR")});
const path = d3.geoPath(proj);
const C = {bg: "#F6F3EC", land: "#E9E3D6", line: "#FFFDF8", ink: "#1B2A41", body: "#4A5568", rep: "#B5451B", dem: "#2E5E9E", teal: "#2E6F8E", grey: "#C9C2B4"};
const font = "font-family=\"IBM Plex Sans, Helvetica, Arial, sans-serif\"";
function base(fill) {
  return states.filter(f => FIPS[f.id] !== "PR").map(f => `<path d="${path(f)}" fill="${fill(FIPS[f.id])}" stroke="${C.line}" stroke-width="1.5"/>`).join("");
}
function svg(body) { return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" ${font}><rect width="${W}" height="${H}" fill="${C.bg}"/>${body}</svg>`; }

// ---- Map A: Tuesday's toss-ups ----
const T = [ // [district, lat, lon, holder party, featured label or null, label anchor dx, dy]
 ["AL-2",32.37,-86.30,"D","AL-2 Figures",14,30],["AZ-6",32.22,-110.97,"R","AZ-6 Ciscomani",-14,32],["CA-22",35.37,-119.02,"R","CA-22 Valadao",-14,30],
 ["CO-5",38.83,-104.82,"R"],["CO-8",40.20,-104.80,"R"],["FL-14",27.95,-82.46,"D"],["FL-22",26.50,-80.10,"D"],["FL-25",26.10,-80.30,"D"],
 ["IA-2",42.50,-92.30,"R"],["KY-6",38.04,-84.50,"R"],["MI-4",42.29,-85.59,"R"],["MI-7",42.73,-84.55,"R"],["MI-10",42.60,-82.90,"R"],["MO-2",38.60,-90.50,"R"],
 ["MT-1",46.87,-113.99,"R"],["NC-1",35.61,-77.37,"D","NC-1 Davis",16,6],["NC-11",35.60,-82.55,"R"],["NY-17",41.10,-73.90,"R","NY-17 Lawler",-10,-26],
 ["OH-7",41.00,-81.90,"R"],["OH-9",41.65,-83.54,"D"],["PA-1",40.30,-75.10,"R"],["PA-8",41.41,-75.66,"R"],["PA-10",40.27,-76.88,"R","PA-10 Perry",-18,44],
 ["TX-15",26.30,-98.20,"R","TX-15 De La Cruz",-14,0],["TX-34",25.90,-97.50,"D"],["TX-35",29.40,-98.50,"D"],["VA-1",37.90,-76.90,"R"],["VA-2",36.85,-76.00,"R"],
 ["VA-5",38.03,-78.48,"R"],["WA-3",45.64,-122.66,"D"],["WI-3",44.30,-91.20,"R"],
 ["CA-13",37.30,-120.70,"D","CA-13 Gray",-14,-16]
];
let dots = "", labels = "";
T.forEach(([d, lat, lon, p, lab, dx, dy]) => {
  const xy = proj([lon, lat]); if (!xy) return;
  const r = lab ? 17 : 12, col = p === "D" ? C.dem : C.rep;
  dots += `<circle cx="${xy[0].toFixed(1)}" cy="${xy[1].toFixed(1)}" r="${r}" fill="${col}" stroke="${C.bg}" stroke-width="3" opacity="${lab ? 1 : .8}"/>`;
  if (lab) labels += `<text x="${(xy[0] + dx).toFixed(1)}" y="${(xy[1] + dy).toFixed(1)}" font-size="30" font-weight="600" fill="${C.ink}" text-anchor="${dx < 0 ? "end" : "start"}" paint-order="stroke" stroke="${C.bg}" stroke-width="7">${lab}</text>`;
});
fs.writeFileSync(__dirname + "/map_tossups.svg", svg(base(() => C.land) + dots + labels));

// ---- Map B: the 2025-26 redistricting war ----
const RD = {TX:["rep","+5 R"],NC:["rep","+1 R"],OH:["rep","+2 R"],FL:["rep","+4 R"],LA:["rep","+1 R"],TN:["rep","+1 R"],AL:["rep","+1 R"],CA:["dem","+5 D"],UT:["teal","+1 D"],MO:["block","blocked"],VA:["block","blocked"]};
const fillB = s => RD[s] ? ({rep: C.rep, dem: C.dem, teal: C.teal, block: C.grey})[RD[s][0]] : C.land;
let tags = "";
const LBL = {TX:[-99,31.5],NC:[-79.2,35.5],OH:[-82.7,40.3],FL:[-81.35,28.0],LA:[-92.5,30.55],TN:[-86.4,35.85],AL:[-86.8,32.8],CA:[-119.6,37.2],UT:[-111.6,39.3],MO:[-92.5,38.4],VA:[-78.6,37.5]};
Object.entries(LBL).forEach(([s, [lon, lat]]) => { const xy = proj([lon, lat]);
  tags += `<text x="${xy[0].toFixed(1)}" y="${xy[1].toFixed(1)}" font-size="${RD[s][1] === "blocked" ? 22 : 28}" font-weight="700" fill="${RD[s][0] === "block" ? C.ink : "#FFFDF8"}" text-anchor="middle" dominant-baseline="middle">${RD[s][1]}</text>`; });
fs.writeFileSync(__dirname + "/map_redistricting.svg", svg(base(fillB) + tags));
console.log("ok", fs.statSync(__dirname + "/map_tossups.svg").size, fs.statSync(__dirname + "/map_redistricting.svg").size);
