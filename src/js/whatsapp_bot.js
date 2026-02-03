const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs').promises;
const fsSync = require('fs');
const dotenv = require('dotenv');
const path = require('path');


console.log("Starting ELO Snitch Bot...");

// Ensure the .wwebjs_auth directory exists
const authDir = path.join(__dirname, '.wwebjs_auth');
if (!fsSync.existsSync(authDir)) {
    fsSync.mkdirSync(authDir, { recursive: true });
}
const envPath = path.resolve(__dirname, '../../config/.env');
console.log('Looking for .env file at:', envPath);
if (!fsSync.existsSync(envPath)) {
    console.error('.env file not found at:', envPath);
    console.log('Please create the .env file with WHATSAPP_GROUP_ID');
    process.exit(1);
} else {
    console.log('.env file found');  // For debugging
}

dotenv.config({ path: envPath });
// Check environment variables
console.log('WHATSAPP_GROUP_ID:', process.env.WHATSAPP_GROUP_ID ? 'Set' : 'Not set');

// Test message
const testMessage = "*ELO SNITCH BOT ONLINE*\n\nAvailable commands:\n!elocheck - Shows full ELO changes list\n!winrate - Shows winrate list\n!topelo - Shows top 5 ELO changes\n\nType any command to get started!";

// Initialize the client with LocalAuth for session persistence
console.log('Initializing WhatsApp client...');

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: authDir
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu'
        ]
    }
});

console.log('Client created, setting up event listeners...');

client.on('loading_screen', (percent, message) => {
    console.log('Loading screen:', percent, message);
});

client.on('authenticated', () => {
    console.log('Client authenticated successfully');
});

client.on('auth_failure', msg => {
    console.error('Authentication failed:', msg);
});

