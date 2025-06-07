const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// Initialize WhatsApp client
const client = new Client({
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process', // <- this one doesn't works in windows
            '--disable-gpu'
        ]
    }
});

// Listen for QR code
client.on('qr', qr => {
    // console.log('QR RECEIVED', qr);
    qrcode.generate(qr, { small: true });
});

// Listen for ready state
client.on('ready', () => {
    console.log('Client is ready!');
    // Test sending a message to yourself
    client.sendMessage('me', 'WhatsApp bot test successful!');
});

// Start the client
client.initialize();
