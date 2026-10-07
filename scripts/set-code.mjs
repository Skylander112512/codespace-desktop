import {readFileSync,writeFileSync,renameSync,chmodSync,existsSync} from 'node:fs';
import {randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {hashViewerCode} from '../viewer-code.mjs';
import readline from 'node:readline/promises';

async function hidden(prompt){
  if(!process.stdin.isTTY){
    const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
    for await(const line of input){input.close();return line.trim();}
    return '';
  }
  process.stdout.write(prompt);
  const input=process.stdin;
  const previous=input.isRaw;
  input.setRawMode(true);input.resume();
  return new Promise((resolve,reject)=>{
    let value='';
    const finish=(error)=>{input.off('data',data);input.setRawMode(previous);input.pause();process.stdout.write('\n');error?reject(error):resolve(value);};
    const data=chunk=>{
      for(const char of chunk.toString()){
        if(char==='\u0003'){finish(new Error('Cancelled'));return;}
        if(char==='\r'||char==='\n'){finish();return;}
        if(char==='\u007f'||char==='\b')value=value.slice(0,-1);
        else if(/\d/.test(char) && value.length<13)value+=char;
      }
    };
    input.on('data',data);
  });
}
try{
  const code=await hidden('Choose your Chromebook code (5–12 digits, hidden): ');
  const viewerCode=await hashViewerCode(code);
  const path=fileURLToPath(new URL('../.secrets.json',import.meta.url));
  const keys=existsSync(path)?JSON.parse(readFileSync(path,'utf8')):{hostKey:randomBytes(32).toString('base64url'),viewerKey:randomBytes(32).toString('base64url')};
  const temporary=path+'.tmp';
  writeFileSync(temporary,JSON.stringify({...keys,viewerCode}),{mode:0o600});
  chmodSync(temporary,0o600);renameSync(temporary,path);
  console.log('Your private Chromebook code is saved. Restart npm start to use it.');
}catch(error){console.error(error.message);process.exitCode=1;}
