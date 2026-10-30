#!/usr/bin/env node
/**
 * eck: the Context Kit command-line tool.
 *
 *   eck init [folder]   Add the context scaffold to a new or existing repository
 *   eck check [folder]  Check a repository's context files
 *   eck list            List the stack profiles
 *
 * Uses Node.js built-ins only and needs Node.js 20 or later.
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import { formatReport, hasFailed, runCheck } from './check-context.mjs';

const KIT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SCAFFOLD_DIR = join(KIT_ROOT, 'scaffold');
const PROFILES_DIR = join(KIT_ROOT, 'profiles');
const CHECK_SCRIPT = join(KIT_ROOT, 'tools', 'check-context.mjs');

export const KIT_VERSION = JSON.parse(readFileSync(join(KIT_ROOT, 'package.json'), 'utf8')).version;
export const DEFAULT_PROFILE = 'generic';
const DEFAULT_REVIEW_DAYS = 90;
const TOKEN_NAME = /^[A-Z][A-Z0-9_]*$/;
const PROFILE_ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const IGNORED_FILES = new Set(['.DS_Store', 'Thumbs.db']);

const CORE_CONTEXT_FILES = [
  { path: 'context/project-overview.md', purpose: 'what is being built, for whom and why' },
  { path: 'context/architecture.md', purpose: 'the stack, structure and boundaries' },
  { path: 'context/code-standards.md', purpose: 'how code is written' },
  { path: 'context/ui-context.md', purpose: 'how the product looks and behaves' },
  { path: 'context/ai-workflow-rules.md', purpose: 'what agents may do, what needs approval and what they must never do' },
  { path: 'context/progress-tracker.md', purpose: 'the current state of the build and what is next' },
];
const MODULE_FILES = ['security-compliance', 'integrations', 'environments-delivery', 'quality-testing', 'operations', 'go-live'].map(
  (name) => `context/modules/${name}.md`,
);
const BUILD_PLAN = 'context/specs/00-build-plan.md';
const ENTRY_POINTS = ['AGENTS.md', '.github/copilot-instructions.md'];

const HELP = `Context Kit ${KIT_VERSION}

Usage:
  eck init [folder] [options]    Add the context scaffold to a repository
  eck check [folder] [options]   Check a repository's context files
  eck list                       List the stack profiles
  eck help                       Show this help

Init options:
  --name <text>        Project name (default: the folder name)
  --client <text>      Client name (default: TBC)
  --owner <text>       Person or role that owns the context files (default: TBC)
  --profile <id>       Stack profile (default: ${DEFAULT_PROFILE}). See "eck list".
  --review-days <n>    Days between context reviews (default: ${DEFAULT_REVIEW_DAYS})
  --yes, -y            Ask no questions; use the options given and the defaults
  --force              Overwrite existing files instead of writing .kit-new copies
  --dry-run            Show what would change without writing anything

Check options:
  --strict             Fail on warnings as well as errors
  --json               Print the result as JSON

Run from a clone of the kit:  node <kit folder>/tools/eck.mjs <command>
Run straight from Bitbucket:  npx --yes "git+https://bitbucket.org/<workspace>/enterprise-context-kit.git#v${KIT_VERSION}" <command>`;

export class UsageError extends Error {}

/** Returns the metadata of every profile, sorted by id. */
export function listProfiles() {
  return readdirSync(PROFILES_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && existsSync(join(PROFILES_DIR, entry.name, 'profile.json')))
    .map((entry) => loadProfile(entry.name).meta)
    .sort((a, b) => a.id.localeCompare(b.id));
}

/** Loads a profile and its parents. chain runs from the root profile to this one. */
export function loadProfile(id, seen = []) {
  if (!PROFILE_ID.test(id)) throw new UsageError(`"${id}" is not a valid profile id.`);
  const dir = join(PROFILES_DIR, id);
  const file = join(dir, 'profile.json');
  if (!existsSync(file)) throw new UsageError(`Unknown profile "${id}". Run "eck list" to see the profiles.`);
  if (seen.includes(id)) throw new Error(`Profile "${id}" extends itself through ${seen.join(' -> ')}.`);

  const meta = JSON.parse(readFileSync(file, 'utf8'));
  if (meta.id !== id) throw new Error(`profiles/${id}/profile.json has id "${meta.id}"; it must match the folder name.`);
  for (const key of ['name', 'description']) {
    if (typeof meta[key] !== 'string' || !meta[key].trim()) throw new Error(`profiles/${id}/profile.json needs a "${key}".`);
  }
  for (const extra of meta.extraContextFiles ?? []) {
    if (typeof extra.path !== 'string' || !extra.path.startsWith('context/') || typeof extra.purpose !== 'string') {
      throw new Error(`profiles/${id}/profile.json: each extraContextFiles entry needs a "path" in context/ and a "purpose".`);
    }
  }

  const parent = meta.extends ? loadProfile(meta.extends, [...seen, id]) : null;
  const chain = [...(parent?.chain ?? []), { id, dir, meta }];
  return { id, meta, chain };
}

