/**
 * Reading the pipeline's output.
 *
 * elo_tracker.py mirrors every snapshot to <folder>/latest.json (see
 * write_snapshot), so there is exactly one file to read. The previous version
 * predated that mirror and walked the dated folders, sorting directory names and
 * then filenames to rediscover what the pipeline already points at -- along with
 * a five-minute cache whose only purpose was to avoid repeating that walk.
 */

const fs = require('fs').promises;
const path = require('path');

const DATA_DIR = path.resolve(__dirname, '../..', 'data');

/**
 * Read the newest snapshot for a data folder, or null if the pipeline has not
 * written one yet.
 *
 * Throws on malformed JSON rather than swallowing it: an unreadable file means
 * something is wrong with the pipeline, and the caller reports that distinctly
 * from "no data yet".
 */
async function readLatest(folder) {
    const file = path.join(DATA_DIR, folder, 'latest.json');
    let contents;
    try {
        contents = await fs.readFile(file, 'utf8');
    } catch (error) {
        if (error.code === 'ENOENT') {
            return null;
        }
        throw error;
    }
    return JSON.parse(contents);
}

module.exports = { DATA_DIR, readLatest };
