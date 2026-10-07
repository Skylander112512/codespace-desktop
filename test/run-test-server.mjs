import {hashViewerCode} from '../viewer-code.mjs';
import {createDesktopServer} from '../server.mjs';
const app=createDesktopServer({hostKey:'synthetic-host-key-00000000000000000000',viewerKey:'synthetic-viewer-key-000000000000000000',viewerCode:await hashViewerCode('94726'),iceServers:[]});
app.server.listen(3000,'127.0.0.1',()=>console.log('Synthetic test server ready on localhost:3000'));
process.on('SIGTERM',async()=>{await app.close();process.exit(0);});
