/* One-off syntax validator for DIAGRAM.md's mermaid blocks (run with node).
   Uses jsdom as a DOM shim because mermaid's sanitizer needs a DOM in Node. */
import { JSDOM } from "jsdom";
import fs from "node:fs";

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.DOMPurify = { addHook: () => {}, sanitize: (x) => x };
Object.defineProperty(globalThis, "navigator", { value: { userAgent: "node" }, configurable: true });

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false });

const text = fs.readFileSync(new URL("../DIAGRAM.md", import.meta.url), "utf8");
const blocks = [...text.matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1]);
console.log("found", blocks.length, "mermaid blocks");
let failed = false;
for (let i = 0; i < blocks.length; i++) {
  try {
    await mermaid.parse(blocks[i]);
    console.log(`block ${i + 1}: OK`);
  } catch (error) {
    failed = true;
    console.log(`block ${i + 1}: SYNTAX ERROR →`, String(error.message).slice(0, 300));
  }
}
process.exit(failed ? 1 : 0);
