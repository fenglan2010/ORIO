const path = require("path");
const fs = require("fs");

const VENV_PYTHON_REL =
  process.platform === "win32"
    ? path.join(".venv", "Scripts", "python.exe")
    : path.join(".venv", "bin", "python");

/**
 * Walk upward from `startDir` looking for repo-root `.venv` Python (max `depth` levels).
 */
function findVenvPythonFrom(startDir, depth = 12) {
  if (!startDir) return null;
  let dir = path.resolve(startDir);
  for (let i = 0; i < depth; i += 1) {
    const candidate = path.join(dir, VENV_PYTHON_REL);
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/**
 * Search anchors in order (e.g. resourcesPath, exe dir, repo root).
 */
function findVenvPython(anchorDirs) {
  for (const anchor of anchorDirs) {
    const found = findVenvPythonFrom(anchor);
    if (found) return found;
  }
  return null;
}

function resolveBackendDir({ isPackaged, resourcesPath, appDir }) {
  if (isPackaged) {
    const bundled = path.join(resourcesPath, "backend");
    if (fs.existsSync(bundled)) {
      return bundled;
    }
  }
  const fromDesktop = path.join(path.resolve(appDir, ".."), "backend");
  if (fs.existsSync(fromDesktop)) {
    return fromDesktop;
  }
  throw new Error(
    isPackaged
      ? "未在安装目录中找到后端资源（resources/backend）。请重新安装或联系支持。"
      : "未找到 backend 目录。请在仓库根目录运行，或先构建桌面安装包。"
  );
}

function pathAnchorsForVenv({ isPackaged, resourcesPath, execPath, appDir }) {
  if (isPackaged) {
    return [
      resourcesPath,
      path.dirname(execPath),
      path.resolve(appDir, ".."),
    ].filter(Boolean);
  }
  return [path.resolve(appDir, ".."), appDir];
}

function defaultDistribution(isPackaged) {
  return isPackaged ? "packaged" : "source";
}

module.exports = {
  findVenvPython,
  findVenvPythonFrom,
  resolveBackendDir,
  pathAnchorsForVenv,
  defaultDistribution,
};