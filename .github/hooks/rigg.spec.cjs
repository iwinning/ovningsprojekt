'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const script = path.join(__dirname, 'rigg.cjs');
function run(mode, event) {
  const r = spawnSync(process.execPath, [script, mode], {
    input: JSON.stringify(event), encoding:'utf8', timeout:3000
  });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

test('rejects disabling a test in tests/', () => {
  assert.equal(run('protect-tests', {
    toolName:'edit', toolArgs:{path:'tests/orders.test.ts',new_string:'it.skip("pristest", () => {})'}
  }).permissionDecision, 'deny');
});
test('rejects removing a test file', () => {
  assert.equal(run('protect-tests', {
    toolName:'powershell', toolArgs:{command:'git rm tests/orders.test.ts'}
  }).permissionDecision, 'deny');
});
test('rejects explicit Delete File patch', () => {
  assert.equal(run('protect-tests', {
    toolName:'apply_patch',toolArgs:{patch:'*** Begin Patch\n*** Delete File: tests/orders.test.ts\n*** End Patch'}
  }).permissionDecision,'deny');
});
test('allows normal test additions', () => {
  assert.deepEqual(run('protect-tests', {
    toolName:'edit',toolArgs:{path:'tests/orders.test.ts',new_string:'it("new feature", () => {})'}
  }),{});
});
test('asks before resetting the local database', () => {
  assert.equal(run('approve-risk', {
    toolName:'powershell',toolArgs:{command:'npm run db:reset'}
  }).permissionDecision,'ask');
});
test('does not interrupt harmless commands', () => {
  assert.deepEqual(run('approve-risk', {
    toolName:'powershell',toolArgs:{command:'npm test'}
  }),{});
});
test('hook configuration has six handlers', () => {
  const config=JSON.parse(fs.readFileSync(path.join(__dirname,'rigg.json'),'utf8'));
  assert.equal(config.version,1);
  assert.equal(Object.values(config.hooks).flat().length,6);
});