/**
 * Works out every file that init would write, without writing anything.
 * Returns a list of { rel, abs, content, action }, where action is one of
 * create, unchanged, overwrite or conflict.
 */
export function planInit(target, answers) {
  const profile = loadProfile(answers.profile);
  const extras = profile.chain.flatMap((p) => p.meta.extraContextFiles ?? []);
  const readingList = orderReadingList(extras);

  const builtIns = {
    PROJECT_NAME: answers.name,
    CLIENT_NAME: answers.client,
    OWNER: answers.owner,
    TODAY: answers.today,
    KIT_VERSION,
    PROFILE_NAME: profile.meta.name,
    REVIEW_DAYS: String(answers.reviewDays),
    CONTEXT_READING_LIST: readingList.map((file, i) => `${i + 1}. \`${file.path}\`: ${file.purpose}`).join('\n'),
  };
  const profileTokens = collectTokens(profile);
  for (const name of Object.keys(profileTokens)) {
    if (name in builtIns) throw new Error(`Profile token ${name} has the same name as a built-in token.`);
  }
  const tokens = { ...profileTokens, ...builtIns };

  const sources = new Map();
  for (const rel of walk(SCAFFOLD_DIR)) sources.set(rel, join(SCAFFOLD_DIR, ...rel.split('/')));
  for (const p of profile.chain) {
    const filesDir = join(p.dir, 'files');
    if (!existsSync(filesDir)) continue;
    for (const rel of walk(filesDir)) sources.set(rel, join(filesDir, ...rel.split('/')));
  }
  for (const extra of extras) {
    if (!sources.has(extra.path)) throw new Error(`A profile lists ${extra.path} in extraContextFiles but does not provide it.`);
  }

  const outputs = new Map();
  for (const [rel, source] of sources) outputs.set(rel, renderTemplate(readText(source), tokens, rel));
  outputs.set('context/check-context.mjs', readText(CHECK_SCRIPT));

  const kit = {
    kitVersion: KIT_VERSION,
    profile: { id: profile.id, name: profile.meta.name },
    project: { name: answers.name, client: answers.client },
    createdOn: answers.today,
    reviewDays: answers.reviewDays,
    entryPoints: ENTRY_POINTS,
    contextFiles: [...readingList.map((file) => file.path), ...MODULE_FILES, BUILD_PLAN],
    managedFiles: [...outputs.keys(), 'context/kit.json'].sort(),
  };
  outputs.set('context/kit.json', `${JSON.stringify(kit, null, 2)}\n`);

  return [...outputs]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([rel, content]) => {
      const abs = join(target, ...rel.split('/'));
      let action = 'create';
      if (existsSync(abs)) {
        if (readText(abs) === content) action = 'unchanged';
        else action = answers.force ? 'overwrite' : 'conflict';
      }
      return { rel, abs, content, action };
    });
}

/** Writes a plan from planInit. Conflicting files are written alongside as .kit-new. */
export function applyPlan(plan) {
  for (const item of plan) {
    if (item.action === 'unchanged') continue;
    const path = item.action === 'conflict' ? `${item.abs}.kit-new` : item.abs;
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, item.content, 'utf8');
  }
}

/** Replaces {{TOKEN}} placeholders. Unknown tokens are a kit bug and stop init. */
export function renderTemplate(text, tokens, source = 'template') {
  const valueOf = (name) => {
    if (!(name in tokens)) throw new Error(`${source} uses {{${name}}}, which no profile or built-in token defines.`);
    return tokens[name];
  };
  return text
    .replace(/\r\n/g, '\n')
    .replace(/^[ \t]*\{\{([A-Z][A-Z0-9_]*)\}\}[ \t]*\n/gm, (_, name) => {
      const value = valueOf(name);
      return value ? `${value}\n` : '';
    })
    .replace(/\{\{([A-Z][A-Z0-9_]*)\}\}/g, (_, name) => valueOf(name));
}

