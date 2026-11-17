// Copies the generated reports into public/ so the dashboard reads exactly what the README reads.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
mkdirSync("public", { recursive: true });
for (const f of ["dev.json", "heldout.json"]) {
  const src = `../reports/${f}`;
  if (existsSync(src)) copyFileSync(src, `public/${f}`);
}
