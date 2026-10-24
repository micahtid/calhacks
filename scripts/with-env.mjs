// Loads the shared repo-root env files, then runs the given command.
// Next.js only reads env files from the app's own directory, and in dev it resets
// process.env to what it saw at boot, so root vars must be set before it starts.
// Existing vars are never overridden: shell > .env.local > .env.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

for (const name of [".env.local", ".env"]) {
  const file = fileURLToPath(new URL(`../${name}`, import.meta.url));
  if (existsSync(file)) process.loadEnvFile(file);
}

const [cmd, ...args] = process.argv.slice(2);
const child = spawn(cmd, args, { stdio: "inherit", shell: true });
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));
