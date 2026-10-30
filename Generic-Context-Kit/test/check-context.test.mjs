import { test } from 'node:test';
import assert from 'node:assert/strict';
import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { applyPlan, planInit } from '../tools/eck.mjs';
import { formatReport, hasFailed, parseDate, parseHeader, runCheck } from '../tools/check-context.mjs';

const TODAY = '2026-10-27';

/** Creates a freshly initialised project in a temporary folder. */
function project(t, profile = 'generic') {
  const dir = mkdtempSync(join(tmpdir(), 'eck-check-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  applyPlan(
    planInit(dir, {
      name: 'Check Project',
      client: 'Example Client',
      owner: 'Technical lead',
      profile,
      reviewDays: 90,
      today: TODAY,
      force: false,
    }),
  );
  return dir;
}

function file(dir, rel) {
  return join(dir, ...rel.split('/'));
}

function edit(dir, rel, from, to) {
  const text = readFileSync(file(dir, rel), 'utf8');
  assert.ok(text.includes(from), `${rel} contains ${from}`);
  writeFileSync(file(dir, rel), text.replace(from, to));
}

function messagesFor(items, rel) {
  return items.filter((item) => item.file === rel).map((item) => item.message);
}

test('parseHeader reads the first table row', () => {
  const header = parseHeader('# Title\n\n| Owner | Last reviewed | Status |\n| --- | --- | --- |\n| Jo | 2026-01-01 | Draft |\n');
  assert.deepEqual(header, { Owner: 'Jo', 'Last reviewed': '2026-01-01', Status: 'Draft' });
  assert.equal(parseHeader('# Title\n\nNo table here.\n'), null);
});

test('parseDate accepts only real YYYY-MM-DD dates', () => {
  assert.equal(parseDate('2026-10-27'), Date.UTC(2026, 9, 27));
  assert.equal(parseDate('2026-02-30'), null);
  assert.equal(parseDate('27/10/2026'), null);
  assert.equal(parseDate(''), null);
});

test('a fresh project has no errors, and the report says it passed', (t) => {
  const result = runCheck(project(t), { today: TODAY });
  assert.deepEqual(result.errors, []);
  assert.match(formatReport(result), /Context check passed/);
  assert.equal(hasFailed(result), false);
  assert.equal(hasFailed(result, true), true, 'strict mode fails on Draft warnings');
});

test('reports missing context files and entry points', (t) => {
  const dir = project(t);
  rmSync(file(dir, 'context/architecture.md'));
  rmSync(file(dir, '.github/copilot-instructions.md'));
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/architecture.md')[0], /Missing/);
  assert.match(messagesFor(errors, '.github/copilot-instructions.md')[0], /Missing/);
});

test('reports a missing kit.json and checks the default file list', (t) => {
  const dir = project(t);
  rmSync(file(dir, 'context/kit.json'));
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/kit.json')[0], /Missing/);
  assert.deepEqual(messagesFor(errors, 'context/architecture.md'), []);
});

test('reports unresolved placeholders with their line', (t) => {
  const dir = project(t);
  appendFileSync(file(dir, 'context/project-overview.md'), '\nThe client is {{CLIENT_NAME}}.\n');
  const errors = runCheck(dir, { today: TODAY }).errors.filter((item) => item.file === 'context/project-overview.md');
  assert.equal(errors.length, 1);
  assert.match(errors[0].message, /Unresolved placeholder \{\{CLIENT_NAME\}\}/);
  assert.ok(errors[0].line > 1);
});

test('an Active file with FILL comments left is an error', (t) => {
  const dir = project(t);
  edit(dir, 'context/architecture.md', '| Draft |', '| Active |');
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/architecture.md')[0], /Status is Active but \d+ FILL comments remain/);
});

test('an unknown status is an error', (t) => {
  const dir = project(t);
  edit(dir, 'context/code-standards.md', '| Draft |', '| Finished |');
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/code-standards.md')[0], /Status "Finished"/);
});

test('files marked Not applicable are skipped', (t) => {
  const dir = project(t);
  edit(dir, 'context/ui-context.md', '| Draft |', '| Not applicable |');
  const result = runCheck(dir, { today: TODAY });
  assert.deepEqual(messagesFor(result.errors, 'context/ui-context.md'), []);
  assert.deepEqual(messagesFor(result.warnings, 'context/ui-context.md'), []);
});

test('warns when a review is overdue', (t) => {
  const dir = project(t);
  const { warnings } = runCheck(dir, { today: '2027-06-01' });
  assert.ok(messagesFor(warnings, 'context/progress-tracker.md').some((message) => /Last reviewed 217 days ago/.test(message)));
});

test('warns when no owner is set', (t) => {
  const dir = project(t);
  edit(dir, 'context/architecture.md', '| Technical lead |', '| TBC |');
  const { warnings } = runCheck(dir, { today: TODAY });
  assert.ok(messagesFor(warnings, 'context/architecture.md').includes('No owner is set.'));
});

test('reports likely secrets but ignores obvious examples', (t) => {
  const dir = project(t);
  const awsKey = `AKIA${'ABCDEFGHIJKLMNOP'}`;
  appendFileSync(
    file(dir, 'context/modules/integrations.md'),
    [
      '',
      `Access key: ${awsKey}`,
      'Server=db;Database=site;User Id=web;Password=Sup3rS3cretValue;',
      'Server=db;Password=changeme;',
      'api_key: "your-example-key-goes-here"',
      '',
    ].join('\n'),
  );
  const messages = messagesFor(runCheck(dir, { today: TODAY }).errors, 'context/modules/integrations.md');
  assert.equal(messages.length, 2, messages.join('\n'));
  assert.ok(messages.some((message) => /AWS access key/.test(message)));
  assert.ok(messages.some((message) => /password in a connection string/.test(message)));
});

test('checks unit specs: a Ready spec must be complete', (t) => {
  const dir = project(t);
  const spec = (status) =>
    `# Unit 01: Foundation\n\n| Owner | Status | Build plan |\n| --- | --- | --- |\n| Tech lead | ${status} | x |\n\n<!-- FILL: Goal -->\n`;

  writeFileSync(file(dir, 'context/specs/01-foundation.md'), spec('Spec in review'));
  assert.deepEqual(messagesFor(runCheck(dir, { today: TODAY }).errors, 'context/specs/01-foundation.md'), []);

  writeFileSync(file(dir, 'context/specs/01-foundation.md'), spec('Ready'));
  assert.match(messagesFor(runCheck(dir, { today: TODAY }).errors, 'context/specs/01-foundation.md')[0], /Status is Ready/);

  writeFileSync(file(dir, 'context/specs/01-foundation.md'), spec('Started'));
  assert.match(messagesFor(runCheck(dir, { today: TODAY }).errors, 'context/specs/01-foundation.md')[0], /Status "Started"/);
});

test('checks decision records but not the template', (t) => {
  const dir = project(t);
  writeFileSync(
    file(dir, 'context/decisions/ADR-0001-hosting.md'),
    '# ADR-0001: Hosting\n\n| Status | Date | Deciders |\n| --- | --- | --- |\n| Maybe | 2026-10-27 | Tech lead |\n',
  );
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/decisions/ADR-0001-hosting.md')[0], /Status "Maybe"/);
  assert.deepEqual(messagesFor(errors, 'context/decisions/ADR-0000-template.md'), []);
});

test('checks brand files but not the template or README', (t) => {
  const dir = project(t);
  writeFileSync(file(dir, 'context/brands/brand-a.md'), '# Brand A\n\nNo header table here.\n');
  writeFileSync(
    file(dir, 'context/brands/brand-b.md'),
    '# Brand B\n\n| Owner | Last reviewed | Status |\n| --- | --- | --- |\n| Brand lead | 2026-10-27 | Draft |\n\n<!-- FILL: Personality -->\n',
  );
  const result = runCheck(dir, { today: TODAY });
  assert.ok(messagesFor(result.errors, 'context/brands/brand-a.md').length > 0, 'a brand file without a header is an error');
  assert.deepEqual(messagesFor(result.errors, 'context/brands/brand-b.md'), []);
  assert.ok(messagesFor(result.warnings, 'context/brands/brand-b.md').length > 0, 'a Draft brand file is a warning');
  assert.deepEqual(messagesFor(result.errors, 'context/brands/_brand-template.md'), []);
  assert.deepEqual(messagesFor(result.warnings, 'context/brands/_brand-template.md'), []);
  assert.deepEqual(messagesFor(result.errors, 'context/brands/README.md'), []);

  edit(dir, 'context/brands/brand-b.md', '| Draft |', '| Active |');
  assert.match(messagesFor(runCheck(dir, { today: TODAY }).errors, 'context/brands/brand-b.md')[0], /Status is Active but 1 FILL comment remains\./);
});

test('rejects unsafe paths in kit.json', (t) => {
  const dir = project(t);
  const kitPath = file(dir, 'context/kit.json');
  const kit = JSON.parse(readFileSync(kitPath, 'utf8'));
  kit.contextFiles = ['../outside.md'];
  writeFileSync(kitPath, JSON.stringify(kit));
  const { errors } = runCheck(dir, { today: TODAY });
  assert.match(messagesFor(errors, 'context/kit.json')[0], /relative paths inside the repository/);
});
