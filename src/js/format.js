/**
 * Pure formatting and parsing. No I/O, no whatsapp-web.js, no clock of its own --
 * every function that needs "now" takes it as an argument so the output is
 * reproducible in tests.
 */

// The only three report commands, plus !help. Anything else is ignored in
// silence: the bot shares a group with real conversation, so replying to
// non-commands turns it into a nuisance.
const COMMAND_NAMES = ['!elocheck', '!winrate', '!topelo', '!help'];

/**
 * Extract a command from a raw message body, or null if it isn't one.
 *
 * Deliberately strict: the whole body must be the command. "!topelo now please"
 * is not a command, so a message that merely mentions one does not trigger a
 * report.
 */
function parseCommand(body) {
    if (typeof body !== 'string') {
        return null;
    }
    const candidate = body.trim().toLowerCase();
    return COMMAND_NAMES.includes(candidate) ? candidate : null;
}

// Written by elo_tracker.py's get_current_date_time() as
// datetime.now().strftime("%Y-%m-%d_%H-%M-%S") -- local wall-clock, no zone.
// The pipeline and the bot run on the same machine, so reading it back as local
// time is consistent.
const TIMESTAMP_PATTERN = /^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})$/;

/**
 * Parse a pipeline timestamp into a Date, or null if it is malformed.
 *
 * The previous implementation split on '_' and immediately called .split on the
 * second half, so any timestamp without an underscore threw a TypeError that
 * surfaced to the group as "Error processing ELO data".
 */
function parseTimestamp(timestamp) {
    if (typeof timestamp !== 'string') {
        return null;
    }
    const match = TIMESTAMP_PATTERN.exec(timestamp);
    if (!match) {
        return null;
    }
    const [, year, month, day, hour, minute, second] = match.map(Number);
    const date = new Date(year, month - 1, day, hour, minute, second);
    // Rejects impossible dates like 2026-02-31, which the Date constructor
    // would otherwise roll forward into March.
    if (date.getMonth() !== month - 1 || date.getDate() !== day) {
        return null;
    }
    return date;
}

function formatTimestamp(timestamp) {
    const date = parseTimestamp(timestamp);
    if (!date) {
        return '';
    }
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ` +
        `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

const MINUTE = 60 * 1000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

function plural(count, noun) {
    return `${count} ${noun}${count === 1 ? '' : 's'} ago`;
}

/**
 * How long ago the pipeline produced this data, in words.
 *
 * Clock skew (a timestamp in the future) reads as "just now" rather than a
 * negative age.
 */
function formatAge(timestamp, now = new Date()) {
    const date = parseTimestamp(timestamp);
    if (!date) {
        return '';
    }
    const elapsed = now.getTime() - date.getTime();
    if (elapsed < MINUTE) {
        return 'just now';
    }
    if (elapsed < HOUR) {
        return plural(Math.floor(elapsed / MINUTE), 'minute');
    }
    if (elapsed < DAY) {
        return plural(Math.floor(elapsed / HOUR), 'hour');
    }
    return plural(Math.floor(elapsed / DAY), 'day');
}

/**
 * The trailing provenance line. Empty string when the timestamp is missing or
 * unparseable, so a bad timestamp costs the footer rather than the report.
 */
function updatedLine(timestamp, now = new Date()) {
    const formatted = formatTimestamp(timestamp);
    if (!formatted) {
        return '';
    }
    return `\n_Last updated: ${formatted} (${formatAge(timestamp, now)})_`;
}

// Promotions and demotions are the events worth reading twice, so they are the
// only ones bolded.
function emphasise(change) {
    const text = change || '';
    return text.includes('PROMOTED') || text.includes('DEMOTED') ? `*${text}*` : text;
}

function formatTopChanges(data, now = new Date()) {
    const changes = (data && data.top_changes) || [];
    if (changes.length === 0) {
        return 'No ELO changes available!';
    }

    let message = '*TOP 5 ELO CHANGES*\n\n';
    changes.forEach((change, index) => {
        message += `#${index + 1} ${change.summ_id}: ${change.tier} (${change.lp} LP) ${emphasise(change.change)}\n`;
    });

    return message + updatedLine(data.timestamp, now);
}

function formatFullChanges(data, now = new Date()) {
    const changes = (data && data.changes) || [];
    if (changes.length === 0) {
        return 'No ELO changes available!';
    }

    const queues = new Map();
    changes.forEach((change) => {
        if (!queues.has(change.queue)) {
            queues.set(change.queue, []);
        }
        queues.get(change.queue).push(change);
    });

    let message = '*FULL ELO CHANGES*\n\n';
    for (const [queue, queueChanges] of queues) {
        message += `*${queue}*: \n`;
        queueChanges.forEach((change, index) => {
            message += `  ${index + 1}. ${change.summ_id}: ${change.tier} (${change.lp} LP) ${emphasise(change.change)}\n`;
        });
        message += '\n';
    }

    return message + updatedLine(data.timestamp, now);
}

function formatWinrate(data, now = new Date()) {
    const players = (data && data.changes) || [];
    if (players.length === 0) {
        return 'No winrate data available!';
    }

    const games = (player) => player.wins + player.losses;

    const byWinRate = [...players].sort((a, b) =>
        b.win_rate !== a.win_rate ? b.win_rate - a.win_rate : games(b) - games(a));

    let message = '*SOLO/DUO QUEUE WIN RATES*\n\n';
    message += '*Top 10 Players by Win Rate:*\n';
    byWinRate.slice(0, 10).forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${player.tier} ${player.rank} ` +
            `(${player.win_rate}% | ${player.wins}W-${player.losses}L)\n`;
    });

    const byActivity = [...players].sort((a, b) => games(b) - games(a));
    message += '\n*Most Active Players:*\n';
    byActivity.slice(0, 5).forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${games(player)} games (${player.win_rate}%)\n`;
    });

    const totalGames = players.reduce((sum, player) => sum + games(player), 0);
    const averageWinRate = players.reduce((sum, player) => sum + player.win_rate, 0) / players.length;

    message += '\n*Stats Summary:*\n';
    message += `Total Players: ${players.length}\n`;
    message += `Total Games Tracked: ${totalGames}\n`;
    message += `Average Win Rate: ${averageWinRate.toFixed(2)}%\n`;

    return message + updatedLine(data.timestamp, now);
}

function formatHelp() {
    return '*ELO SNITCH BOT*\n\n' +
        'Available commands:\n' +
        '!elocheck - Full ELO changes list\n' +
        '!winrate - Solo/duo win rates\n' +
        '!topelo - Top 5 ELO changes\n' +
        '!help - This message';
}

module.exports = {
    COMMAND_NAMES,
    formatAge,
    formatFullChanges,
    formatHelp,
    formatTimestamp,
    formatTopChanges,
    formatWinrate,
    parseCommand,
    parseTimestamp,
    updatedLine,
};
