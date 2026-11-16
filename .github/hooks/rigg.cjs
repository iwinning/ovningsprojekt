'use strict';
// Copilot workspace hooks. Store metadata only: no prompts, arguments or tool results.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const runtimeDir = path.join(root, '.ai-runtime');
const sessionsDir = path.join(root, 'sessions');
const mode = process.argv[2];

function input() {
  const raw = fs.readFileSync(0, 'utf8');
  return raw.trim() ? JSON.parse(raw) : {};
}
function out(value = {}) { process.stdout.write(JSON.stringify(value)); }
function git(...args) {
  try { return execFileSync('git', args, {cwd: root, encoding: 'utf8', timeout: 3000}).trim(); }
  catch { return '(unavailable)'; }
}
function ensure(dir) { fs.mkdirSync(dir, {recursive: true}); }
function snapshot(reason) {
  return {
    updatedAt: new Date().toISOString(), reason,
    branch: git('branch', '--show-current'),
    commit: git('rev-parse', '--short', 'HEAD'),
    changedFiles: git('status', '--short').split('\n').slice(0, 40).filter(Boolean)
  };
}
function save(reason, durable) {
  const s = snapshot(reason);
  ensure(runtimeDir);
  fs.writeFileSync(path.join(runtimeDir, 'state.json'), JSON.stringify(s, null, 2) + '\n');
  if (durable) {
    ensure(sessionsDir);
    fs.writeFileSync(path.join(sessionsDir, 'last-state.md'), [
      '# Senaste sessionsläge (automatiskt sammanställt)', '',
      '- Uppdaterat: ' + s.updatedAt,
      '- Orsak: ' + s.reason,
      '- Branch: ' + s.branch,
      '- Commit: ' + s.commit,
      '- Lokala ändringar:',
      ...(s.changedFiles.length ? s.changedFiles : ['(inga)']).map(x => '  - ' + x),
      '', 'Läs senaste daterade sessionsloggen i sessions/ för beslut och nästa steg.',
      'Detta är en teknisk ögonblicksbild, inte ett fullständigt samtalsminne.', ''
    ].join('\n'));
  }
}
try {
  const e = input();
  const tool = String(e.toolName || e.tool_name || '').toLowerCase();
  const args = e.toolArgs ?? e.tool_input ?? {};
  const text = typeof args === 'string' ? args : JSON.stringify(args);
  switch (mode) {
    case 'restore': {
      const f = path.join(sessionsDir, 'last-state.md');
      if (fs.existsSync(f)) return out({additionalContext: 'Tidigare sessionsläge:\n' + fs.readFileSync(f, 'utf8').slice(0, 3500)});
      return out({additionalContext: 'Läs senaste daterade sessionsloggen i sessions/ före arbetet.'});
    }
    case 'save': save('sessionEnd', true); return out();
    case 'checkpoint': save('preCompact', false); return out();
    case 'protect-tests': {
      if (!/^(bash|powershell|edit|create|apply_patch|str_replace_editor)$/.test(tool)) return out();
      const value = text.replace(/\\\\/g, '/');
      const tests = /(?:^|[^a-z])tests\//i.test(value);
      const remove = /(?:git\s+rm|rm\s+(-r|-rf|-fr)|remove-item|del\s+|rmdir\s+)/i.test(value);
      const deletePatch = /\*\*\*\s+Delete\s+File\s*:\s*[^\n]*tests\//i.test(value);
      const skip = /\b(?:describe|test|it)\.(?:skip|only)\s*\(|\b(?:xdescribe|xit|xtest)\s*\(/i.test(value);
      const removeDeclaration = /(?:^|\n|\\n)\s*-\s*(?:it|test|describe)\s*\(/i.test(value);
      if ((tests && remove) || deletePatch || (tests && (skip || removeDeclaration))) {
        return out({permissionDecision:'deny', permissionDecisionReason:'Testskydd: ta inte bort, isolera eller inaktivera befintliga tester. Ändra hellre produktionskoden.'});
      }
      return out();
    }
    case 'approve-risk': {
      if (!/^(bash|powershell)$/.test(tool)) return out();
      if (/git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f|docker\s+system\s+prune|npm\s+run\s+db:reset|drop\s+database|drop\s+table|remove-item\s+.*-recurse/i.test(text)) {
        return out({permissionDecision:'ask', permissionDecisionReason:'Riskabelt kommando: begär uttryckligt godkännande före körning.'});
      }
      return out();
    }
    case 'audit': {
      ensure(runtimeDir);
      fs.appendFileSync(path.join(runtimeDir, 'events.jsonl'), JSON.stringify({
        time: new Date().toISOString(), event: 'postToolUse', tool: tool.slice(0, 100)
      }) + '\n');
      if (/^(edit|create|apply_patch|str_replace_editor)$/.test(tool)) {
        const check = git('diff', '--check');
        if (check && check !== '(unavailable)') return out({additionalContext:'git diff --check: ' + check.slice(0, 500)});
      }
      return out();
    }
    default: throw new Error('Unknown mode: ' + mode);
  }
} catch (e) {
  process.stderr.write('Hook failure: ' + String(e.message || e) + '\n');
  process.exit(1);
}
