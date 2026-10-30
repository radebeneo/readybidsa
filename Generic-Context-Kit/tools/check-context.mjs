#!/usr/bin/env node
/**
 * Context check for the Context Kit.
 *
 * Checks that a repository's context files are present, filled in and reviewed,
 * and that they contain no unresolved placeholders or likely secrets.
 *
 * Usage:
 *   node context/check-context.mjs [--root <folder>] [--strict] [--json]
 *
 *   --root    Repository root. Defaults to the folder above this script when it
 *             lives in context/, otherwise the current folder.
 *   --strict  Fail on warnings as well as errors.
 *   --json    Print the result as JSON.
 *
 * Exit codes: 0 passed, 1 failed, 2 could not run.
 *
 * Uses Node.js built-ins only and needs Node.js 20 or later. In a project this
 * file is managed by the Context Kit: update it from the kit rather
 * than editing it.
 */
import { existsSync, readdirSync, readFileSync, realpathSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const TOKEN_PATTERN = /\{\{([A-Z][A-Z0-9_]*)\}\}/g;
const FILL_PATTERN = /<!--\s*FILL:/g;
const CONTEXT_STATUSES = ['Draft', 'Active', 'Not applicable'];
const SPEC_STATUSES = ['Spec in review', 'Ready', 'In progress', 'In review', 'Done', 'Blocked'];
const SPEC_COMPLETE_STATUSES = ['Ready', 'In progress', 'In review', 'Done'];
const ADR_STATUS = /^(Proposed|Accepted|Rejected|Superseded by ADR-\d{4})$/;
const ADR_COMPLETE_STATUS = /^(Accepted|Superseded by ADR-\d{4})$/;
const DEFAULT_REVIEW_DAYS = 90;
const DAY_MS = 24 * 60 * 60 * 1000;

const DEFAULT_CONFIG = {
  reviewDays: DEFAULT_REVIEW_DAYS,
  entryPoints: ['AGENTS.md', '.github/copilot-instructions.md'],
  contextFiles: [
    'context/project-overview.md',
    'context/architecture.md',
    'context/code-standards.md',
    'context/ui-context.md',
    'context/ai-workflow-rules.md',
    'context/progress-tracker.md',
    'context/modules/security-compliance.md',
    'context/modules/integrations.md',
    'context/modules/environments-delivery.md',
    'context/modules/quality-testing.md',
    'context/modules/operations.md',
    'context/modules/go-live.md',
    'context/specs/00-build-plan.md',
  ],
  managedFiles: [],
};

// Values that are clearly examples rather than real secrets.
const PLACEHOLDER_VALUE = /[<>{}]|example|placeholder|changeme|^[*x.]+$/i;

const SECRET_PATTERNS = [
  { name: 'private key', pattern: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g },
  { name: 'AWS access key', pattern: /\bAKIA[0-9A-Z]{16}\b/g },
  { name: 'GitHub token', pattern: /\bgh[pousr]_[A-Za-z0-9]{36,}\b/g },
  { name: 'Slack token', pattern: /\bxox[abprs]-[A-Za-z0-9-]{10,}/g },
  { name: 'Azure storage account key', pattern: /\bAccountKey=([A-Za-z0-9+/=]{40,})/gi, valueGroup: 1 },
  { name: 'JSON web token', pattern: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g },
  { name: 'password in a connection string', pattern: /\b(?:Password|Pwd)\s*=\s*([^;\s"'`]{4,})/gi, valueGroup: 1 },
  {
    name: 'hard-coded credential',
    pattern: /\b(?:api[_-]?key|client[_-]?secret|secret[_-]?key|access[_-]?token|auth[_-]?token|password)["']?\s*[:=]\s*["']([^"'\s]{12,})["']/gi,
    valueGroup: 1,
  },
];

const USAGE = `Usage: node context/check-context.mjs [--root <folder>] [--strict] [--json]

  --root    Repository root. Defaults to the folder above this script when it
            lives in context/, otherwise the current folder.
  --strict  Fail on warnings as well as errors.
  --json    Print the result as JSON.`;

/**
 * Reads the first Markdown table in the opening lines of a file and returns its
 * first data row as an object keyed by column name, or null if there is none.
 */
export function parseHeader(text) {
  const lines = text.split(/\r?\n/, 20);
  for (let i = 0; i + 2 < lines.length; i++) {
    const head = splitRow(lines[i]);
    const separator = splitRow(lines[i + 1]);
    if (!head || !separator || !separator.every((cell) => /^:?-{3,}:?$/.test(cell))) continue;
    const values = splitRow(lines[i + 2]) ?? [];
    const header = {};
    head.forEach((name, index) => {
      header[name] = values[index] ?? '';
    });
    return header;
  }
  return null;
}

/** Parses a YYYY-MM-DD date and returns its UTC timestamp, or null if invalid. */
export function parseDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value ?? '').trim());
  if (!match) return null;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const time = Date.UTC(year, month - 1, day);
  const date = new Date(time);
  const valid = date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  return valid ? time : null;
}

/**
 * Checks the repository at root. Returns { errors, warnings }, where each item
 * is { file, line, message } and file is a forward-slash path relative to root.
 * options.today (YYYY-MM-DD) overrides the current date.
 */
export function runCheck(root, options = {}) {
  const today = options.today === undefined ? localToday() : parseDate(options.today);
  if (today === null) throw new Error(`Invalid date: ${options.today}`);

  const errors = [];
  const warnings = [];
  const error = (file, message, line) => errors.push({ file, line, message });
  const warn = (file, message, line) => warnings.push({ file, line, message });

  const config = loadConfig(root, error);

  for (const rel of config.entryPoints) {
    const abs = toAbsolute(root, rel);
    if (!existsSync(abs)) {
      error(rel, 'Missing. Agents use this file to find the project instructions.');
      continue;
    }
    const fills = findAll(readText(abs), FILL_PATTERN);
    if (fills.length) warn(rel, `${plural(fills.length, 'FILL comment')} still to complete.`, fills[0].line);
  }

  for (const rel of config.contextFiles) {
    const abs = toAbsolute(root, rel);
    if (!existsSync(abs)) {
      error(rel, 'Missing. Restore it; if it does not apply, keep it and set its Status to "Not applicable".');
      continue;
    }
    checkContextFile(rel, readText(abs), { today, reviewDays: config.reviewDays, error, warn });
  }

  const tracked = new Set(config.contextFiles);

  // Brand files are added per project, so they are found rather than listed in kit.json.
  for (const rel of listMarkdown(root, 'context/brands')) {
    const name = fileName(rel);
    if (tracked.has(rel) || name.startsWith('_') || name === 'README.md') continue;
    checkContextFile(rel, readText(toAbsolute(root, rel)), { today, reviewDays: config.reviewDays, error, warn });
  }

  for (const rel of listMarkdown(root, 'context/specs')) {
    if (tracked.has(rel) || !/^\d+-.+\.md$/.test(fileName(rel))) continue;
    checkStatusDocument(rel, readText(toAbsolute(root, rel)), {
      error,
      isValid: (status) => SPEC_STATUSES.includes(status),
      isComplete: (status) => SPEC_COMPLETE_STATUSES.includes(status),
      allowed: SPEC_STATUSES.join(', '),
    });
  }

  for (const rel of listMarkdown(root, 'context/decisions')) {
    const name = fileName(rel);
    if (!/^ADR-\d{4}-.+\.md$/.test(name) || name === 'ADR-0000-template.md') continue;
    checkStatusDocument(rel, readText(toAbsolute(root, rel)), {
      error,
      isValid: (status) => ADR_STATUS.test(status),
      isComplete: (status) => ADR_COMPLETE_STATUS.test(status),
      allowed: 'Proposed, Accepted, Rejected, Superseded by ADR-NNNN',
    });
  }

  const scanned = new Set([
    ...config.entryPoints,
    ...listMarkdown(root, 'context'),
    ...config.managedFiles.filter((rel) => rel.endsWith('.md')),
  ]);
  for (const rel of [...scanned].sort()) {
    const abs = toAbsolute(root, rel);
    if (existsSync(abs)) scanFile(rel, readText(abs), error);
  }

  return { errors, warnings };
}

export function hasFailed(result, strict = false) {
  return result.errors.length > 0 || (strict && result.warnings.length > 0);
}

export function formatReport(result, { strict = false } = {}) {
  const location = (item) => (item.line ? `${item.file}:${item.line}` : item.file);
  const lines = [
    ...result.errors.map((item) => `ERROR  ${location(item)}  ${item.message}`),
    ...result.warnings.map((item) => `WARN   ${location(item)}  ${item.message}`),
  ];
  if (lines.length) lines.push('');
  const outcome = hasFailed(result, strict) ? 'failed' : 'passed';
  const mode = strict ? ' (strict: warnings also fail)' : '';
  lines.push(
    `Context check ${outcome}: ${plural(result.errors.length, 'error')}, ${plural(result.warnings.length, 'warning')}${mode}.`,
  );
  return lines.join('\n');
}

function checkContextFile(rel, text, { today, reviewDays, error, warn }) {
  const header = parseHeader(text);
  if (!header || !('Owner' in header) || !('Last reviewed' in header) || !('Status' in header)) {
    error(rel, 'The header table (Owner, Last reviewed, Status) is missing or incomplete.', 1);
    return;
  }

  const status = header.Status;
  if (!CONTEXT_STATUSES.includes(status)) {
    error(rel, `Status "${status}" is not one of: ${CONTEXT_STATUSES.join(', ')}.`);
    return;
  }
  if (status === 'Not applicable') return;

  const fills = findAll(text, FILL_PATTERN);
  if (status === 'Active' && fills.length) {
    error(rel, `Status is Active but ${plural(fills.length, 'FILL comment')} ${fills.length === 1 ? 'remains' : 'remain'}. Finish them or set Status to Draft.`, fills[0].line);
  }
  if (status === 'Draft') {
    if (fills.length) warn(rel, `Draft: ${plural(fills.length, 'section')} still to fill.`, fills[0].line);
    else warn(rel, 'Draft: no FILL comments remain. Review it and set Status to Active.');
  }

  if (!header.Owner || /^(TBC|TBD)$/i.test(header.Owner)) warn(rel, 'No owner is set.');

  const reviewed = parseDate(header['Last reviewed']);
  if (reviewed === null) {
    error(rel, `Last reviewed "${header['Last reviewed']}" is not a date in YYYY-MM-DD format.`);
  } else {
    const age = Math.floor((today - reviewed) / DAY_MS);
    if (age > reviewDays) warn(rel, `Last reviewed ${age} days ago. Reviews are due every ${reviewDays} days.`);
  }
}

function checkStatusDocument(rel, text, { error, isValid, isComplete, allowed }) {
  const status = parseHeader(text)?.Status;
  if (!status) {
    error(rel, 'The header table with a Status column is missing.', 1);
    return;
  }
  if (!isValid(status)) {
    error(rel, `Status "${status}" is not one of: ${allowed}.`);
    return;
  }
  const fills = findAll(text, FILL_PATTERN);
  if (isComplete(status) && fills.length) {
    error(rel, `Status is ${status} but ${plural(fills.length, 'FILL comment')} ${fills.length === 1 ? 'remains' : 'remain'}.`, fills[0].line);
  }
}

function scanFile(rel, text, error) {
  for (const { match, line } of findAll(text, TOKEN_PATTERN)) {
    error(rel, `Unresolved placeholder ${match[0]}. Replace it with a real value.`, line);
  }
  for (const secret of SECRET_PATTERNS) {
    for (const { match, line } of findAll(text, secret.pattern)) {
      if (secret.valueGroup && PLACEHOLDER_VALUE.test(match[secret.valueGroup])) continue;
      error(
        rel,
        `Possible ${secret.name}. Remove it, rotate the secret and store it as described in context/modules/security-compliance.md.`,
        line,
      );
    }
  }
}

function loadConfig(root, error) {
  const rel = 'context/kit.json';
  const abs = toAbsolute(root, rel);
  if (!existsSync(abs)) {
    error(rel, 'Missing. Add the kit with "eck init". The default file list was checked instead.');
    return { ...DEFAULT_CONFIG };
  }

  let data;
  try {
    data = JSON.parse(readFileSync(abs, 'utf8'));
  } catch (err) {
    error(rel, `Not valid JSON (${err.message}). The default file list was checked instead.`);
    return { ...DEFAULT_CONFIG };
  }

  const pathList = (key) => {
    if (!(key in data)) return DEFAULT_CONFIG[key];
    const value = data[key];
    if (!Array.isArray(value) || !value.every((item) => typeof item === 'string' && isSafePath(item))) {
      error(rel, `"${key}" must be a list of relative paths inside the repository.`);
      return DEFAULT_CONFIG[key];
    }
    return value;
  };

  let reviewDays = DEFAULT_REVIEW_DAYS;
  if ('reviewDays' in data) {
    if (Number.isInteger(data.reviewDays) && data.reviewDays > 0) reviewDays = data.reviewDays;
    else error(rel, '"reviewDays" must be a whole number greater than 0.');
  }

  return {
    reviewDays,
    entryPoints: pathList('entryPoints'),
    contextFiles: pathList('contextFiles'),
    managedFiles: pathList('managedFiles'),
  };
}

function isSafePath(rel) {
  return rel.length > 0 && !/^([a-zA-Z]:|[\\/])/.test(rel) && !rel.split(/[\\/]/).includes('..');
}

function splitRow(line) {
  const trimmed = (line ?? '').trim();
  if (trimmed.length < 2 || !trimmed.startsWith('|') || !trimmed.endsWith('|')) return null;
  return trimmed
    .slice(1, -1)
    .split('|')
    .map((cell) => cell.trim());
}

function findAll(text, pattern) {
  const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`;
  return [...text.matchAll(new RegExp(pattern.source, flags))].map((match) => ({
    match,
    line: lineAt(text, match.index),
  }));
}

function lineAt(text, index) {
  let line = 1;
  for (let i = 0; i < index; i++) if (text.charCodeAt(i) === 10) line++;
  return line;
}

function listMarkdown(root, rel) {
  const dir = toAbsolute(root, rel);
  if (!existsSync(dir)) return [];
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
    const child = `${rel}/${entry.name}`;
    if (entry.isDirectory()) files.push(...listMarkdown(root, child));
    else if (entry.isFile() && entry.name.endsWith('.md')) files.push(child);
  }
  return files;
}

function localToday() {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
}

function toAbsolute(root, rel) {
  return join(root, ...rel.split('/'));
}

function fileName(rel) {
  return rel.split('/').pop();
}

function readText(path) {
  return readFileSync(path, 'utf8').replace(/\r\n/g, '\n');
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

function main(args) {
  let root;
  let strict = false;
  let json = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--root') {
      root = args[++i];
      if (!root) {
        console.error('--root needs a folder.');
        return 2;
      }
    } else if (arg === '--strict') strict = true;
    else if (arg === '--json') json = true;
    else if (arg === '--help' || arg === '-h') {
      console.log(USAGE);
      return 0;
    } else {
      console.error(`Unknown option: ${arg}\n\n${USAGE}`);
      return 2;
    }
  }

  if (!root) {
    const here = dirname(fileURLToPath(import.meta.url));
    root = basename(here) === 'context' ? dirname(here) : process.cwd();
  }
  root = resolve(root);
  if (!existsSync(root)) {
    console.error(`Folder not found: ${root}`);
    return 2;
  }

  let result;
  try {
    result = runCheck(root);
  } catch (err) {
    console.error(`The context check could not run: ${err.message}`);
    return 2;
  }

  if (json) console.log(JSON.stringify({ passed: !hasFailed(result, strict), strict, ...result }, null, 2));
  else console.log(formatReport(result, { strict }));
  return hasFailed(result, strict) ? 1 : 0;
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

if (isMainModule()) process.exitCode = main(process.argv.slice(2));
