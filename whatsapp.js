const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// Initialize WhatsApp client
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// Add error handlers
client.on('error', (err) => {
    console.error('WhatsApp client error:', err);
});

client.on('disconnected', (reason) => {
    console.log('Disconnected:', reason);
});

// Listen for QR code
client.on('qr', qr => {
    console.log('QR RECEIVED');
    qrcode.generate(qr, { small: true });
});

// Listen for authentication
client.on('authenticated', () => {
    console.log('Authenticated successfully!');
});

// SINGLE ready event listener - this is the main one
client.on('ready',  async () => {
    console.log('Client is ready!');
    console.log('Bot connected successfully!');
    
    try {
        console.log('Attempting to get bot info...');
        const info = await client.info;
        console.log('Bot info:', {
            id: info.wid._serialized,
            name: info.pushname
        });

        console.log('Attempting to send message to self...');
        try {
            // Get the current user's ID
            const myId = info.wid._serialized;
            const result = await client.sendMessage(myId, 'WhatsApp bot test successful!');
            console.log('Message sent successfully:', result);
        } catch (sendError) {
            console.error('Failed to send message:', sendError);
            console.error('Error details:', {
                message: sendError.message,
                stack: sendError.stack
            });
        }
    } catch (error) {
        console.error('Failed to get bot info:', error);
        console.error('Error details:', {
            message: error.message,
            stack: error.stack
        });
    }
});

client.on ('ready', async () => {
    const phoneNumber = '08164738265';
    const message = 'Hello! I am a WhatsApp bot for League of Legends rank tracking.';

    const chatId = `${phoneNumber}@c.us`;

    await sendMessage(chatId, message);
});

client.on('message', message => {
    if (message.body === "hello" || message.body === "Hello"){
        message.reply("Hello! I am a WhatsApp bot for League of Legends rank tracking.");
    }
});

async function sendMessage(to, text) {
    try{
        await client.sendMessage(to, text);
        console.log (`Message sent to ${to}: ${text}` );
    }catch(error){
        console.error(`Failed to send message to ${to}: ${error.message}`);
    }
}

// Add this function to read the latest ELO changes
async function sendEloUpdates() {
    try {
        // Get the latest JSON file
        const fs = require('fs');
        const path = require('path');
        const files = fs.readdirSync('.');
        const eloFiles = files.filter(file => file.startsWith('elo_changes_'));
        const latestFile = eloFiles.sort().pop();
        
        if (latestFile) {
            const data = JSON.parse(fs.readFileSync(latestFile, 'utf8'));
            await client.sendMessage(groupChatId, data.message);
        }
    } catch (error) {
        console.error('Error sending ELO updates:', error);
    }
}

// Listen for messages
// client.on('message', async message => {
//     if (message.body === '!test') {
//         await message.reply('I am alive and ready to help!');
//     }
// });

// Start the client
client.initialize();
