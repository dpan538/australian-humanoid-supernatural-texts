import { readFile, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const repositoryRoot = process.cwd();
const sourcePath = path.join(repositoryRoot, "public/data/frontend-data.json");
const outputPath = path.join(repositoryRoot, "public/data/frontend-interactive.json");
const temporaryPath = `${outputPath}.tmp`;

const sourceText = await readFile(sourcePath, "utf8");
const source = JSON.parse(sourceText);

if (!Array.isArray(source.records) || !Array.isArray(source.map_flags)) {
  throw new Error("frontend-data.json is missing records or map_flags");
}

const recordIds = new Set(source.records.map((record) => record.record_id));
const orphanMapFlags = source.map_flags.filter((flag) => !recordIds.has(flag.record_id));
if (orphanMapFlags.length) {
  throw new Error(`interactive projection refused ${orphanMapFlags.length} orphan map flags`);
}

const projection = {
  ...source,
  locations: [],
  map_points: [],
  broad_locations: [],
};

const outputText = JSON.stringify(projection);
await writeFile(temporaryPath, outputText);
await rename(temporaryPath, outputPath);

const outputStats = await stat(outputPath);
const reduction = 1 - outputStats.size / Buffer.byteLength(sourceText);

console.log(
  JSON.stringify(
    {
      source: path.relative(repositoryRoot, sourcePath),
      output: path.relative(repositoryRoot, outputPath),
      records: projection.records.length,
      map_flags: projection.map_flags.length,
      source_bytes: Buffer.byteLength(sourceText),
      output_bytes: outputStats.size,
      byte_reduction_percent: Number((reduction * 100).toFixed(1)),
    },
    null,
    2,
  ),
);
