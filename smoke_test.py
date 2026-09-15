"""Windows source and frozen executable smoke verification with real Tk widgets."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from PIL import Image
from imaging import Processor, encode_image, validate_profile


def run(app):
    report=Path(os.environ.get('WATERMARK_SMOKE_REPORT','smoke-report.json'))
    try:
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'photo.png';logo=Path(d)/'logo.png'
            Image.new('RGB',(640,480),'#345678').save(path)
            Image.new('RGBA',(100,50),(255,0,0,180)).save(logo)
            app._append([str(path)])
            app.watermark_path=str(logo)
            app.edit_mode.set('裁切框');app.output_ratio.set('4:5')
            app.update();app.render_preview()
            assert len(app._handles)==4
            x,y=app._handles['se'];app.pointer_down(SimpleNamespace(x=x,y=y))
            app.pointer_move(SimpleNamespace(x=x-40,y=y-40));app.pointer_up();app.render_preview()
            assert str(path) in app._crops
            app.edit_mode.set('Logo');app.render_preview()
            assert 'rotate' in app._handles
            x,y=app._handles['se'];app.pointer_down(SimpleNamespace(x=x,y=y))
            old=app.wm_scale.get();app.pointer_move(SimpleNamespace(x=x+20,y=y+20));app.pointer_up();app.render_preview()
            assert app.wm_scale.get()!=old
            x,y=app._handles['rotate'];app.pointer_down(SimpleNamespace(x=x,y=y))
            app.pointer_move(SimpleNamespace(x=x+25,y=y));app.pointer_up();app.render_preview()
            assert abs(app.wm_rotation.get())>0
            app.edit_profile(next(iter(app.profiles)))
            for child in app.winfo_children():
                if child.winfo_class()=='Toplevel':child.destroy()
            app.update()
            assert app._thumbs
            c=validate_profile(dict(ratio='4:5',mode='指定寬高',width=320,height=400,format='WEBP'))
            im,exif=Processor(app.config(),app._crops).process_profile(str(path),c)
            assert im.size==(320,400)
            data=encode_image(im,'WEBP',90,max_kb=100)
            assert data[:4]==b'RIFF'
        report.write_text(json.dumps({'success':True,'dnd_available':__import__('app').DND_AVAILABLE,'checks':['Tk startup','crop handles and drag','logo scaling and rotation','profile editor','thumbnails','WebP export']}),encoding='utf-8')
        app.destroy()
    except Exception:
        import traceback
        report.write_text(json.dumps({'success':False,'error':traceback.format_exc()}),encoding='utf-8')
        app.destroy()
        os._exit(1)
