import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEFAULT_PROFILE, KIT_VERSION, applyPlan, listProfiles, loadProfile, planInit, renderTemplate } from '../tools/eck.mjs';
import { runCheck } from '../tools/check-context.mjs';

const KIT_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ECK = join(KIT_ROOT, 'tools', 'eck.mjs');
const TODAY = '2026-10-27';

function tempDir(t) {
  const dir = mkdtempSync(join(tmpdir(), 'eck-test-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function answers(overrides = {}) {
  return {
    name: 'Test Project',
    client: 'Example Client',
    owner: 'Technical lead',
    profile: 'generic',
    reviewDays: 90,
    today: TODAY,
    force: false,
    ...overrides,
  };
}

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walk(path));
    else files.push(path);
  }
  return files;
}

function eck(args, options = {}) {
  return spawnSync(process.execPath, [ECK, ...args], { encoding: 'utf8', ...options });
}

function contentOf(plan, rel) {
  const item = plan.find((entry) => entry.rel === rel);
  assert.ok(item, `${rel} is in the plan`);
  return item.content;
}

test('lists the generic profile, which is the default', () => {
  const ids = listProfiles().map((profile) => profile.id);
  assert.ok(ids.includes('generic'));
  assert.equal(DEFAULT_PROFILE, 'generic');
  assert.deepEqual(
    loadProfile('generic').chain.map((profile) => profile.id),
    ['generic'],
  );
});

test('rejects unknown and invalid profile ids', () => {
  assert.throws(() => loadProfile('does-not-exist'), /Unknown profile/);
  assert.throws(() => loadProfile('../generic'), /not a valid profile id/);
});

test('renderTemplate replaces tokens and removes lines whose token is empty', () => {
  const tokens = { NAME: 'Acme', EMPTY: '', LIST: '  - one\n  - two' };
  assert.equal(renderTemplate('Hello {{NAME}}.\n', tokens), 'Hello Acme.\n');
  assert.equal(renderTemplate('a\n{{EMPTY}}\nb\n', tokens), 'a\nb\n');
  assert.equal(renderTemplate('Paths:\n{{LIST}}\nend\n', tokens), 'Paths:\n  - one\n  - two\nend\n');
  assert.equal(renderTemplate('a\r\nb {{NAME}}\r\n', tokens), 'a\nb Acme\n');
  assert.throws(() => renderTemplate('{{MISSING}}', tokens, 'x.md'), /x\.md uses \{\{MISSING\}\}/);
});

test('every profile renders with no unresolved tokens', (t) => {
  const dir = tempDir(t);
  for (const { id } of listProfiles()) {
    const plan = planInit(dir, answers({ profile: id }));
    for (const item of plan.filter((entry) => entry.rel.endsWith('.md') || entry.rel.endsWith('.json'))) {
      assert.doesNotMatch(item.content, /\{\{[A-Z][A-Z0-9_]*\}\}/, `${id}: ${item.rel} has an unresolved token`);
    }
  }
});