client.on('qr', (qr) => {
    console.log('QR Code received, scan with your phone:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', async () => {
    console.log('Client is ready!');
    console.log('Bot is now active and monitoring messages...');
    
    // Test basic functionality first
    try {
        const info = await client.info;
        console.log('Client info:', info.wid._serialized);
    } catch (error) {
        console.error('Error getting client info:', error);
    }


    // Send test message with better error handling
    setTimeout(async () => {
        try {
            const groupId = process.env.WHATSAPP_GROUP_ID;
            if (!groupId) {
                console.error('Whatsapp group ID not set in environment variables');
                return;
            }

            console.log('Attempting to send test message...');
            console.log('Target group ID:', groupId);

            // Format group ID properly
            const formattedGroupId = groupId.includes('@g.us') ? groupId : `${groupId}@g.us`;
            console.log('Formatted group ID:', formattedGroupId);

            // Get all chats for debugging
            console.log('Fetching all chats...');
            const chats = await client.getChats();
            console.log(`Found ${chats.length} chats total`);
            
            const groups = chats.filter(chat => chat.isGroup);
            console.log(`Found ${groups.length} group chats:`);
            groups.forEach((group, index) => {
                console.log(`  ${index + 1}. ${group.name}: ${group.id._serialized}`);
            });

            // Find target chat
            const targetChat = groups.find(chat => chat.id._serialized === formattedGroupId);
            
            if (!targetChat) {
                console.error('Could not find target group chat');
                console.log('Available group IDs:');
                groups.forEach(group => {
                    console.log(`  - ${group.id._serialized} (${group.name})`);
                });
                return;
            }

            console.log(`Found target group: ${targetChat.name}`);
            
            // Send message
            await targetChat.sendMessage(testMessage);
            console.log('Test message sent successfully!');

        } catch (error) {
            console.error('Error in test message routine:', error);
            console.error('Stack trace:', error.stack);
        }
    }, 10000); // 10 second delay
});

client.on('disconnected', (reason) => {
    console.log('Disconnected:', reason);
    console.log('Attempting to reconnect...');
});

client.on('error', (err) => {
    console.error('Client error:', err);
});

// Add process error handlers
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Rest of your functions (keeping them the same)
async function getLatestEloFile() {
    const eloChangesDir = '../../data/elo_changes';
    
    try {
        if (!fsSync.existsSync(eloChangesDir)) {
            console.log('ELO changes directory does not exist:', eloChangesDir);
            return null;
        }
        
        const items = await fs.readdir(eloChangesDir);
        const folders = [];
        
        for (const item of items) {
            const fullPath = path.join(eloChangesDir, item);
            const stat = await fs.stat(fullPath);
            if (stat.isDirectory()) {
                folders.push(item);
            }
        }
        
        if (folders.length === 0) {
            return null;
        }
        
        const latestFolder = folders.sort().pop();
        const latestFolderPath = path.join(eloChangesDir, latestFolder);
        
        const files = await fs.readdir(latestFolderPath);
        const jsonFiles = files.filter(file => file.endsWith('.json'));
        
        if (jsonFiles.length === 0) {
            return null;
        }
        
        const latestFile = jsonFiles.sort().pop();
        return path.join(latestFolderPath, latestFile);
    } catch (error) {
        console.error('Error in getLatestEloFile:', error);
        return null;
    }
}

async function getLatestWinrateFile() {
    const winrateDir = '../../data/winrate/solo';
    
    try {
        if (!fsSync.existsSync(winrateDir)) {
            console.log('Winrate directory does not exist:', winrateDir);
            return null;
        }
        
        const items = await fs.readdir(winrateDir);
        const folders = [];
        
        for (const item of items) {
            const fullPath = path.join(winrateDir, item);
            const stat = await fs.stat(fullPath);
            if (stat.isDirectory()) {
                folders.push(item);
            }
        }
        
        if (folders.length === 0) {
            console.error('No date folders found in winrate directory');
            return null;
        }
        
        const latestFolder = folders.sort().pop();
        const latestFolderPath = path.join(winrateDir, latestFolder);
        
        const files = await fs.readdir(latestFolderPath);
        const winrateFiles = files.filter(file => file.endsWith('.json') && file.startsWith('winrate_solo'));
        
        if (winrateFiles.length === 0) {
            console.error('No winrate JSON files found in', latestFolderPath);
            return null;
        }
        
        const latestFile = winrateFiles.sort().pop();
        return path.join(latestFolderPath, latestFile);
    } catch (error) {
        console.error('Error in getLatestWinrateFile:', error);
        return null;
    }
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    const [datePart, timePart] = timestamp.split('_');
    const [year, month, day] = datePart.split('-');
    const [hour, minute, second] = timePart.split('-');
    return `${year}/${month}/${day} ${hour}:${minute}:${second}`;
}

function formatWinrate(data) {
    if (!data.changes || data.changes.length === 0) {
        return "No winrate data available!";
    }

    const sortedData = [...data.changes].sort((a, b) => {
        if (b.win_rate !== a.win_rate) {
            return b.win_rate - a.win_rate;
        }
        return (b.wins + b.losses) - (a.wins + a.losses);
    });

    let message = "*SOLO/DUO QUEUE WIN RATES*\n\n";
    
    message += "*Top 10 Players by Win Rate:*\n";
    sortedData.slice(0, 10).forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${player.tier} ${player.rank} (${player.win_rate}% | ${player.wins}W-${player.losses}L)\n`;
    });
    
    const mostGames = [...data.changes].sort((a, b) => 
        (b.wins + b.losses) - (a.wins + a.losses)
    ).slice(0, 5);
    
    message += "\n*Most Active Players:*\n";
    mostGames.forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${player.wins + player.losses} games (${player.win_rate}%)\n`;
    });
    
    const totalGames = data.changes.reduce((sum, p) => sum + p.wins + p.losses, 0);
    const avgWinRate = data.changes.reduce((sum, p) => sum + p.win_rate, 0) / data.changes.length;
    
    message += `\n*Stats Summary:*\n`;
    message += `Total Players: ${data.changes.length}\n`;
    message += `Total Games Tracked: ${totalGames}\n`;
    message += `Average Win Rate: ${avgWinRate.toFixed(2)}%\n`;
    
    if (data.timestamp) {
        const formattedTime = formatTimestamp(data.timestamp);
        message += `\n_Last updated: ${formattedTime}_`;
    }
    
    return message;
}

