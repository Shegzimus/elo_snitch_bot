const { join } = require('path');

/**
 * Puppeteer downloads a ~500MB Chromium and by default caches it under the user
 * profile on C:, which has no free space on this machine. A partial extraction
 * there is what produced the "browser folder exists but the executable is
 * missing" failure -- the disk filled mid-unzip.
 *
 * Keeping the browser beside the project puts it on the same (roomy) drive as
 * the repo. Both `npx puppeteer browsers install chrome` and the runtime lookup
 * read this file, so they stay in agreement.
 */
module.exports = {
    cacheDirectory: join(__dirname, '.cache', 'puppeteer'),
};
