import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import process from "node:process";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "..");

function withDefault(env, key, value) {
  if (env[key] !== undefined && env[key] !== null && String(env[key]).trim() !== "") return env;
  return { ...env, [key]: value };
}

function spawnLogged(name, command, args, opts) {
  const child = spawn(command, args, {
    ...opts,
    stdio: "inherit",
    env: opts?.env || process.env
  });
  child.on("exit", (code, signal) => {
    // Surface unexpected exits (Playwright will also fail if the webServer quits).
    if (!shuttingDown) {
      console.error(`[e2e] ${name} exited (code=${code ?? "null"}, signal=${signal ?? "null"})`);
      shutdown(code ?? 1);
    }
  });
  return child;
}

let shuttingDown = false;
let backend = null;
let web = null;

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;

  try {
    if (web && !web.killed) web.kill("SIGTERM");
  } catch {}
  try {
    if (backend && !backend.killed) backend.kill("SIGTERM");
  } catch {}

  const killTimer = setTimeout(() => {
    try {
      if (web && !web.killed) web.kill("SIGKILL");
    } catch {}
    try {
      if (backend && !backend.killed) backend.kill("SIGKILL");
    } catch {}
  }, 5000);
  killTimer.unref?.();

  // Give children a moment to flush logs, but don't hang forever.
  setTimeout(() => process.exit(code), 250).unref?.();
}

process.on("SIGINT", () => shutdown(130));
process.on("SIGTERM", () => shutdown(143));

const backendEnv0 = { ...process.env };
let backendEnv = backendEnv0;
backendEnv = withDefault(backendEnv, "INVITE_ENABLED", "0");
backendEnv = withDefault(backendEnv, "DISABLE_WORKER", "1");
backendEnv = withDefault(backendEnv, "OUTPUT_DIR", "output/e2e");
backendEnv = withDefault(backendEnv, "AUTH_SECRET_KEY", "dev");
backendEnv = withDefault(backendEnv, "OVERLOAD_MAX_INFLIGHT_REQUESTS", "0");

const pythonPath = path.resolve(repoRoot, "src");
backendEnv = {
  ...backendEnv,
  PYTHONPATH: backendEnv.PYTHONPATH ? `${pythonPath}:${backendEnv.PYTHONPATH}` : pythonPath
};

const pythonExe = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
backend = spawnLogged("backend", pythonExe, ["-m", "autosedance.main", "server", "--host", "127.0.0.1", "--port", "8000"], {
  cwd: repoRoot,
  env: backendEnv
});

const webEnv0 = { ...process.env };
let webEnv = webEnv0;
webEnv = withDefault(webEnv, "BACKEND_INTERNAL_URL", "http://127.0.0.1:8000/api");

web = spawnLogged("web", process.platform === "win32" ? "npm.cmd" : "npm", ["run", "start"], {
  cwd: webRoot,
  env: webEnv
});

// Keep the parent process alive until Playwright terminates it.
setInterval(() => {}, 60_000).unref?.();
