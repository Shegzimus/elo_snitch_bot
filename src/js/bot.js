/**
 * ELO Snitch Bot -- WhatsApp client wiring.
 *
 * This file is the impure shell: environment, session, events, replies. All the
 * logic worth testing lives in format.js and commands.js.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fsSync = require('fs');
const dotenv = require('dotenv');
const path = require('path');

const { createRateLimiter, runCommand } = require('./commands');
const { formatHelp, parseCommand } = require('./format');

// Paths resolve from this file, not the CWD, so the bot can start from anywhere.
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const ENV_PATH = path.join(PROJECT_ROOT, 'config', '.env');

// Stays next to this file so an existing logged-in session keeps working.
const AUTH_DIR = path.join(__dirname, '.wwebjs_auth');

if (!fsSync.existsSync(ENV_PATH)) {
    console.error(`No .env at ${ENV_PATH}`);
    console.error('Create it with WHATSAPP_GROUP_ID set.');
    process.exit(1);
}
dotenv.config({ path: ENV_PATH });

const rawGroupId = process.env.WHATSAPP_GROUP_ID;
if (!rawGroupId) {
    console.error('WHATSAPP_GROUP_ID is not set in config/.env');
    process.exit(1);
}
// The env may or may not carry the @g.us suffix.
const GROUP_ID = rawGroupId.includes('@g.us') ? rawGroupId : `${rawGroupId}@g.us`;

// Off by default: the bot restarts on every crash, and an announcement per
// restart is noise in a live group.
const ANNOUNCE_ON_START = process.env.ANNOUNCE_ON_START === 'true';

if (!fsSync.existsSync(AUTH_DIR)) {
    fsSync.mkdirSync(AUTH_DIR, { recursive: true });
}

const limiter = createRateLimiter({ windowMs: 60000, max: 5 });

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: AUTH_DIR }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--disable-gpu',
        ],
    },
});

client.on('qr', (qr) => {
    console.log('Scan this QR code with WhatsApp on your phone:');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => console.log('Authenticated.'));
client.on('auth_failure', (message) => console.error('Authentication failed:', message));
client.on('loading_screen', (percent) => console.log(`Loading ${percent}%`));
client.on('disconnected', (reason) => console.warn('Disconnected:', reason));

client.on('ready', async () => {
    console.log('Client ready.');

    let target;
    try {
        const chats = await client.getChats();
        target = chats.find((chat) => chat.id._serialized === GROUP_ID);
    } catch (error) {
        console.error('Could not list chats:', error.message);
        return;
    }

    if (!target) {
        // Printing the available groups is the fastest way to fix a wrong ID.
        console.error(`No group matches WHATSAPP_GROUP_ID (${GROUP_ID}). Available groups:`);
        const chats = await client.getChats();
        chats.filter((chat) => chat.isGroup)
            .forEach((chat) => console.error(`  ${chat.id._serialized}  ${chat.name}`));
        return;
    }

    console.log(`Listening in "${target.name}".`);

    if (ANNOUNCE_ON_START) {
        try {
            await target.sendMessage(formatHelp());
        } catch (error) {
            console.error('Could not send the startup announcement:', error.message);
        }
    }
});

/**
 * whatsapp-web.js emits 'message' only for *incoming* messages, so commands
 * typed from the linked account itself were never seen -- which is exactly how
 * you would test your own bot. 'message_create' covers both directions, so it is
 * the only listener; adding 'message' as well would double-handle every incoming
 * command.
 */
client.on('message_create', async (message) => {
    // For messages sent by this account, the chat is the recipient.
    const chatId = message.fromMe ? message.to : message.from;
    if (chatId !== GROUP_ID) {
        return;
    }

    const command = parseCommand(message.body);
    if (!command) {
        return; // Ordinary conversation. Say nothing.
    }

    const userId = message.author || message.from || 'unknown';
    if (!limiter.allow(userId)) {
        console.warn(`Rate limited: ${userId}`);
        return; // Silently, so a flood is not amplified into a reply per message.
    }

    console.log(`${command} from ${userId}`);
    try {
        const reply = await runCommand(command);
        if (reply) {
            await message.reply(reply);
        }
    } catch (error) {
        console.error(`${command} failed:`, error);
        await message.reply('Could not read the ELO data. Try again shortly.');
    }
});

process.on('unhandledRejection', (reason) => {
    console.error('Unhandled rejection:', reason);
});

process.on('uncaughtException', (error) => {
    // Exit rather than continue in an unknown state; the supervisor restarts us.
    console.error('Uncaught exception:', error);
    process.exit(1);
});

console.log('Starting ELO Snitch Bot...');
client.initialize().catch((error) => {
    console.error('Failed to initialise the client:', error);
    process.exit(1);
});
