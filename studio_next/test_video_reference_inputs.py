"""Actual local input transport and owned-media custody; no GPU inference claim."""
import copy,hashlib,importlib.util,json,tempfile,unittest
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from studio_next.comfy_video_runtime import LocalComfyVideoClient,bind_reference_images,validate_video_job
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.test_comfy_video_runtime import job


@unittest.skipUnless(importlib.util.find_spec('PIL'),'Actual PNG decoder required')
class ActualReferenceInputTests(unittest.TestCase):
    def image(self,root):
        from PIL import Image
        p=Path(root)/'original.png';Image.new('RGBA',(17,13),(10,90,180,211)).save(p)
        return p

    def test_real_multipart_carries_exact_png_in_hash_namespace_and_rejects_changed_receipt(self):
        observed=[];receipt={}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']))
                message=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
                observed.append((self.path,{part.get_param('name',header='content-disposition'):(part.get_filename(),part.get_payload(decode=True)) for part in message.iter_parts()}))
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(receipt).encode())
            def log_message(self,*a):pass
        with tempfile.TemporaryDirectory() as root:
            png=self.image(root);digest=sha256_file(png)
            receipt.update(name=digest+'.png',subfolder='zx7-body',type='input')
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                client=LocalComfyVideoClient('http://127.0.0.1:'+str(server.server_port))
                self.assertEqual(client.upload_image(png,digest),'zx7-body/'+digest+'.png')
                path,parts=observed[0];self.assertEqual(path,'/upload/image')
                self.assertEqual(parts['image'],(digest+'.png',png.read_bytes()))
                self.assertEqual(parts['subfolder'][1],b'zx7-body')
                self.assertEqual(parts['overwrite'][1],b'true')
                receipt['subfolder']='../other-project'
                with self.assertRaisesRegex(ValueError,'identity'):client.upload_image(png,digest)
                with self.assertRaisesRegex(ValueError,'original'):client.upload_image(png,'a'*64)
                self.assertEqual(len(observed),2)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)

    def reference(self,root):
        p=self.image(root);v=MediaVault(Path(root)/'vault')
        record=v.ingest(p,mime='image/png',rights='owner_supplied',source_type='owner_upload',
            source_id='original-reference-test',evidence='Original test pixels',owner_or_generator='test author')
        return p,{'source':p.name,'asset_id':sha256_file(p),'attestation_id':record['attestation_id']}

    def test_only_approved_distinct_slots_receive_attested_decoded_original(self):
        with tempfile.TemporaryDirectory() as root:
            p,media=self.reference(root);graph={'load':{'inputs':{'image':'old.png'}}}
            meta={'images':{'product':{'node':'load','key':'image'}},'required_images':['product']}
            actual=job();actual['images']=[{'binding':'product','media':media}];validate_video_job(actual)
            seen=[]
            class Upload:
                def upload_image(self,path,digest):
                    seen.append(Path(path).read_bytes());return 'zx7-body/'+digest+'.png'
            result=bind_reference_images(graph,meta,actual,Upload(),root,Path(root)/'vault')
            self.assertEqual(seen,[p.read_bytes()]);self.assertEqual(result,[(p,media)])
            self.assertEqual(graph['load']['inputs']['image'],'zx7-body/'+media['asset_id']+'.png')
            for changes in ({'images':[]},{'images':[{'binding':'unknown','media':media}]}):
                with self.assertRaisesRegex(ValueError,'required or unregistered'):bind_reference_images(graph,meta,{**actual,**changes},Upload(),root,Path(root)/'vault')
            duplicate=copy.deepcopy(meta);duplicate['images']['second']=duplicate['images']['product']
            with self.assertRaisesRegex(ValueError,'distinct'):bind_reference_images(graph,duplicate,actual,Upload(),root,Path(root)/'vault')
            invalid=copy.deepcopy(actual);invalid['images']*=2
            with self.assertRaisesRegex(ValueError,'distinct'):validate_video_job(invalid)

    def test_upload_cannot_redirect_binding_or_change_original_source(self):
        with tempfile.TemporaryDirectory() as root:
            p,media=self.reference(root);graph={'load':{'inputs':{'image':'old'}}}
            meta={'images':{'product':{'node':'load','key':'image'}}};actual={**job(),'images':[{'binding':'product','media':media}]}
            class WrongPath:
                def upload_image(self,path,digest):return '../../someone-else.png'
            with self.assertRaisesRegex(ValueError,'unregistered input path'):bind_reference_images(graph,meta,actual,WrongPath(),root,Path(root)/'vault')
            class MutateOriginal:
                def upload_image(self,path,digest):
                    p.write_bytes(b'changed original during upload');return 'zx7-body/'+digest+'.png'
            with self.assertRaisesRegex(ValueError,'changed during'):bind_reference_images(graph,meta,actual,MutateOriginal(),root,Path(root)/'vault')

if __name__=='__main__':unittest.main()