test('templates never put a token inside a FILL comment', () => {
  const sources = [...walk(join(KIT_ROOT, 'scaffold')), ...walk(join(KIT_ROOT, 'profiles'))].filter((file) =>
    file.endsWith('.md'),
  );
  assert.ok(sources.length > 20);
  for (const file of sources) {
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(/<!--\s*FILL:[\s\S]*?-->/g)) {
      assert.doesNotMatch(match[0], /\{\{/, `${file} has a token inside a FILL comment`);
    }
  }
});

test('the generic profile records the kit and adds no stack-specific commands', (t) => {
  const plan = planInit(tempDir(t), answers({ profile: 'generic' }));
  assert.doesNotMatch(contentOf(plan, 'AGENTS.md'), /dotnet/);

  const kit = JSON.parse(contentOf(plan, 'context/kit.json'));
  assert.equal(kit.kitVersion, KIT_VERSION);
  assert.equal(kit.profile.id, 'generic');
  assert.ok(kit.managedFiles.includes('context/check-context.mjs'));
});

test('a freshly initialised project passes the context check', (t) => {
  for (const { id: profile } of listProfiles()) {
    const dir = tempDir(t);
    applyPlan(planInit(dir, answers({ profile })));
    const result = runCheck(dir, { today: TODAY });
    assert.deepEqual(result.errors, [], `${profile}: no errors`);
    assert.ok(result.warnings.length > 0, `${profile}: Draft files are reported as warnings`);
  }
});

test('existing files are kept and the kit version is written alongside', (t) => {
  const dir = tempDir(t);
  writeFileSync(join(dir, 'AGENTS.md'), '# Our own instructions\n');
  const plan = planInit(dir, answers());
  assert.equal(plan.find((item) => item.rel === 'AGENTS.md').action, 'conflict');
  applyPlan(plan);
  assert.equal(readFileSync(join(dir, 'AGENTS.md'), 'utf8'), '# Our own instructions\n');
  assert.match(readFileSync(join(dir, 'AGENTS.md.kit-new'), 'utf8'), /Agent Instructions/);
});

test('--force overwrites existing files', (t) => {
  const dir = tempDir(t);
  writeFileSync(join(dir, 'AGENTS.md'), '# Our own instructions\n');
  const plan = planInit(dir, answers({ force: true }));
  assert.equal(plan.find((item) => item.rel === 'AGENTS.md').action, 'overwrite');
  applyPlan(plan);
  assert.match(readFileSync(join(dir, 'AGENTS.md'), 'utf8'), /Agent Instructions/);
  assert.ok(!existsSync(join(dir, 'AGENTS.md.kit-new')));
});

test('running init again with the same answers changes nothing', (t) => {
  const dir = tempDir(t);
  applyPlan(planInit(dir, answers()));
  const again = planInit(dir, answers());
  assert.deepEqual([...new Set(again.map((item) => item.action))], ['unchanged']);
});

test('eck init and eck check work from the command line', (t) => {
  const dir = tempDir(t);
  const init = eck(['init', dir, '--yes', '--profile', 'generic', '--name', 'CLI Project', '--owner', 'Tech lead']);
  assert.equal(init.status, 0, init.stderr);
  assert.match(init.stdout, /Next steps/);
  assert.ok(existsSync(join(dir, 'context', 'kit.json')));
  assert.match(readFileSync(join(dir, 'AGENTS.md'), 'utf8'), /^# CLI Project: Agent Instructions/);

  const check = eck(['check', dir]);
  assert.equal(check.status, 0, check.stdout);
  assert.match(check.stdout, /Context check passed/);

  const strict = eck(['check', dir, '--strict']);
  assert.equal(strict.status, 1, 'Draft warnings fail in strict mode');

  const standalone = spawnSync(process.execPath, [join('context', 'check-context.mjs'), '--json'], {
    cwd: dir,
    encoding: 'utf8',
  });
  assert.equal(standalone.status, 0, standalone.stdout);
  assert.equal(JSON.parse(standalone.stdout).passed, true);
});

test('eck --dry-run writes nothing', (t) => {
  const dir = tempDir(t);
  const result = eck(['init', dir, '--yes', '--dry-run']);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Dry run/);
  assert.deepEqual(readdirSync(dir), []);
});

test('eck reports usage errors with exit code 2', (t) => {
  const dir = tempDir(t);
  assert.equal(eck(['init', dir, '--yes', '--profile', 'nope']).status, 2);
  assert.equal(eck(['launch']).status, 2);
  assert.equal(eck(['init', dir, '--bogus']).status, 2);
  assert.equal(eck(['init', dir, '--yes', '--review-days', '0']).status, 2);
  assert.equal(eck(['init', dir, '--yes', '--name', 'Bad | name']).status, 2);
});

test('every skill has a valid name that matches its folder, and a description', () => {
  const roots = [join(KIT_ROOT, 'scaffold', '.agents', 'skills'), join(KIT_ROOT, 'skills')];
  let count = 0;
  for (const root of roots) {
    for (const entry of readdirSync(root, { withFileTypes: true }).filter((item) => item.isDirectory())) {
      const text = readFileSync(join(root, entry.name, 'SKILL.md'), 'utf8');
      const frontmatter = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
      assert.ok(frontmatter, `${entry.name}: has frontmatter`);
      const name = frontmatter[1].match(/^name:\s*(.+)$/m)?.[1].trim();
      const description = frontmatter[1].match(/^description:\s*(.+)$/m)?.[1].trim();
      assert.equal(name, entry.name, `${entry.name}: name matches the folder`);
      assert.match(name, /^[a-z0-9]+(-[a-z0-9]+)*$/, `${entry.name}: name is lowercase-hyphenated`);
      assert.ok(name.length <= 64, `${entry.name}: name is 64 characters or fewer`);
      assert.ok(description && description.length <= 1024, `${entry.name}: has a description of 1024 characters or fewer`);
      count += 1;
    }
  }
  assert.equal(count, 10, 'nine workflow skills and the kit skill');
});

test('every workflow skill has a playbook, a Copilot prompt and a row in AGENTS.md', () => {
  const scaffold = join(KIT_ROOT, 'scaffold');
  const agents = readFileSync(join(scaffold, 'AGENTS.md'), 'utf8');
  const copilot = readFileSync(join(scaffold, '.github', 'copilot-instructions.md'), 'utf8');
  const skills = readdirSync(join(scaffold, '.agents', 'skills'), { withFileTypes: true }).filter((item) => item.isDirectory());
  for (const { name } of skills) {
    const playbook = `context/playbooks/${name}.md`;
    assert.ok(existsSync(join(scaffold, ...playbook.split('/'))), `${name}: ${playbook} exists`);
    assert.ok(existsSync(join(scaffold, '.github', 'prompts', `${name}.prompt.md`)), `${name}: has a Copilot prompt`);
    const skill = readFileSync(join(scaffold, '.agents', 'skills', name, 'SKILL.md'), 'utf8');
    const prompt = readFileSync(join(scaffold, '.github', 'prompts', `${name}.prompt.md`), 'utf8');
    assert.ok(skill.includes(playbook), `${name}: the skill points to its playbook`);
    assert.ok(prompt.includes(playbook), `${name}: the prompt points to its playbook`);
    assert.ok(agents.includes(`\`${playbook}\``), `${name}: AGENTS.md lists the playbook`);
    assert.ok(copilot.includes(`/${name}`), `${name}: copilot-instructions.md lists the prompt`);
  }
});

test('brand files and the brand gates are part of a new project', (t) => {
  const dir = tempDir(t);
  const plan = planInit(dir, answers());
  assert.ok(plan.some((entry) => entry.rel === 'context/brands/README.md'));
  assert.ok(plan.some((entry) => entry.rel === 'context/brands/_brand-template.md'));
  const rules = contentOf(plan, 'context/ai-workflow-rules.md');
  assert.match(rules, /design token values/);
  assert.match(rules, /approved brand copy/);
  assert.match(rules, /context\/playbooks\/fix-small\.md/);
});

test('staging and go-live guidance is part of a new project', (t) => {
  const dir = tempDir(t);
  const plan = planInit(dir, answers());
  assert.ok(plan.some((entry) => entry.rel === 'context/modules/go-live.md'));
  assert.ok(plan.some((entry) => entry.rel === 'context/playbooks/prepare-release.md'));
  const goLive = contentOf(plan, 'context/modules/go-live.md');
  assert.match(goLive, /## Snag log/);
  assert.match(goLive, /## Cutover plan/);
  assert.match(goLive, /## Hypercare/);
  assert.match(contentOf(plan, 'context/specs/_unit-spec-template.md'), /## Release impact/);
  assert.match(contentOf(plan, 'context/modules/environments-delivery.md'), /## Environment parity/);
  assert.match(contentOf(plan, 'context/modules/quality-testing.md'), /## Before staging/);
  assert.match(contentOf(plan, 'context/playbooks/plan-build.md'), /production-like deployment/);
  assert.match(contentOf(plan, 'AGENTS.md'), /context\/playbooks\/prepare-release\.md/);
});

test('the team guides cover every workflow and status', (t) => {
  const plan = planInit(tempDir(t), answers());
  const howTo = contentOf(plan, 'context/HOW-TO-USE.md');
  assert.match(howTo, /^# How to Use the Context Files on Test Project/);
  assert.doesNotMatch(howTo, /<!--\s*FILL:/, 'the guide has no FILL comments');
  assert.match(contentOf(plan, 'context/README.md'), /`HOW-TO-USE\.md`/);
  assert.match(contentOf(plan, 'AGENTS.md'), /context\/HOW-TO-USE\.md/);

  const guide = readFileSync(join(KIT_ROOT, 'GUIDE.md'), 'utf8');
  assert.match(guide, /context\/HOW-TO-USE\.md/);
  assert.match(readFileSync(join(KIT_ROOT, 'README.md'), 'utf8'), /\(GUIDE\.md\)/);

  const skills = readdirSync(join(KIT_ROOT, 'scaffold', '.agents', 'skills'), { withFileTypes: true }).filter((item) =>
    item.isDirectory(),
  );
  for (const { name } of skills) {
    assert.ok(howTo.includes(`\`/${name}\``), `HOW-TO-USE.md lists /${name}`);
    assert.ok(guide.includes(`\`/${name}\``), `GUIDE.md lists /${name}`);
  }
  for (const status of ['Not started', 'Spec in review', 'Ready', 'In progress', 'In review', 'Done', 'Blocked']) {
    assert.ok(howTo.includes(`| ${status} |`), `HOW-TO-USE.md explains the ${status} status`);
  }
});

test('the skill and command reference lists every skill, command and option', (t) => {
  const plan = planInit(tempDir(t), answers());
  const reference = contentOf(plan, 'context/SKILLS-AND-COMMANDS.md');
  assert.match(reference, /^# Skills and Commands on Test Project/);
  assert.doesNotMatch(reference, /\{\{[A-Z][A-Z0-9_]*\}\}/, 'every token is filled in');
  assert.doesNotMatch(reference, /<!--\s*FILL:/, 'the reference has no FILL comments');
  assert.match(contentOf(plan, 'context/README.md'), /`SKILLS-AND-COMMANDS\.md`/);
  assert.match(contentOf(plan, 'AGENTS.md'), /context\/SKILLS-AND-COMMANDS\.md/);
  assert.match(contentOf(plan, 'context/HOW-TO-USE.md'), /context\/SKILLS-AND-COMMANDS\.md/);
  assert.match(readFileSync(join(KIT_ROOT, 'GUIDE.md'), 'utf8'), /context\/SKILLS-AND-COMMANDS\.md/);
  assert.match(readFileSync(join(KIT_ROOT, 'README.md'), 'utf8'), /SKILLS-AND-COMMANDS\.md/);

  const skills = readdirSync(join(KIT_ROOT, 'scaffold', '.agents', 'skills'), { withFileTypes: true }).filter((item) =>
    item.isDirectory(),
  );
  for (const { name } of skills) {
    assert.ok(reference.includes(`### \`${name}\``), `the reference has a section for ${name}`);
    assert.ok(reference.includes(`| \`${name}\` | \`/${name}\` |`), `the reference lists ${name} at a glance`);
    assert.ok(reference.includes(`context/playbooks/${name}.md`), `the reference points to the ${name} playbook`);
  }
  assert.match(reference, /`enterprise-context-kit`/, 'the reference covers the kit skill');
  assert.match(reference, /node context\/check-context\.mjs/);
  for (const option of ['--strict', '--json', '--root <folder>']) {
    assert.ok(reference.includes(`\`${option}\``), `the reference explains check option ${option}`);
  }
  for (const command of ['init <folder>', 'check <folder>', 'list', 'help', '--version']) {
    assert.ok(reference.includes(`\`node tools/eck.mjs ${command}\``), `the reference lists eck ${command}`);
  }
  for (const option of ['--name', '--client', '--owner', '--profile', '--review-days', '--yes', '--dry-run', '--force']) {
    assert.ok(reference.includes(`| \`${option}`), `the reference explains init option ${option}`);
  }
});

test('the kit can be run straight from Bitbucket with npx', () => {
  const pkg = JSON.parse(readFileSync(join(KIT_ROOT, 'package.json'), 'utf8'));
  assert.equal(pkg.bin.eck, 'tools/eck.mjs');
  for (const folder of ['tools/', 'scaffold/', 'profiles/']) {
    assert.ok(pkg.files.includes(folder), `package.json files includes ${folder}, which eck needs at run time`);
  }
  const script = readFileSync(join(KIT_ROOT, 'tools', 'eck.mjs'), 'utf8');
  assert.ok(script.startsWith('#!/usr/bin/env node\n'), 'eck.mjs starts with a shebang that ends in LF');
  assert.doesNotMatch(script, /KIT_ROOT, 'ci'/, 'init does not print paths inside the kit, which npx deletes');
  assert.match(readFileSync(join(KIT_ROOT, '.gitattributes'), 'utf8'), /\*\.mjs text eol=lf/);
});

test('eck --version prints the kit version', () => {
  const result = eck(['--version']);
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), KIT_VERSION);
});
