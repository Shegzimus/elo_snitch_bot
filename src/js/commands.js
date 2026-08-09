/**
 * The command table and the rate limiter.
 *
 * Adding a report means adding one entry here: which snapshot it reads and which
 * formatter renders it.
 */

const { readLatest } = require('./data');
const format = require('./format');

const COMMANDS = {
    '!topelo': {
        source: 'elo_changes',
        render: format.formatTopChanges,
        missing: 'No ELO changes data available!',
    },
    '!elocheck': {
        source: 'elo_changes',
        render: format.formatFullChanges,
        missing: 'No ELO changes data available!',
    },
    '!winrate': {
        source: 'winrate/solo',
        render: format.formatWinrate,
        missing: 'No winrate data available!',
    },
    // No source: the help text does not depend on pipeline output.
    '!help': {
        render: format.formatHelp,
    },
};

/**
 * Render a command's reply, or null if the name is not a command.
 *
 * Dependencies are injectable so the table can be exercised without a
 * filesystem or a real clock.
 */
async function runCommand(name, { read = readLatest, now = new Date() } = {}) {
    const command = COMMANDS[name];
    if (!command) {
        return null;
    }
    if (!command.source) {
        return command.render();
    }
    const data = await read(command.source);
    if (!data) {
        return command.missing;
    }
    return command.render(data, now);
}

/**
 * Per-user sliding window, counted in commands rather than messages.
 *
 * The previous version metered every message in the group before checking
 * whether it was a command, so ordinary conversation exhausted the window and
 * the bot answered chatter with "Rate limit exceeded" -- then refused the real
 * command when it arrived. Callers must parse the command first and only meter
 * what they are actually about to serve.
 */
function createRateLimiter({ windowMs = 60000, max = 5 } = {}) {
    const hits = new Map();

    return {
        allow(userId, now = Date.now()) {
            const recent = (hits.get(userId) || []).filter((at) => now - at < windowMs);
            if (recent.length >= max) {
                hits.set(userId, recent);
                return false;
            }
            recent.push(now);
            hits.set(userId, recent);
            return true;
        },
    };
}

module.exports = { COMMANDS, createRateLimiter, runCommand };
