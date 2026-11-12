// 独立实现交叉验证：Node 原生 crypto vs main.py 纯 Python AES/MD5/SHA256
// 固定向量，无现网外发。运行：node parity.js
const crypto = require('node:crypto');

function sign(data, saltHex, ts, token) {
    const md5 = crypto.createHash('md5').update(data, 'utf8').digest('hex');
    const preimage = md5 + saltHex + String(ts);
    const key = crypto.createHash('sha256').update(token, 'utf8').digest();
    const iv = Buffer.from(saltHex, 'hex');
    const c = crypto.createCipheriv('aes-256-cbc', key, iv);
    const ct = Buffer.concat([c.update(Buffer.from(preimage, 'utf8')), c.final()]);
    return {salt: saltHex, timestamp: ts, sign: ct.toString('hex')};
}

const v = sign('天气', '000102030405060708090a0b0c0d0e0f',
    1739178536, 'aimode_token_1739178536');
console.log(JSON.stringify(v));