function orderReadingList(extras) {
  const list = [...CORE_CONTEXT_FILES];
  for (const extra of extras) {
    if (list.some((file) => file.path === extra.path)) continue;
    const after = extra.after ? list.findIndex((file) => file.path === extra.after) : -1;
    list.splice(after === -1 ? list.length : after + 1, 0, { path: extra.path, purpose: extra.purpose });
  }
  return list;
}

function collectTokens(profile) {
  const tokens = {};
  for (const p of profile.chain) {
    const dir = join(p.dir, 'tokens');
    if (!existsSync(dir)) continue;
    for (const file of readdirSync(dir).filter((name) => name.endsWith('.md'))) {
      const name = file.slice(0, -3);
      if (!TOKEN_NAME.test(name)) throw new Error(`profiles/${p.id}/tokens/${file}: token names must be UPPER_SNAKE_CASE.`);
      tokens[name] = readText(join(dir, file)).replace(/^\n+/, '').trimEnd();
    }
  }
  return tokens;
}

function walk(dir, prefix = '') {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (IGNORED_FILES.has(entry.name)) continue;
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) files.push(...walk(join(dir, entry.name), rel));
    else if (entry.isFile()) files.push(rel);
  }
  return files.sort();
}

function readText(path) {
  return readFileSync(path, 'utf8').replace(/\r\n/g, '\n');
}

function localToday() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function cleanValue(label, value) {
  const text = String(value ?? '').trim();
  if (!text) throw new UsageError(`${label} cannot be empty.`);
  if (/[\r\n|]/.test(text) || text.includes('{{') || text.includes('<!--')) {
    throw new UsageError(`${label} cannot contain line breaks, "|", "{{" or "<!--".`);
  }
  return text;
}

function parseArgs(argv) {
  const valueFlags = { '--name': 'name', '--client': 'client', '--owner': 'owner', '--profile': 'profile', '--review-days': 'reviewDays' };
  const booleanFlags = {
    '--yes': 'yes', '-y': 'yes', '--force': 'force', '--dry-run': 'dryRun', '--strict': 'strict',
    '--json': 'json', '--help': 'help', '-h': 'help', '--version': 'version', '-v': 'version',
  };
  const options = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    let arg = argv[i];
    let inline;
    if (arg.startsWith('--') && arg.includes('=')) {
      inline = arg.slice(arg.indexOf('=') + 1);
      arg = arg.slice(0, arg.indexOf('='));
    }
    if (arg in valueFlags) {
      const value = inline ?? argv[++i];
      if (value === undefined || (inline === undefined && value.startsWith('-'))) throw new UsageError(`${arg} needs a value.`);
      options[valueFlags[arg]] = value;
    } else if (arg in booleanFlags) {
      if (inline !== undefined) throw new UsageError(`${arg} does not take a value.`);
      options[booleanFlags[arg]] = true;
    } else if (arg.startsWith('-')) {
      throw new UsageError(`Unknown option: ${arg}`);
    } else {
      options._.push(arg);
    }
  }
  return options;
}

async function askMissing(answers, target) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const ask = async (question, fallback) => (await rl.question(`${question} [${fallback}]: `)).trim() || fallback;
  try {
    answers.name ??= await ask('Project name', basename(target));
    answers.client ??= await ask('Client name', 'TBC');
    answers.owner ??= await ask('Context owner (person or role)', 'TBC');
    if (!answers.profile) {
      console.log('\nProfiles:');
      for (const p of listProfiles()) console.log(`  ${p.id.padEnd(10)} ${p.description}`);
      answers.profile = await ask('Profile', DEFAULT_PROFILE);
    }
    console.log('');
  } finally {
    rl.close();
  }
}