function formatTopChanges(data) {
    if (!data.top_changes || data.top_changes.length === 0) {
        return "No ELO changes available!";
    }

    let message = "*TOP 5 ELO CHANGES*\n\n";
    
    data.top_changes.forEach((change, index) => {
        const changeText = change.change.includes('PROMOTED') || 
                         change.change.includes('DEMOTED') ? 
                         `*${change.change}*` : 
                         change.change;
        
        message += `#${index + 1} ${change.summ_id}: ${change.tier} (${change.lp} LP) ${changeText}\n`;
    });
    
    return message;
}

function formatFullChanges(data) {
    if (!data.changes || data.changes.length === 0) {
        return "No ELO changes available!";
    }

    let message = "*FULL ELO CHANGES*\n\n";
    
    const queues = {};
    data.changes.forEach(change => {
        if (!queues[change.queue]) {
            queues[change.queue] = [];
        }
        queues[change.queue].push(change);
    });
    
    Object.entries(queues).forEach(([queue, changes]) => {
        message += `*${queue}*: \n`;
        changes.forEach((change, index) => {
            const changeText = change.change.includes('PROMOTED') || 
                             change.change.includes('DEMOTED') ? 
                             `*${change.change}*` : 
                             change.change;
            
            message += `  ${index + 1}. ${change.summ_id}: ${change.tier} (${change.lp} LP) ${changeText}\n`;
        });
        message += '\n';
    });
    
    if (data.timestamp) {
        message += `\n_Last updated: ${formatTimestamp(data.timestamp)}_`;
    }

    return message;
}

client.on('message', async message => {
    console.log(`📨 Received message: ${message.body}`);
    
    if (message.body.toLowerCase() === '!topelo') {
        console.log('Processing !topelo command');
        const latestFile = await getLatestEloFile();
        if (!latestFile) {
            await message.reply('No ELO changes data available!');
            return;
        }

        try {
            const fileContent = await fs.readFile(latestFile, 'utf8');
            const data = JSON.parse(fileContent);
            const formattedMessage = formatTopChanges(data);
            await message.reply(formattedMessage);
            console.log('Sent topelo response');
        } catch (error) {
            console.error('Error processing ELO data:', error);
            await message.reply('Error processing ELO data. Please try again later.');
        }
    }

    else if (message.body.toLowerCase() === '!elocheck') {
        console.log('Processing !elocheck command');
        const latestFile = await getLatestEloFile();
        if (!latestFile) {
            await message.reply('No ELO changes data available!');
            return;
        }

        try {
            const fileContent = await fs.readFile(latestFile, 'utf8');
            const data = JSON.parse(fileContent);
            const formattedMessage = formatFullChanges(data);
            await message.reply(formattedMessage);
            console.log('Sent elocheck response');
        } catch (error) {
            console.error('Error processing ELO data:', error);
            await message.reply('Error processing ELO data. Please try again later.');
        }
    }

    else if (message.body.toLowerCase() === '!winrate') {
        console.log('Processing !winrate command');
        const latestFile = await getLatestWinrateFile();
        if (!latestFile) {
            await message.reply('No winrate data available!');
            return;
        }

        try {
            const fileContent = await fs.readFile(latestFile, 'utf8');
            const data = JSON.parse(fileContent);
            const formattedMessage = formatWinrate(data);
            await message.reply(formattedMessage);
            console.log('Sent winrate response');
        } catch (error) {
            console.error('Error processing winrate data:', error);
            await message.reply('Error processing winrate data. Please try again later.');
        }
    }
});

console.log('🔄 Initializing client...');
client.initialize().catch(error => {
    console.error('Failed to initialize client:', error);
    process.exit(1);
});
