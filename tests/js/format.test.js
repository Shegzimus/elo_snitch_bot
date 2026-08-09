/**
 * The pure layer: command parsing, timestamps, and the three report formatters.
 *
 * Run with `npm test` (node --test, no test framework installed).
 */

const test = require('node:test');
const assert = require('node:assert');

const {
    formatAge,
    formatFullChanges,
    formatHelp,
    formatTimestamp,
    formatTopChanges,
    formatWinrate,
    parseCommand,
    parseTimestamp,
    updatedLine,
} = require('../../src/js/format');

// A fixed "now" so relative ages are reproducible. Local time, matching what
// elo_tracker.py writes.
const NOW = new Date(2026, 7, 8, 21, 32, 50); // 2026-08-08 21:32:50
const STAMP = '2026-08-08_21-32-50';

// --- parseCommand ------------------------------------------------------------

test('parseCommand accepts the four commands', () => {
    for (const name of ['!elocheck', '!winrate', '!topelo', '!help']) {
        assert.strictEqual(parseCommand(name), name);
    }
});

test('parseCommand is case insensitive and tolerates surrounding whitespace', () => {
    assert.strictEqual(parseCommand('  !TopElo \n'), '!topelo');
    assert.strictEqual(parseCommand('!WINRATE'), '!winrate');
});

test('parseCommand rejects near misses', () => {
    for (const body of ['!topelo2', 'topelo', '!top elo', '!!topelo', '!elo']) {
        assert.strictEqual(parseCommand(body), null, body);
    }
});

test('parseCommand rejects a command merely mentioned inside a sentence', () => {
    // Otherwise "does !topelo still work?" fires a full report.
    assert.strictEqual(parseCommand('does !topelo still work?'), null);
});

test('parseCommand ignores ordinary conversation', () => {
    for (const body of ['gg', 'who queued', '', '   ', 'hello!']) {
        assert.strictEqual(parseCommand(body), null, JSON.stringify(body));
    }
});

test('parseCommand survives non-string bodies', () => {
    for (const body of [null, undefined, 42, {}]) {
        assert.strictEqual(parseCommand(body), null);
    }
});

// --- timestamps --------------------------------------------------------------

test('parseTimestamp reads the pipeline format as local time', () => {
    assert.deepStrictEqual(parseTimestamp(STAMP), NOW);
});

test('parseTimestamp returns null for malformed input instead of throwing', () => {
    // The old formatTimestamp did "ts.split('_')[1].split('-')" and threw a
    // TypeError on anything without an underscore, which reached the group as
    // "Error processing ELO data".
    for (const bad of ['2026-08-08', '', 'not-a-timestamp', null, undefined, 42, '2026-13-01_00-00-00']) {
        assert.strictEqual(parseTimestamp(bad), null, JSON.stringify(bad));
    }
});

test('parseTimestamp rejects a date that does not exist', () => {
    // new Date(2026, 1, 31) silently rolls forward to 3 March.
    assert.strictEqual(parseTimestamp('2026-02-31_10-00-00'), null);
});

test('formatTimestamp renders zero-padded local time', () => {
    assert.strictEqual(formatTimestamp('2026-01-02_03-04-05'), '2026/01/02 03:04:05');
});

test('formatTimestamp returns empty string rather than throwing on bad input', () => {
    assert.strictEqual(formatTimestamp('garbage'), '');
    assert.strictEqual(formatTimestamp(undefined), '');
});

// --- relative age ------------------------------------------------------------

test('formatAge describes how stale the snapshot is', () => {
    const cases = [
        [new Date(2026, 7, 8, 21, 33, 20), 'just now'],       // +30s
        [new Date(2026, 7, 8, 21, 33, 50), '1 minute ago'],
        [new Date(2026, 7, 8, 21, 47, 50), '15 minutes ago'],
        [new Date(2026, 7, 8, 22, 32, 50), '1 hour ago'],
        [new Date(2026, 7, 9, 0, 32, 50), '3 hours ago'],
        [new Date(2026, 7, 9, 21, 32, 50), '1 day ago'],
        [new Date(2026, 7, 11, 21, 32, 50), '3 days ago'],
    ];
    for (const [now, expected] of cases) {
        assert.strictEqual(formatAge(STAMP, now), expected, now.toISOString());
    }
});

test('formatAge reports a future timestamp as just now rather than negative', () => {
    assert.strictEqual(formatAge(STAMP, new Date(2026, 7, 8, 20, 0, 0)), 'just now');
});

test('updatedLine carries both the absolute time and the age', () => {
    const line = updatedLine(STAMP, new Date(2026, 7, 9, 0, 32, 50));
    assert.strictEqual(line, '\n_Last updated: 2026/08/08 21:32:50 (3 hours ago)_');
});

test('updatedLine is empty when the timestamp is missing or unparseable', () => {
    assert.strictEqual(updatedLine(undefined, NOW), '');
    assert.strictEqual(updatedLine('garbage', NOW), '');
});

// --- fixtures ----------------------------------------------------------------

