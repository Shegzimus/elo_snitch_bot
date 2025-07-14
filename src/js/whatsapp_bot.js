const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const dotenv = require('dotenv');

dotenv.config();

// Test message
const testMessage = "*TEST MESSAGE FROM ELO SNITCH BOT*\n\nThis is a test message to verify the WhatsApp bot is working correctly.";

// Initialize the client with session configuration
const client = new Client({
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    },
    session: null // Force new session
});

client.on('qr', (qr) => {
    // Generate and scan this code with your phone
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('Client is ready!');
    console.log('Bot is now active and monitoring messages...');
    
    // Send the test message to the group
    client.sendMessage(process.env.WHATSAPP_GROUP_ID, testMessage)
        .then(() => {
            console.log('Message sent successfully!');
        })
        .catch(err => {
            console.error('Error sending message:', err);
        });
});

// Handle disconnection
client.on('disconnected', (reason) => {
    console.log('Disconnected:', reason);
    console.log('Attempting to reconnect...');
    client.initialize();
});

// Handle errors
client.on('error', (err) => {
    console.error('Error:', err);
    console.log('Attempting to reconnect...');
    client.initialize();
});

// Function to get the latest ELO changes file
function getLatestEloFile() {
    const files = fs.readdirSync('.').filter(file => file.startsWith('elo_changes_'));
    if (files.length === 0) {
        return null;
    }
    return files.sort().pop();
}

// Function to format ELO changes data
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
        
        message += `#${index + 1} (${change.summ_id}): ${change.tier} (${change.lp} LP) ${changeText}\n`;
    });
    
    return message;
}

function formatFullChanges(data) {
    if (!data.changes || data.changes.length === 0) {
        return "No ELO changes available!";
    }

    let message = "*FULL ELO CHANGES*\n\n";
    
    // Group by queue type
    const queues = {};
    data.changes.forEach(change => {
        if (!queues[change.queue]) {
            queues[change.queue] = [];
        }
        queues[change.queue].push(change);
    });
    
    // Format each queue's changes
    Object.entries(queues).forEach(([queue, changes]) => {
        message += `*${queue}*: \n`;
        changes.forEach((change, index) => {
            const changeText = change.change.includes('PROMOTED') || 
                             change.change.includes('DEMOTED') ? 
                             `*${change.change}*` : 
                             change.change;
            
            message += `  ${index + 1}. (${change.summ_id}): ${change.tier} (${change.lp} LP) ${changeText}\n`;
        });
        message += '\n';
    });
    
    return message;
}

client.on('message', async message => {
    console.log(`Received message: ${message.body}`);
    
    // Handle !topelo command - shows top 5 changes
    if (message.body.toLowerCase() === '!topelo') {
        const latestFile = getLatestEloFile();
        if (!latestFile) {
            await message.reply('No ELO changes data available!');
            return;
        }

        try {
            const data = JSON.parse(fs.readFileSync(latestFile, 'utf8'));
            const formattedMessage = formatTopChanges(data);
            await message.reply(formattedMessage);
        } catch (error) {
            console.error('Error processing ELO data:', error);
            await message.reply('Error processing ELO data. Please try again later.');
        }
    }

    // Handle !elocheck command - shows full changes
    else if (message.body.toLowerCase() === '!elocheck') {
        const latestFile = getLatestEloFile();
        if (!latestFile) {
            await message.reply('No ELO changes data available!');
            return;
        }

        try {
            const data = JSON.parse(fs.readFileSync(latestFile, 'utf8'));
            const formattedMessage = formatFullChanges(data);
            await message.reply(formattedMessage);
        } catch (error) {
            console.error('Error processing ELO data:', error);
            await message.reply('Error processing ELO data. Please try again later.');
        }
    }
});

// Initialize
client.initialize();
