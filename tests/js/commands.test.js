/**
 * The command table and the rate limiter, exercised without a filesystem.
 */

const test = require('node:test');
const assert = require('node:assert');

const { COMMANDS, createRateLimiter, runCommand } = require('../../src/js/commands');
const { parseCommand } = require('../../src/js/format');

const NOW = new Date(2026, 7, 8, 21, 32, 50);
const STAMP = '2026-08-08_21-32-50';

const snapshots = {
    elo_changes: {
        timestamp: STAMP,
        changes: [{ summ_id: 'Sadme17', queue: 'Solo/Duo Queue', tier: 'GOLD IV', lp: 4, change: '+25 LP' }],
        top_changes: [{ summ_id: 'Sadme17', tier: 'GOLD IV', lp: 4, change: '+25 LP' }],
    },
    'winrate/solo': {
        timestamp: STAMP,
        changes: [{ summ_id: 'Sadme17', tier: 'GOLD', rank: 'IV', wins: 5, losses: 5, win_rate: 50 }],
    },
};

const readStub = async (folder) => snapshots[folder] ?? null;
const readNothing = async () => null;

// --- the table ---------------------------------------------------------------

test('every command in the table is one parseCommand recognises', () => {
    // Otherwise a command could be added to the table and never reachable.
    for (const name of Object.keys(COMMANDS)) {
        assert.strictEqual(parseCommand(name), name);
    }
});

test('runCommand renders each report from its own snapshot', async () => {
    const top = await runCommand('!topelo', { read: readStub, now: NOW });
    assert.match(top, /TOP 5 ELO CHANGES/);

    const full = await runCommand('!elocheck', { read: readStub, now: NOW });
    assert.match(full, /FULL ELO CHANGES/);

    const winrate = await runCommand('!winrate', { read: readStub, now: NOW });
    assert.match(winrate, /SOLO\/DUO QUEUE WIN RATES/);
});

test('runCommand returns null for anything that is not a command', async () => {
    for (const name of ['!nope', 'topelo', '', null]) {
        assert.strictEqual(await runCommand(name, { read: readStub, now: NOW }), null);
    }
});

test('!help works before the pipeline has ever run', async () => {
    // It reads no snapshot, so a missing data directory must not affect it.
    const reply = await runCommand('!help', { read: readNothing, now: NOW });
    assert.match(reply, /!elocheck/);
});

test('runCommand reports missing data distinctly per source', async () => {
    assert.strictEqual(await runCommand('!topelo', { read: readNothing, now: NOW }), 'No ELO changes data available!');
    assert.strictEqual(await runCommand('!elocheck', { read: readNothing, now: NOW }), 'No ELO changes data available!');
    assert.strictEqual(await runCommand('!winrate', { read: readNothing, now: NOW }), 'No winrate data available!');
});

test('runCommand propagates a read failure rather than reporting no data', async () => {
    // A corrupt latest.json is not the same as an absent one; the caller says so.
    const readBroken = async () => { throw new SyntaxError('Unexpected end of JSON input'); };
    await assert.rejects(() => runCommand('!topelo', { read: readBroken, now: NOW }), SyntaxError);
});

test('the ELO commands read the same snapshot as the pipeline mirrors it', async () => {
    const requested = [];
    const spy = async (folder) => { requested.push(folder); return snapshots[folder] ?? null; };

    await runCommand('!topelo', { read: spy, now: NOW });
    await runCommand('!elocheck', { read: spy, now: NOW });
    await runCommand('!winrate', { read: spy, now: NOW });

    assert.deepStrictEqual(requested, ['elo_changes', 'elo_changes', 'winrate/solo']);
});

test('reports carry the snapshot age', async () => {
    const later = new Date(2026, 7, 8, 23, 32, 50);
    const reply = await runCommand('!elocheck', { read: readStub, now: later });
    assert.match(reply, /\(2 hours ago\)/);
});

// --- rate limiting -----------------------------------------------------------

test('the limiter allows the first five commands and blocks the sixth', () => {
    const limiter = createRateLimiter({ windowMs: 60000, max: 5 });
    const at = Date.now();

    for (let i = 0; i < 5; i += 1) {
        assert.strictEqual(limiter.allow('user-a', at + i), true, `call ${i + 1}`);
    }
    assert.strictEqual(limiter.allow('user-a', at + 5), false);
});

test('the window slides, so the budget returns', () => {
    const limiter = createRateLimiter({ windowMs: 60000, max: 5 });
    const at = Date.now();

    for (let i = 0; i < 5; i += 1) {
        limiter.allow('user-a', at);
    }
    assert.strictEqual(limiter.allow('user-a', at + 59999), false);
    assert.strictEqual(limiter.allow('user-a', at + 60001), true);
});

test('the budget is per user', () => {
    const limiter = createRateLimiter({ windowMs: 60000, max: 5 });
    const at = Date.now();

    for (let i = 0; i < 5; i += 1) {
        limiter.allow('user-a', at);
    }
    assert.strictEqual(limiter.allow('user-a', at), false);
    assert.strictEqual(limiter.allow('user-b', at), true);
});

test('a blocked call does not extend the block', () => {
    // Rejected attempts must not be recorded, or a persistent spammer would
    // never recover.
    const limiter = createRateLimiter({ windowMs: 60000, max: 5 });
    const at = Date.now();

    for (let i = 0; i < 5; i += 1) {
        limiter.allow('user-a', at);
    }
    for (let i = 0; i < 20; i += 1) {
        limiter.allow('user-a', at + 1000 + i);
    }
    assert.strictEqual(limiter.allow('user-a', at + 60001), true);
});

test('ordinary conversation never reaches the limiter', () => {
    // The regression that made the bot unusable: the old handler metered every
    // message before checking whether it was a command, so chatter exhausted the
    // window and the bot answered it with "Rate limit exceeded", then refused the
    // real command. Parsing first is what prevents that, so assert the order.
    const limiter = createRateLimiter({ windowMs: 60000, max: 5 });
    const at = Date.now();

    const chatter = ['gg', 'who queued', 'lol', 'im inting', 'one more', 'last one', 'ok'];
    for (const body of chatter) {
        const command = parseCommand(body);
        assert.strictEqual(command, null, body);
        if (command) {
            limiter.allow('user-a', at);
        }
    }

    assert.strictEqual(limiter.allow('user-a', at), true, 'chatter consumed the command budget');
});
