const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const FILES = ['core.py', 'presets.py', 'studies.py', 'api.py', 'validation.py'];
const INIT = 'from . import api, core, studies, presets, validation\nfrom .core import max_range, fly, Aircraft, FuelCell, Battery, Tank, isa\n\n__version__ = "1.0.0"\n';
let py = null;
async function boot(base) {
  importScripts(PYODIDE_URL + 'pyodide.js');
  postMessage({ type: 'progress', text: 'Starting Python runtime …' });
  py = await loadPyodide({ indexURL: PYODIDE_URL });
  py.FS.mkdirTree('/home/pyodide/h2volt');
  py.FS.writeFile('/home/pyodide/h2volt/__init__.py', INIT);
  for (const f of FILES) {
    const r = await fetch(base + 'python/h2volt/' + f + '?v=' + Date.now(), { cache: 'no-store' });
    if (!r.ok) throw new Error('python/h2volt/' + f + ' (HTTP ' + r.status + ') – is the folder python/h2volt uploaded?');
    py.FS.writeFile('/home/pyodide/h2volt/' + f, await r.text());
  }
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')\nfrom h2volt import api");
  return py.version;
}
onmessage = async e => {
  const { id, fn, args, base } = e.data;
  try {
    if (fn === 'boot') { const v = await boot(base); postMessage({ id, ok: true, data: { version: v } }); return; }
    py.globals.set('h2v_args', JSON.stringify(args || []));
    const out = py.runPython("import json\n_a = json.loads(h2v_args)\napi." + fn + "(*_a)");
    const j = JSON.parse(out);
    postMessage({ id, ok: j.ok, data: j.data, error: j.error });
  } catch (err) { postMessage({ id, ok: false, error: String(err && err.message || err) }); }
};
