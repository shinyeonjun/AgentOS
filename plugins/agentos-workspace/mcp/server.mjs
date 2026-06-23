import path from "node:path";
import { pluginRootFromImportMeta, runPythonMcp } from "./python-bridge.mjs";

const pluginRoot = pluginRootFromImportMeta(import.meta.url);
const scriptPath = path.join(pluginRoot, "agentos_mcp_launcher.py");

runPythonMcp({ pluginRoot, scriptPath });