async function cmdInit(options) {
  const target = resolve(options._[1] ?? '.');
  if (existsSync(target) && !statSync(target).isDirectory()) throw new UsageError(`${target} is not a folder.`);

  const answers = { name: options.name, client: options.client, owner: options.owner, profile: options.profile };
  if (!options.yes && process.stdin.isTTY && process.stdout.isTTY) await askMissing(answers, target);

  answers.name = cleanValue('Project name', answers.name ?? basename(target));
  answers.client = cleanValue('Client name', answers.client ?? 'TBC');
  answers.owner = cleanValue('Owner', answers.owner ?? 'TBC');
  answers.profile = (answers.profile ?? DEFAULT_PROFILE).trim();
  answers.reviewDays = options.reviewDays === undefined ? DEFAULT_REVIEW_DAYS : Number(options.reviewDays);
  if (!Number.isInteger(answers.reviewDays) || answers.reviewDays < 1) {
    throw new UsageError('--review-days must be a whole number greater than 0.');
  }
  answers.today = localToday();
  answers.force = Boolean(options.force);

  const plan = planInit(target, answers);
  const profileName = loadProfile(answers.profile).meta.name;
  console.log(`Context Kit ${KIT_VERSION}, ${profileName} profile`);
  console.log(`Target: ${target}\n`);
  for (const item of plan) {
    const note = item.action === 'conflict' ? `  (kit version written to ${item.rel}.kit-new)` : '';
    console.log(`  ${item.action.padEnd(10)} ${item.rel}${note}`);
  }

  const count = (action) => plan.filter((item) => item.action === action).length;
  const conflicts = count('conflict');
  console.log(
    `\n${count('create')} to create, ${count('overwrite')} to overwrite, ${count('unchanged')} unchanged, ${conflicts} conflicting.`,
  );

  if (options.dryRun) {
    console.log('Dry run: nothing was written.');
    return 0;
  }
  if (!existsSync(target)) mkdirSync(target, { recursive: true });
  applyPlan(plan);

  const result = runCheck(target);
  console.log(
    `Context check: ${result.errors.length} errors, ${result.warnings.length} warnings. ` +
      'Warnings for Draft files are expected until the context is filled in.',
  );

  console.log('\nNext steps:');
  let step = 1;
  if (conflicts) {
    console.log(`  ${step++}. Merge each .kit-new file into the existing file, then delete it. Do not commit .kit-new files.`);
  }
  console.log(`  ${step++}. Open the project in OpenCode or Copilot and ask the agent to set up the context.`);
  console.log('     In Copilot Chat you can run /setup-context.');
  console.log(`  ${step++}. Add the context check step to bitbucket-pipelines.yml. The step is under Pipelines in`);
  console.log('     context/modules/environments-delivery.md.');
  console.log(`  ${step++}. Run "node context/check-context.mjs", then commit the new files.`);
  console.log(`  ${step++}. Share context/HOW-TO-USE.md with the team. It explains the workflows, statuses and roles.`);
  console.log('     context/SKILLS-AND-COMMANDS.md lists every skill and command, and when to use each one.');
  return 0;
}

function cmdCheck(options) {
  const target = resolve(options._[1] ?? '.');
  if (!existsSync(target)) throw new UsageError(`Folder not found: ${target}`);
  const result = runCheck(target);
  const strict = Boolean(options.strict);
  if (options.json) console.log(JSON.stringify({ passed: !hasFailed(result, strict), strict, ...result }, null, 2));
  else console.log(formatReport(result, { strict }));
  return hasFailed(result, strict) ? 1 : 0;
}

function cmdList() {
  for (const p of listProfiles()) {
    console.log(`${p.id.padEnd(10)} ${p.name}${p.id === DEFAULT_PROFILE ? ' (default)' : ''}`);
    console.log(`${' '.repeat(11)}${p.description}`);
  }
  return 0;
}

async function main(argv) {
  try {
    const options = parseArgs(argv);
    if (options.version) {
      console.log(KIT_VERSION);
      return 0;
    }
    const command = options._[0];
    if (options.help || !command || command === 'help') {
      console.log(HELP);
      return 0;
    }
    if (command === 'init') return await cmdInit(options);
    if (command === 'check') return cmdCheck(options);
    if (command === 'list') return cmdList();
    throw new UsageError(`Unknown command: ${command}`);
  } catch (err) {
    if (err instanceof UsageError) {
      console.error(`eck: ${err.message}\nRun "eck help" for usage.`);
      return 2;
    }
    console.error(`eck: ${err.message}`);
    return 1;
  }
}

function isMainModule() {
  if (!process.argv[1]) return false;
  try {
    const self = realpathSync(fileURLToPath(import.meta.url));
    const invoked = realpathSync(resolve(process.argv[1]));
    return process.platform === 'win32' ? self.toLowerCase() === invoked.toLowerCase() : self === invoked;
  } catch {
    return false;
  }
}

if (isMainModule()) process.exitCode = await main(process.argv.slice(2));
