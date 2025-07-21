const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const dotenv = require('dotenv');
const path = require('path');
const envPath = path.resolve(__dirname, '../../config/.env');

dotenv.config({ path: envPath });

// Test message
const testMessage = "*ELO SNITCH BOT ONLINE*\n\nI'm ready to help you track ELO changes and snitch on these hoes! Available commands:\n\n!topelo - Shows top 5 ELO changes\n!fullelo - Shows full ELO changes list\n\nType any command to get started!";

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
    
    // Add a small delay before sending the test message
    setTimeout(async () => {
        try {
            const groupId = process.env.WHATSAPP_GROUP_ID;
            if (!groupId) {
                console.error('WhatsApp group ID not configured in .env file');
                return;
            }

            // Check if client is fully connected
            const isConnected = await client.isConnected();
            if (!isConnected) {
                console.error('Client is not fully connected yet');
                return;
            }

            // Attempt to send message with retries
            let retries = 3;
            while (retries > 0) {
                try {
                    const chat = await client.getChatById(groupId);
                    if (!chat) {
                        console.error('Could not find chat with ID:', groupId);
                        return;
                    }

                    await chat.sendMessage(testMessage);
                    console.log('Message sent successfully!');
                    break;
                } catch (err) {
                    console.error(`Attempt ${4 - retries}: Error sending message:`, err);
                    if (retries > 1) {
                        console.log(`Retrying in 2 seconds...`);
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }
                    retries--;
                }
            }

            if (retries === 0) {
                console.error('Failed to send message after 3 attempts');
            }
        } catch (error) {
            console.error('Unexpected error:', error);
        }
    }, 8000); // Increased delay to 8 seconds to ensure full connection
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
    const eloChangesDir = '../../data/elo_changes';
    
    // Get all date folders
    const folders = fs.readdirSync(eloChangesDir)
        .filter(item => fs.statSync(`${eloChangesDir}/${item}`).isDirectory());
    
    if (folders.length === 0) {
        return null;
    }
    
    // Get the latest folder (sorted by date)
    const latestFolder = folders.sort().pop();
    const latestFolderPath = `${eloChangesDir}/${latestFolder}`;
    
    // Get all JSON files in the latest folder
    const files = fs.readdirSync(latestFolderPath)
        .filter(file => file.endsWith('.json'));
    
    if (files.length === 0) {
        return null;
    }
    
    // Get the latest file (sorted by timestamp)
    const latestFile = files.sort().pop();
    return `${latestFolderPath}/${latestFile}`;
}

// Function to get the latest winrate file
function getLatestWinrateFile() {
    const winrateDir = '../../data/winrate/solo';
    
    // Get all date folders
    const folders = fs.readdirSync(winrateDir)
        .filter(item => {
            const fullPath = path.join(winrateDir, item);
            return fs.statSync(fullPath).isDirectory();
        });
    
    if (folders.length === 0) {
        console.error('No date folders found in winrate directory');
        return null;
    }
    
    // Get the latest folder (sorted by date)
    const latestFolder = folders.sort().pop();
    const latestFolderPath = path.join(winrateDir, latestFolder);
    
    // Get all JSON files in the latest folder
    const files = fs.readdirSync(latestFolderPath)
        .filter(file => file.endsWith('.json') && file.startsWith('winrate_solo'));
    
    if (files.length === 0) {
        console.error('No winrate JSON files found in', latestFolderPath);
        return null;
    }
    
    // Get the latest file (sorted by timestamp)
    const latestFile = files.sort().pop();
    return path.join(latestFolderPath, latestFile);
}

// Function to format winrate data
function formatWinrate(data) {
    if (!data.changes || data.changes.length === 0) {
        return "No winrate data available!";
    }

    // Sort by win rate descending, then by total games descending
    const sortedData = [...data.changes].sort((a, b) => {
        if (b.win_rate !== a.win_rate) {
            return b.win_rate - a.win_rate; // Higher win rate first
        }
        return (b.wins + b.losses) - (a.wins + a.losses); // More games first if win rates are equal
    });

    let message = "*SOLO/DUO QUEUE WIN RATES*\n\n";
    
    // Add top 10 players by win rate
    message += "*Top 10 Players by Win Rate:*\n";
    sortedData.slice(0, 10).forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${player.tier} ${player.rank} (${player.win_rate}% | ${player.wins}W-${player.losses}L)\n`;
    });
    
    // Add players with most games
    const mostGames = [...data.changes].sort((a, b) => 
        (b.wins + b.losses) - (a.wins + a.losses)
    ).slice(0, 5);
    
    message += "\n*Most Active Players:*\n";
    mostGames.forEach((player, index) => {
        message += `${index + 1}. ${player.summ_id} - ${player.wins + player.losses} games (${player.win_rate}%)\n`;
    });
    
    // Add summary stats
    const totalGames = data.changes.reduce((sum, p) => sum + p.wins + p.losses, 0);
    const avgWinRate = data.changes.reduce((sum, p) => sum + p.win_rate, 0) / data.changes.length;
    
    message += `\n*Stats Summary:*\n`;
    message += `Total Players: ${data.changes.length}\n`;
    message += `Total Games Tracked: ${totalGames}\n`;
    message += `Average Win Rate: ${avgWinRate.toFixed(2)}%\n`;
    
    // Add timestamp if available
    if (data.timestamp) {
        // Format: Convert "2025-07-20_21-52-54" to "2025/07/20 21:52:54"
        const [datePart, timePart] = data.timestamp.split('_');
        const [year, month, day] = datePart.split('-');
        const [hour, minute, second] = timePart.split('-');
        const formattedTime = `${year}/${month}/${day} ${hour}:${minute}:${second}`;
        message += `\n_Last updated: ${formattedTime}_`;
    }
    
    return message;
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
        
        message += `#${index + 1} ${change.summ_id}: ${change.tier} (${change.lp} LP) ${changeText}\n`;
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
            
            message += `  ${index + 1}. ${change.summ_id}: ${change.tier} (${change.lp} LP) ${changeText}\n`;
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

    // Handle !winrate command - shows winrate
    else if (message.body.toLowerCase() === '!winrate') {
        const latestFile = getLatestWinrateFile();
        if (!latestFile) {
            await message.reply('No winrate data available!');
            return;
        }

        try {
            const data = JSON.parse(fs.readFileSync(latestFile, 'utf8'));
            const formattedMessage = formatWinrate(data);
            await message.reply(formattedMessage);
        } catch (error) {
            console.error('Error processing winrate data:', error);
            await message.reply('Error processing winrate data. Please try again later.');
        }
    }
});










client.initialize();
