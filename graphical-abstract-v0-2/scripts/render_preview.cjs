#!/usr/bin/env node
'use strict';

// SVG-to-PNG renderer. This script never changes the input SVG.
// Requires Sharp: npm install sharp, or pass --sharp-module /path/to/sharp.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const usage = `Usage: node render_preview.cjs INPUT.svg OUTPUT.png [options]

Options:
  --width N             Output width in pixels (default: 3600)
  --height N            Output height; omit to preserve the SVG aspect ratio
  --density N           PNG print-resolution metadata in ppi (default: 300)
  --sharp-module PATH   Explicit Sharp module directory; otherwise require('sharp')
  --help                Show this help

SVG is rasterized directly at the final resolution. Explicit width and height
use 'contain' with a transparent margin if their ratio differs from the SVG.
Embedded raster images retain their original detail; this does not vectorize them.
Input and output must be different, and an existing output is never overwritten.
`;

function fail(message) { throw new Error(message); }
function integer(value, name, maximum = 20000) {
  if (!/^\d+$/.test(value || '') || Number(value) < 1 || Number(value) > maximum) {
    fail(`${name} must be an integer between 1 and ${maximum}.`);
  }
  return Number(value);
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help')) { process.stdout.write(usage); return; }
  if (argv.length < 2 || argv[0].startsWith('--') || argv[1].startsWith('--')) fail(usage);
  const input = path.resolve(argv[0]);
  const output = path.resolve(argv[1]);
  const options = { width: 3600, density: 300 };
  const seen = new Set();
  for (let i = 2; i < argv.length; i += 2) {
    const flag = argv[i];
    if (!['--width', '--height', '--density', '--sharp-module'].includes(flag)) fail(`Unknown option: ${flag}\n${usage}`);
    if (seen.has(flag)) fail(`Duplicate option: ${flag}`);
    seen.add(flag);
    if (argv[i + 1] === undefined) fail(`Missing value for ${flag}.`);
    const name = flag.slice(2);
    options[name] = name === 'sharp-module' ? argv[i + 1] : integer(argv[i + 1], flag, name === 'density' ? 10000 : 20000);
  }
  if (input === output) fail('Input and output must be different files.');
  if (!input.toLowerCase().endsWith('.svg') || !output.toLowerCase().endsWith('.png')) fail('Input must be .svg and output must be .png.');
  if (fs.existsSync(output)) fail('Output already exists; choose a new output path.');
  let sharp;
  try { sharp = require(options['sharp-module'] ? path.resolve(options['sharp-module']) : 'sharp'); }
  catch (error) { fail(`Sharp could not be loaded. Install it with npm install sharp or supply --sharp-module PATH.\n${error.message}`); }
  const svg = fs.readFileSync(input);
  const info = await sharp(svg, { density: 72 }).metadata();
  if (info.format !== 'svg' || !info.width || !info.height) fail('Input must be an SVG with a measurable width/height or viewBox.');
  const width = options.width;
  const height = options.height || Math.max(1, Math.round(width * info.height / info.width));
  if (height > 20000 || width * height > 100000000) fail('Requested image is too large (maximum dimension 20000; maximum area 100 million pixels).');
  // libvips/librsvg applies this density while rasterizing the vector, before resize.
  const renderDensity = 72 * Math.min(width / info.width, height / info.height);
  if (renderDensity > 100000) fail('SVG intrinsic size is too small for the requested output; normalize its width/height first.');
  const png = await sharp(svg, { density: renderDensity, limitInputPixels: 100000000 })
    .resize(width, height, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .withMetadata({ density: options.density })
    .png()
    .toBuffer();
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, png, { flag: 'wx' });
  const result = await sharp(png).metadata();
  process.stdout.write(JSON.stringify({
    input, output, width: result.width, height: result.height, density_ppi: result.density,
    source_sha256: crypto.createHash('sha256').update(svg).digest('hex'),
    output_sha256: crypto.createHash('sha256').update(png).digest('hex'),
    source_svg_unchanged: true,
    embedded_raster_note: 'Any embedded raster image retains its original detail.'
  }, null, 2) + '\n');
}

main().catch(error => { process.stderr.write(`error: ${error.message}\n`); process.exitCode = 2; });
