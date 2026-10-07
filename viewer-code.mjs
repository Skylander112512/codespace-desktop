import {randomBytes, scrypt, timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
const derive=promisify(scrypt);
export async function hashViewerCode(code){
  if(typeof code!=='string' || !/^\d{5,12}$/.test(code))throw new Error('Choose 5–12 digits.');
  const salt=randomBytes(16).toString('hex');
  const hash=await derive(code,salt,32);
  return {salt,hash:hash.toString('hex')};
}
export async function verifyViewerCode(code,record){
  if(typeof code!=='string' || !/^\d{5,12}$/.test(code) || !record ||
      !/^[0-9a-f]{32}$/.test(record.salt) || !/^[0-9a-f]{64}$/.test(record.hash))return false;
  return timingSafeEqual(await derive(code,record.salt,32),Buffer.from(record.hash,'hex'));
}