const eloData = {
    timestamp: STAMP,
    changes: [
        {
            summ_id: 'AJsBigBackClock',
            queue: 'Solo/Duo Queue',
            tier: 'MASTER I',
            lp: 6,
            change: '+35 LP - PROMOTED from DIAMOND to MASTER',
        },
        {
            summ_id: 'Sadme17',
            queue: 'Solo/Duo Queue',
            tier: 'PLATINUM IV',
            lp: 4,
            change: '+25 LP',
        },
        {
            summ_id: 'Rahzzcal',
            queue: 'Flex Queue',
            tier: 'EMERALD II',
            lp: 95,
            change: '-14 LP',
        },
    ],
    top_changes: [
        {
            rank: 1,
            summ_id: 'Rahzzcal',
            tier: 'EMERALD II',
            lp: 95,
            change: '+1229 LP - PROMOTED from SILVER to EMERALD',
        },
        {
            rank: 2,
            summ_id: 'Sadme17',
            tier: 'PLATINUM IV',
            lp: 4,
            change: '+25 LP',
        },
    ],
};

const winrateData = {
    timestamp: STAMP,
    changes: [
        { summ_id: 'Ajax d great', tier: 'GOLD', rank: 'I', wins: 30, losses: 20, win_rate: 60 },
        { summ_id: 'Sadme17', tier: 'PLATINUM', rank: 'IV', wins: 5, losses: 5, win_rate: 50 },
        { summ_id: 'Rahzzcal', tier: 'EMERALD', rank: 'II', wins: 40, losses: 40, win_rate: 50 },
    ],
};

// --- formatTopChanges --------------------------------------------------------

test('formatTopChanges numbers the entries and bolds promotions', () => {
    const message = formatTopChanges(eloData, NOW);

    assert.match(message, /^\*TOP 5 ELO CHANGES\*/);
    assert.match(message, /#1 Rahzzcal: EMERALD II \(95 LP\) \*\+1229 LP - PROMOTED from SILVER to EMERALD\*/);
    // A plain LP move is not bolded.
    assert.match(message, /#2 Sadme17: PLATINUM IV \(4 LP\) \+25 LP\n/);
});

test('formatTopChanges reports the snapshot age', () => {
    const message = formatTopChanges(eloData, new Date(2026, 7, 8, 23, 32, 50));
    assert.match(message, /_Last updated: 2026\/08\/08 21:32:50 \(2 hours ago\)_$/);
});

test('formatTopChanges handles an empty or absent snapshot', () => {
    assert.strictEqual(formatTopChanges({ top_changes: [] }, NOW), 'No ELO changes available!');
    assert.strictEqual(formatTopChanges({}, NOW), 'No ELO changes available!');
    assert.strictEqual(formatTopChanges(null, NOW), 'No ELO changes available!');
});

// --- formatFullChanges -------------------------------------------------------

test('formatFullChanges groups players under their queue', () => {
    const message = formatFullChanges(eloData, NOW);

    assert.match(message, /\*Solo\/Duo Queue\*: \n {2}1\. AJsBigBackClock/);
    assert.match(message, /\*Flex Queue\*: \n {2}1\. Rahzzcal/);
    // Numbering restarts within each queue.
    assert.match(message, / {2}2\. Sadme17: PLATINUM IV \(4 LP\) \+25 LP/);
});

test('formatFullChanges bolds demotions as well as promotions', () => {
    const demoted = {
        timestamp: STAMP,
        changes: [{ summ_id: 'X', queue: 'Solo/Duo Queue', tier: 'GOLD IV', lp: 0, change: '-40 LP - DEMOTED from PLATINUM to GOLD' }],
    };
    assert.match(formatFullChanges(demoted, NOW), /\*-40 LP - DEMOTED from PLATINUM to GOLD\*/);
});

test('formatFullChanges handles an empty snapshot', () => {
    assert.strictEqual(formatFullChanges({ changes: [] }, NOW), 'No ELO changes available!');
    assert.strictEqual(formatFullChanges(null, NOW), 'No ELO changes available!');
});

test('formatFullChanges survives a snapshot with no timestamp', () => {
    const message = formatFullChanges({ changes: eloData.changes }, NOW);
    assert.match(message, /AJsBigBackClock/);
    assert.ok(!message.includes('Last updated'));
});

// --- formatWinrate -----------------------------------------------------------

test('formatWinrate ranks by win rate, breaking ties on games played', () => {
    const message = formatWinrate(winrateData, NOW);

    assert.match(message, /1\. Ajax d great - GOLD I \(60% \| 30W-20L\)/);
    // Rahzzcal and Sadme17 both sit at 50%; the busier player ranks higher.
    assert.match(message, /2\. Rahzzcal - EMERALD II \(50% \| 40W-40L\)/);
    assert.match(message, /3\. Sadme17 - PLATINUM IV \(50% \| 5W-5L\)/);
});

test('formatWinrate lists the most active players by total games', () => {
    const message = formatWinrate(winrateData, NOW);
    const activity = message.split('*Most Active Players:*')[1];

    assert.match(activity, /1\. Rahzzcal - 80 games \(50%\)/);
    assert.match(activity, /2\. Ajax d great - 50 games \(60%\)/);
});

test('formatWinrate summarises totals', () => {
    const message = formatWinrate(winrateData, NOW);

    assert.match(message, /Total Players: 3\n/);
    assert.match(message, /Total Games Tracked: 140\n/);
    assert.match(message, /Average Win Rate: 53\.33%\n/);
});

test('formatWinrate handles an empty roster without dividing by zero', () => {
    assert.strictEqual(formatWinrate({ changes: [] }, NOW), 'No winrate data available!');
    assert.strictEqual(formatWinrate(null, NOW), 'No winrate data available!');
});

// --- help --------------------------------------------------------------------

test('formatHelp names every command the bot answers', () => {
    const message = formatHelp();
    for (const name of ['!elocheck', '!winrate', '!topelo', '!help']) {
        assert.ok(message.includes(name), name);
    }
});
